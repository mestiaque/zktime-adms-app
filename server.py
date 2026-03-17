#!/usr/bin/env python3
"""
ZKTeco ADMS Proxy Server
========================
Receives attendance and access-control events from ZKTeco devices via the
ADMS push protocol and forwards them to a Laravel backend.

Run:
    python server.py
"""

import os
import sys
import logging
import threading
from datetime import datetime

import requests
import urllib3
from flask import Flask, request, make_response

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


# ── Log callback (set by GUI; falls back to print) ─────────────────────────────
_log_callback = None


def set_log_callback(fn) -> None:
    """Register a callable(str) that the GUI uses to display server messages."""
    global _log_callback
    _log_callback = fn


def _log(msg: str) -> None:
    if _log_callback:
        _log_callback(msg)
    else:
        print(msg)


# ── Configuration ──────────────────────────────────────────────────────────────
HOST        = "0.0.0.0"
PORT        = 5015
LARAVEL_URL = "https://pr.nitbd.com/iclock/cdata/"

# Verification type codes → human-readable names
VERIFY_TYPES: dict[str, str] = {
    "0":  "Password/Other",
    "1":  "Fingerprint",
    "2":  "Card",
    "3":  "Password",
    "15": "Face",
    "25": "Palm",
}

# Access-control status codes → human-readable names
ACCESS_STATUS: dict[str, str] = {
    "0": "Access Denied",
    "1": "Access Granted",
}

# Standard ADMS handshake/registry response body
HANDSHAKE_RESPONSE = (
    "RegistryCode=None\n"
    "ServerVersion=3.1.1\n"
    "ServerName=ADMS\n"
    "PushVersion=3.1.1\n"
    "ErrorDelay=60\n"
    "Delay=30\n"
    "TransInterval=1\n"
    "TransFlag=1111111111\n"
    "Realtime=1\n"
    "Encrypt=0"
)


# ── Logging Setup ──────────────────────────────────────────────────────────────
# When frozen as a PyInstaller EXE the working directory may be read-only
# (e.g. C:\Program Files\).  Always write logs to a user-writable location.
if getattr(sys, "frozen", False):
    # Running as compiled EXE → %APPDATA%\ZKTimeAdms\logs
    _LOG_DIR = os.path.join(
        os.environ.get("APPDATA", os.path.expanduser("~")),
        "ZKTimeAdms", "logs",
    )
else:
    # Running as plain Python script → ./logs
    _LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")

os.makedirs(_LOG_DIR, exist_ok=True)


def _file_logger(name: str, path: str) -> logging.Logger:
    """Create (or retrieve) a named logger that writes to *path*."""
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    if not logger.handlers:
        handler = logging.FileHandler(path, encoding="utf-8")
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        logger.addHandler(handler)
    return logger


att_log = _file_logger("attendance", os.path.join(_LOG_DIR, "attendance.log"))
acc_log = _file_logger("access",     os.path.join(_LOG_DIR, "access.log"))
err_log = _file_logger("error",      os.path.join(_LOG_DIR, "error.log"))


# ── Flask App ──────────────────────────────────────────────────────────────────
app = Flask(__name__)


# ── Helpers ────────────────────────────────────────────────────────────────────
def _merge_params() -> dict:
    """
    Merge GET query-string params with POST form params into one dict.

    ZKTeco devices put SN / table in the query string and usually send
    pin / time / verifytype either also in the query string (GET) or in an
    application/x-www-form-urlencoded body (POST).  POST values win on
    collision.  Key 'sn' is normalised to 'SN'.
    """
    merged: dict = {}
    merged.update(request.args.to_dict(flat=True))
    if request.form:
        merged.update(request.form.to_dict(flat=True))
    # Some firmware sends lowercase 'sn'
    if "sn" in merged and "SN" not in merged:
        merged["SN"] = merged.pop("sn")
    return merged


