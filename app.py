# app.py
import threading
import tkinter as tk
from tkinter import scrolledtext, messagebox, simpledialog
import socket
import server_core

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
        self.root.title("ZKTime ADMS Proxy")
        self.root.geometry("600x400")
        self.root.resizable(False, False)

        # Close block - initially enabled
        self.close_blocked = True
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        # IP & Port display
        tk.Label(root, text=f"IP: {get_ip()}  |  Port: {server_core.PORT}", font=("Arial", 12, "bold")).pack(pady=5)

        # URL is intentionally hidden from the UI; edit is only via shortcut.

        # Log box
        self.log_box = scrolledtext.ScrolledText(root, width=75, height=20)
        self.log_box.pack(padx=10, pady=5)

        # Single bottom info button.
        tk.Button(root, text="ℹ", width=3, font=("Arial", 10, "bold"),
              command=self.show_info).pack(pady=5)

        # Start server thread
        t = threading.Thread(target=server_core.start_server, args=(self.log,), daemon=True)
        t.start()
        self.log(f"Server started on {server_core.HOST}:{server_core.PORT}")

        # Bind Ctrl+Alt+A to edit URL
        self.root.bind_all("<Control-Alt-a>", lambda e: self.edit_url())
        self.root.bind_all("<Control-Alt-A>", lambda e: self.edit_url())

    def log(self, text):
        self.log_box.insert(tk.END, text + "\n")
        self.log_box.see(tk.END)

    def edit_url(self):
        """Edit LARAVEL_URL with Ctrl+Alt+A shortcut."""
        new_url = simpledialog.askstring("Edit Server URL", "Enter new Laravel URL:", initialvalue=server_core.LARAVEL_URL)
        if new_url and new_url.strip():
            server_core.LARAVEL_URL = new_url.strip()
            self.log(f"URL updated to: {server_core.LARAVEL_URL}")

    def show_info(self):
        """Show device configuration and developer information."""
        info_text = """1 >> COMM. অপশনে প্রবেশ করুন
2 >> Cloud Server / ADMS নির্বাচন করুন
3 >> Enable Domain : OFF
4 >> Server Address : 192.168.1.15
5 >> Server Port : 8000
6 >> HTTPS : Disable

----------------------------

Developer Info
Developer : M. Estiaque Ahmed Khan
Company   : Natore IT
Website     : natoreit.com"""
        messagebox.showinfo("Device Configuration", info_text)

    def on_closing(self):
        """Handle window close - ask for forced exit."""
        if messagebox.askyesno("Exit", "Do you want to force exit?"):
            self.log("Server force exited by user.")
            self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = ServerApp(root)
    root.mainloop()
