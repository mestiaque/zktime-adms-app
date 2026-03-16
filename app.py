# app.py
import os
import threading
import tkinter as tk
from tkinter import scrolledtext, messagebox, simpledialog
import socket

import server  # new Flask-based server


# ── Helpers ────────────────────────────────────────────────────────────────────
def get_local_ip() -> str:
    """Detect the primary LAN IP address."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()


def is_port_open(port: int) -> bool:
    """Return True if something is actually listening on 127.0.0.1:port."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(0.4)
    try:
        s.connect(("127.0.0.1", port))
        return True
    except Exception:
        return False
    finally:
        s.close()


# ── GUI Application ────────────────────────────────────────────────────────────
class ServerApp:
    _PORT_CHECK_INTERVAL_MS = 3000  # re-check port status every 3 seconds

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("ZKTime ADMS Proxy")
        self.root.geometry("620x440")
        self.root.resizable(False, False)
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        # ── Top info bar ───────────────────────────────────────────────────────
        top_frame = tk.Frame(root)
        top_frame.pack(fill=tk.X, padx=10, pady=(8, 2))

        tk.Label(
            top_frame,
            text=f"IP: {get_local_ip()}  |  Port: {server.PORT}",
            font=("Arial", 11, "bold"),
        ).pack(side=tk.LEFT)

        # Port status indicator (● coloured dot + text)
        self.port_status_var = tk.StringVar(value="● Checking…")
        self.port_label = tk.Label(
            top_frame,
            textvariable=self.port_status_var,
            font=("Arial", 11, "bold"),
            fg="orange",
        )
        self.port_label.pack(side=tk.RIGHT)

        # ── Log box ────────────────────────────────────────────────────────────
        self.log_box = scrolledtext.ScrolledText(root, width=77, height=22, font=("Consolas", 9))
        self.log_box.pack(padx=10, pady=6)

        # ── Bottom button bar ──────────────────────────────────────────────────
        btn_frame = tk.Frame(root)
        btn_frame.pack(pady=(0, 8))

        tk.Button(
            btn_frame, text="ℹ Info", width=8, font=("Arial", 10, "bold"),
            command=self.show_info,
        ).pack(side=tk.LEFT, padx=4)

        tk.Button(
            btn_frame, text="🔗 URL", width=8, font=("Arial", 10, "bold"),
            command=self.edit_url,
        ).pack(side=tk.LEFT, padx=4)

        tk.Button(
            btn_frame, text="✖ Exit", width=8, font=("Arial", 10, "bold"),
            fg="red", command=self.on_closing,
        ).pack(side=tk.LEFT, padx=4)

        # ── Start Flask server in background thread ────────────────────────────
        server.set_log_callback(self._safe_log)
        flask_thread = threading.Thread(
            target=server.app.run,
            kwargs={
                "host":        server.HOST,
                "port":        server.PORT,
                "debug":       False,
                "threaded":    True,
                "use_reloader": False,
            },
            daemon=True,
        )
        flask_thread.start()
        self._safe_log(f"Server started on {server.HOST}:{server.PORT}")

        # ── Keyboard shortcut: Ctrl+Alt+A → edit URL ──────────────────────────
        self.root.bind_all("<Control-Alt-a>", lambda _e: self.edit_url())
        self.root.bind_all("<Control-Alt-A>", lambda _e: self.edit_url())

        # ── Start periodic port-status polling ─────────────────────────────────
        self.root.after(1500, self._poll_port_status)

    # ── Log helpers ───────────────────────────────────────────────────────────
    def _safe_log(self, text: str) -> None:
        """Thread-safe log: schedule GUI update on the main thread."""
        self.root.after(0, self._append_log, text)

    def _append_log(self, text: str) -> None:
        self.log_box.insert(tk.END, text + "\n")
        self.log_box.see(tk.END)

    # ── Port status polling ───────────────────────────────────────────────────
    def _poll_port_status(self) -> None:
        if is_port_open(server.PORT):
            self.port_status_var.set(f"● Port {server.PORT} OPEN")
            self.port_label.config(fg="green")
        else:
            self.port_status_var.set(f"● Port {server.PORT} CLOSED")
            self.port_label.config(fg="red")
        self.root.after(self._PORT_CHECK_INTERVAL_MS, self._poll_port_status)

    # ── URL editor ────────────────────────────────────────────────────────────
    def edit_url(self) -> None:
        """Open a dialog to update the Laravel forwarding URL (Ctrl+Alt+A)."""
        new_url = simpledialog.askstring(
            "Edit Laravel URL",
            "Enter new Laravel endpoint URL:",
            initialvalue=server.LARAVEL_URL,
            parent=self.root,
        )
        if new_url and new_url.strip():
            server.LARAVEL_URL = new_url.strip()
            self._safe_log(f"[CONFIG] Laravel URL updated → {server.LARAVEL_URL}")

    # ── Info dialog ───────────────────────────────────────────────────────────
    def show_info(self) -> None:
        info_text = (
            "1 >> COMM. অপশনে প্রবেশ করুন\n"
            "2 >> Cloud Server / ADMS নির্বাচন করুন\n"
            "3 >> Enable Domain : OFF\n"
            f"4 >> Server Address : {get_local_ip()}\n"
            f"5 >> Server Port    : {server.PORT}\n"
            "6 >> HTTPS : Disable\n\n"
            "----------------------------\n\n"
            "Developer Info\n"
            "Developer : M. Estiaque Ahmed Khan\n"
            "Company   : Natore IT\n"
            "Website   : natoreit.com"
        )
        messagebox.showinfo("Device Configuration", info_text)

    # ── Close handler ─────────────────────────────────────────────────────────
    def on_closing(self) -> None:
        """Ask once, then force-kill the entire process (stops Flask too)."""
        if messagebox.askyesno("Exit", "Server বন্ধ করে বের হবেন?", parent=self.root):
            self._append_log("[EXIT] Force closing server...")
            self.root.update()          # flush the log line to screen
            os._exit(0)                 # hard-kill: stops Flask + all threads


# ── Entry Point ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    root = tk.Tk()
    app = ServerApp(root)
    root.mainloop()