def _parse_adms_body(body: str, table: str = "") -> tuple[list[dict], str]:
    """
    Parse a full ADMS POST body that may contain a header section.

    Real device body format:
        STAMP=1234567890\n
        Table=attLog\n
        Size=2\n
        \n
        PIN\tTime\tStatus\tVerify\tWorkCode\tReserved\n
        ...

    Returns:
        (records, stamp) — stamp is the STAMP value (or "" if absent).
        Passing stamp back in the response body as "OK: <stamp>" tells the
        device its data was received and advances its internal cursor.

    attlog / rtlog record fields:
        [0] PIN  [1] Time  [2] Status  [3] Verify  [4] WorkCode  [5] Reserved

    aclog record fields:
        [0] PIN  [1] Time  [2] Door  [3] Event(0=denied,1=granted)  [4] Verify
    """
    stamp = ""
    records: list[dict] = []
    is_aclog = (table == "aclog")

    for line in body.splitlines():
        line = line.strip()
        if not line:
            continue

        # ── Header key=value lines ────────────────────────────────────────────
        if "\t" not in line and "=" in line:
            key, _, val = line.partition("=")
            if key.strip().upper() == "STAMP":
                stamp = val.strip()
            continue  # skip all header lines; only process tab-separated rows

        # ── Data record lines (tab-separated) ─────────────────────────────────
        parts = [p.strip() for p in line.split("\t")]
        if is_aclog:
            if len(parts) >= 4:
                records.append({
                    "pin":        parts[0],
                    "time":       parts[1],
                    "door":       parts[2],
                    "status":     parts[3],
                    "verifytype": parts[4] if len(parts) > 4 else "0",
                })
        else:
            if len(parts) >= 4:
                records.append({
                    "pin":        parts[0],
                    "time":       parts[1],
                    "status":     parts[2],
                    "verifytype": parts[3],
                })

    return records, stamp


# ── Core Functions ─────────────────────────────────────────────────────────────
def parse_attendance(device_sn: str, record: dict) -> dict:
    """
    Build a structured attendance payload from a single ADMS record dict.

    Args:
        device_sn: Serial number of the reporting device.
        record:    Dict with keys pin, time, verifytype (and optionally status).

    Returns:
        Flat dict ready to POST to the Laravel endpoint.
    """
    type_code = str(record.get("verifytype", "0"))
    return {
        "event_type":         "attendance",
        "device_sn":          device_sn,
        "user_id":            record.get("pin", "Unknown"),
        "time":               record.get("time", "Unknown"),
        "type_code":          type_code,
        "type_name":          VERIFY_TYPES.get(type_code, "Other"),
        "access_status_code": "",
        "access_status_name": "",
    }


def parse_access(device_sn: str, record: dict) -> dict:
    """
    Build a structured access-control payload from a single ADMS record dict.

    Args:
        device_sn: Serial number of the reporting device.
        record:    Dict with keys pin, time, status, verifytype.

    Returns:
        Flat dict ready to POST to the Laravel endpoint.
    """
    status_code = str(record.get("status", "0"))
    type_code   = str(record.get("verifytype", "0"))
    return {
        "event_type":         "access",
        "device_sn":          device_sn,
        "user_id":            record.get("pin", "Unknown"),
        "time":               record.get("time", "Unknown"),
        "type_code":          type_code,
        "type_name":          VERIFY_TYPES.get(type_code, "Other"),
        "access_status_code": status_code,
        "access_status_name": ACCESS_STATUS.get(status_code, "Unknown"),
    }


def forward_to_laravel(payload: dict) -> None:
    """
    POST a single parsed event to the Laravel backend.
    Intended to run inside a daemon thread so the device gets its HTTP 200
    response instantly without waiting for the upstream call to resolve.

    Args:
        payload: Flat dict built by parse_attendance() or parse_access().
    """
    try:
        resp = requests.post(
            LARAVEL_URL,
            data=payload,
            headers={"User-Agent": "ZKTimeADMS/1.0"},
            timeout=10,
            verify=False,
        )
        _log(
            f"    [LARAVEL] {resp.status_code} ← "
            f"{payload['event_type']} user={payload['user_id']}"
        )
    except Exception as exc:
        err_log.error(
            "Laravel forward failed | payload=%s | error=%s", payload, exc
        )
        _log(f"    [LARAVEL ERROR] {exc}")


def handle_handshake() -> str:
    """
    Log and return the ADMS device configuration/registry response string.

    Returns:
        Multi-line key=value string expected by ZKTeco firmware.
    """
    _log(f"  [HANDSHAKE] Registry config sent to {request.remote_addr}")
    return HANDSHAKE_RESPONSE


# ── Routes ─────────────────────────────────────────────────────────────────────
@app.route("/iclock/registry", methods=["GET", "POST"])
def registry():
    """Handle explicit /iclock/registry handshake requests."""
    return make_response(handle_handshake(), 200, {"Content-Type": "text/plain"})


@app.route("/iclock/getrequest", methods=["GET", "POST"])
def getrequest():
    """
    Device polls this endpoint for pending server commands.
    Return an empty OK — no commands queued in this implementation.
    """
    sn = request.args.get("SN") or request.args.get("sn", "Unknown")
    _log(f"  [GETREQUEST] Device SN={sn} polling for commands")
    return make_response("OK", 200, {"Content-Type": "text/plain"})


@app.route("/iclock/devicecmd", methods=["GET", "POST"])
def devicecmd():
    """Acknowledge device command execution reports."""
    sn = request.args.get("SN") or request.args.get("sn", "Unknown")
    _log(f"  [DEVICECMD] SN={sn} reported command result")
    return make_response("OK", 200, {"Content-Type": "text/plain"})


