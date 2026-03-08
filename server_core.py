# server_core.py
#!/usr/bin/env python3
import socket
import re
import requests
from datetime import datetime
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

HOST = '0.0.0.0'
PORT = 5015
LARAVEL_URL = "https://pr.nitbd.com/iclock/cdata/"

verifyTypes = {'0':'Password/Other','1':'Fingerprint','2':'Card','3':'Password','15':'Face','25':'Palm'}

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server.bind((HOST, PORT))
server.listen(10)

def start_server(log_fn):
    """Run TCP server in a thread. log_fn(text) prints logs to UI."""
    while True:
        try:
            client, addr = server.accept()
            data = client.recv(131072)
            if not data:
                client.close()
                continue

            raw_str = data.decode(errors="ignore")
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            log_fn(f"[{timestamp}] Incoming: {addr}")

            # 1. Attendance
            if "table=rtlog" in raw_str.lower() or "table=attlog" in raw_str.lower():
                log_fn(f"  --> [FIND] Attendance Data! Processing...")
                # Flexible regex: allow whitespace, delimiter, case-insensitive
                sn_match = re.search(r'sn\s*=\s*([A-Z0-9]+)', raw_str, re.I)
                pin_match = re.search(r'pin\s*=\s*(\d+)', raw_str, re.I)
                time_match = re.search(r'time\s*=\s*([\d-]+\s[\d:]+)', raw_str, re.I)
                vtype_match = re.search(r'verifytype\s*=\s*(\d+)', raw_str, re.I)

                postData = {
                    'device_sn': sn_match.group(1) if sn_match else 'Unknown',
                    'user_id': pin_match.group(1) if pin_match else 'Unknown',
                    'time': time_match.group(1) if time_match else 'Unknown',
                    'type_code': vtype_match.group(1) if vtype_match else '0',
                    'type_name': verifyTypes.get(vtype_match.group(1) if vtype_match else '0', 'Other'),
                    'raw_data': raw_str  # Always send raw data
                }

                log_fn(f"  --> [Data:{timestamp}] User: {postData['user_id']} | Type: {postData['type_name']} | RAW: {postData['raw_data'][:100]}")

                try:
                    requests.post(LARAVEL_URL, data=postData, headers={'User-Agent': 'PostmanRuntime/7.40.0'}, timeout=5, verify=False)
                    log_fn(f"  --> [SUCCESS:{timestamp}] Forwarded to Server")
                except Exception as e:
                    log_fn(f"  --> [ERROR:{timestamp}] API Fail: {e}")

                response_body = "OK"

            # 2. Handshake / registry
            elif "options=all" in raw_str or "/iclock/registry" in raw_str:
                log_fn(f"  --> [HANDSHAKE:{timestamp}] Sending RegistryCode and Config...")
                response_body = "RegistryCode=None\nServerVersion=3.1.1\nServerName=ADMS\nPushVersion=3.1.1\nErrorDelay=60\nDelay=30\nTransInterval=1\nTransFlag=1111111111\nRealtime=1\nEncrypt=0"

            else:
                log_fn(f"  --> [HEARTBEAT:{timestamp}] Sending OK & Logging Raw Data")
                # Always send raw_data to Laravel for debug
                postData = {
                    'device_sn': 'Unknown',
                    'user_id': 'Unknown',
                    'time': 'Unknown',
                    'type_code': '0',
                    'type_name': 'Other',
                    'raw_data': raw_str
                }
                try:
                    requests.post(LARAVEL_URL, data=postData, headers={'User-Agent': 'PostmanRuntime/7.40.0'}, timeout=5, verify=False)
                    log_fn(f"  --> [SUCCESS:{timestamp}] Raw Data Forwarded to Server")
                except Exception as e:
                    log_fn(f"  --> [ERROR:{timestamp}] Raw Data API Fail: {e}")
                response_body = "OK"

            # 3. HTTP response
            http_res = (
                "HTTP/1.1 200 OK\r\n"
                "Content-Type: text/plain;charset=UTF-8\r\n"
                f"Content-Length: {len(response_body)}\r\n"
                "Connection: close\r\n\r\n"
                f"{response_body}"
            )

            client.sendall(http_res.encode())
            client.close()
            log_fn(f"  --> [CLOSE:{timestamp}] Response Sent.\n")

        except Exception as e:
            log_fn(f"  --> [SYSTEM ERROR:{timestamp}] {e}")
