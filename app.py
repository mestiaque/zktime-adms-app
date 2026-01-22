# app.py
import threading
import tkinter as tk
from tkinter import scrolledtext, messagebox
import socket
from server_core import start_server, HOST, PORT

def get_ip():
    """Detect local IP for display."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip

class ServerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("G4 Pro ADMS Proxy")
        self.root.geometry("600x400")
        self.root.resizable(False, False)

        # Close block
        self.root.protocol("WM_DELETE_WINDOW", lambda: None)

        # IP & Port display
        tk.Label(root, text=f"IP: {get_ip()}  |  Port: {PORT}", font=("Arial", 12, "bold")).pack(pady=5)

        # Log box
        self.log_box = scrolledtext.ScrolledText(root, width=75, height=20)
        self.log_box.pack(padx=10, pady=5)

        # Developer info
        tk.Button(root, text="ℹ", width=3, font=("Arial", 10, "bold"),
                  command=lambda: messagebox.showinfo("Developer Info", "M. Estiaque Ahmed Khan\nNatore IT")).pack(pady=5)

        # Start server thread
        t = threading.Thread(target=start_server, args=(self.log,), daemon=True)
        t.start()
        self.log(f"Server started on {HOST}:{PORT}")

    def log(self, text):
        self.log_box.insert(tk.END, text + "\n")
        self.log_box.see(tk.END)

if __name__ == "__main__":
    root = tk.Tk()
    app = ServerApp(root)
    root.mainloop()