@app.route("/iclock/cdata", methods=["GET", "POST"])
def cdata():
    """
    Main ADMS data endpoint.  Handles:
      - Handshake  (GET ?options=all)
      - Attendance (POST ?table=attlog or ?table=rtlog)
      - Access     (POST ?table=aclog)
      - Heartbeat  (GET/POST, any other table value)

    Always responds HTTP 200 / 'OK' so the device does not retry.
    Upstream forwarding to Laravel happens in a background daemon thread.
    """
    ip        = request.remote_addr
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    qs        = request.query_string.decode(errors="ignore")

    _log(f"\n[{timestamp}] {request.method} /iclock/cdata  IP={ip}")
    _log(f"  Query : {qs}")

    # ── Handshake: GET ?options=all ───────────────────────────────────────────
    if "options=all" in qs.lower():
        return make_response(handle_handshake(), 200, {"Content-Type": "text/plain"})

    # ── Merge all parameters ──────────────────────────────────────────────────
    params    = _merge_params()
    device_sn = params.get("SN", "Unknown")
    table     = params.get("table", "").lower()
    raw_body  = request.get_data(as_text=True)

    _log(f"  SN={device_sn}  table={table!r}")
    if raw_body.strip():
        _log(f"  Body  : {raw_body[:300]}")

    # ── Resolve the list of records to process ────────────────────────────────
    # Case 1: single-record URL-encoded form POST (some older firmware)
    # Case 2: multi-record tab-separated raw body with optional header section
    records: list[dict] = []
    stamp = ""
    if request.form and ("pin" in request.form or "PIN" in request.form):
        pin = request.form.get("pin") or request.form.get("PIN", "Unknown")
        records = [
            {
                "pin":        pin,
                "time":       params.get("time", "Unknown"),
                "status":     params.get("status", "0"),
                "verifytype": params.get("verifytype", "0"),
            }
        ]
    elif raw_body.strip():
        records, stamp = _parse_adms_body(raw_body, table=table)

    if stamp:
        _log(f"  STAMP={stamp}  records={len(records)}")

    # ── Attendance (rtlog / attlog) ───────────────────────────────────────────
    if table in ("rtlog", "attlog"):
        if not records:
            _log("  [ATTENDANCE] Body received but no parseable records")
        for rec in records:
            payload = parse_attendance(device_sn, rec)
            att_log.info(
                "SN=%s | User=%s | Time=%s | Verify=%s (%s)",
                payload["device_sn"],
                payload["user_id"],
                payload["time"],
                payload["type_code"],
                payload["type_name"],
            )
            _log(
                f"  [ATTENDANCE] User={payload['user_id']}  "
                f"Time={payload['time']}  Verify={payload['type_name']}"
            )
            threading.Thread(
                target=forward_to_laravel, args=(payload,), daemon=True
            ).start()

    # ── Access Control (aclog) ────────────────────────────────────────────────
    elif table == "aclog":
        if not records:
            _log("  [ACCESS] Body received but no parseable records")
        for rec in records:
            payload = parse_access(device_sn, rec)
            acc_log.info(
                "SN=%s | User=%s | Time=%s | Status=%s (%s)",
                payload["device_sn"],
                payload["user_id"],
                payload["time"],
                payload["access_status_code"],
                payload["access_status_name"],
            )
            _log(
                f"  [ACCESS] User={payload['user_id']}  "
                f"Time={payload['time']}  "
                f"Status={payload['access_status_name']}"
            )
            threading.Thread(
                target=forward_to_laravel, args=(payload,), daemon=True
            ).start()

    # ── Operation log (operlog) — acknowledge only ────────────────────────────
    elif table == "operlog":
        _log(f"  [OPERLOG] SN={device_sn} — {len(records)} operation record(s) received")

    # ── Heartbeat / unknown table ─────────────────────────────────────────────
    else:
        _log(f"  [HEARTBEAT] table={table!r} — acknowledged")

    # ── Response: include STAMP so device advances its internal cursor ─────────
    # Without the correct stamp echo, the device retransmits the same records.
    response_body = f"OK: {stamp}" if stamp else "OK"
    return make_response(response_body, 200, {"Content-Type": "text/plain"})


# ── Entry Point ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    _log("=" * 60)
    _log("  ZKTeco ADMS Proxy Server")
    _log(f"  Listening : http://0.0.0.0:{PORT}")
    _log(f"  Laravel   : {LARAVEL_URL}")
    _log("  Logs      : ./logs/")
    _log("=" * 60)
    # threaded=True lets Flask handle each device request in its own thread
    # while background daemon threads forward data to Laravel concurrently.
    app.run(host=HOST, port=PORT, debug=False, threaded=True, use_reloader=False)
