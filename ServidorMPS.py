import customtkinter as ctk
import socket
import threading
import webbrowser
import qrcode
import requests # Para pedir la lista de clientes a Flask
import time
from PIL import Image
from waitress import serve
from app import app  # Importa la app de Flask desde app.py

# --- Configuración ---
HOST = '0.0.0.0'
PORT = 80
SERVER_URL_LOCAL = f"http://localhost:{PORT}"

class ServerControlApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Panel de Control del Servidor")
        self.geometry("480x520") # Ventana más alta para la lista
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

        self.server_thread = None
        self.server_running = False
        self.local_ip = self.get_local_ip()

        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("green")

        # --- Creación de Widgets ---
        self.main_frame = ctk.CTkFrame(self)
        self.main_frame.pack(pady=15, padx=15, fill="both", expand=True)
        self.main_frame.grid_columnconfigure(0, weight=1)

        self.title_label = ctk.CTkLabel(self.main_frame, text="Servidor de Control Robótico", font=ctk.CTkFont(size=22, weight="bold"))
        self.title_label.grid(row=0, column=0, pady=(10, 5), sticky="ew")

        # Frame para el estado
        self.status_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.status_frame.grid(row=1, column=0, pady=5)
        ctk.CTkLabel(self.status_frame, text="Estado:", font=ctk.CTkFont(size=14)).pack(side="left", padx=(0, 5))
        self.status_indicator_label = ctk.CTkLabel(self.status_frame, text="Detenido", text_color="#d9534f", font=ctk.CTkFont(size=14, weight="bold"))
        self.status_indicator_label.pack(side="left")

        self.toggle_button = ctk.CTkButton(self.main_frame, text="▶  Iniciar Servidor", command=self.toggle_server, height=40, font=ctk.CTkFont(size=14, weight="bold"))
        self.toggle_button.grid(row=2, column=0, pady=15, sticky="ew")

        # Frame para el QR y la info
        self.access_frame = ctk.CTkFrame(self.main_frame)
        self.access_frame.grid(row=3, column=0, pady=10, sticky="ew")
        self.access_frame.grid_columnconfigure(0, weight=1)
        self.access_frame.grid_columnconfigure(1, weight=1)

        self.qr_code_label = ctk.CTkLabel(self.access_frame, text="")
        self.qr_code_label.grid(row=0, column=0, rowspan=2, padx=10, pady=10)
        self.info_label = ctk.CTkLabel(self.access_frame, text="Escanee para conectar desde el móvil:", justify="left", font=ctk.CTkFont(size=12))
        self.info_label.grid(row=0, column=1, sticky="w", padx=10)
        self.ip_entry = ctk.CTkEntry(self.access_frame, font=ctk.CTkFont(family="Courier New"))
        self.ip_entry.grid(row=1, column=1, sticky="ew", padx=10)

        # --- NUEVO: Listado de Clientes ---
        self.clients_label = ctk.CTkLabel(self.main_frame, text="Clientes Conectados (último minuto):", font=ctk.CTkFont(size=14, weight="bold"))
        self.clients_label.grid(row=4, column=0, pady=(10, 5), sticky="w")
        
        self.clients_listbox = ctk.CTkTextbox(self.main_frame, height=80, state="disabled", font=ctk.CTkFont(family="Courier New"))
        self.clients_listbox.grid(row=5, column=0, sticky="ew")

        self.generate_qr_code()
        self.update_ip_info()
        
        # Iniciar el actualizador de clientes
        self.update_clients_list()

    def get_local_ip(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.connect(("8.8.8.8", 80)); ip = s.getsockname()[0]; s.close(); return ip
        except: return "127.0.0.1"

    def generate_qr_code(self):
        server_url_network = f"http://{self.local_ip}:{PORT}"
        qr_img = qrcode.make(server_url_network)
        qr_img = qr_img.resize((100, 100), Image.Resampling.LANCZOS)
        self.qr_ctk_image = ctk.CTkImage(light_image=qr_img, dark_image=qr_img, size=(100, 100))
        self.qr_code_label.configure(image=self.qr_ctk_image)

    def update_ip_info(self):
        self.ip_entry.insert(0, f"http://{self.local_ip}:{PORT}")
        self.ip_entry.configure(state="disabled")

    def start_server_thread(self):
        try:
            self.server_running = True
            self.after(100, self.on_server_started)
            serve(app, host=HOST, port=PORT, threads=8)
        except Exception as e:
            self.server_running = False
            self.after(100, lambda: self.update_status_on_error(str(e)))

    def on_server_started(self):
        self.status_indicator_label.configure(text="Activo", text_color="#5cb85c")
        self.toggle_button.configure(text="■  Detener Servidor", state="normal")
        try: webbrowser.open(SERVER_URL_LOCAL)
        except: print("No se pudo abrir el navegador.")

    def update_status_on_error(self, error_msg):
        self.status_indicator_label.configure(text="Error", text_color="#d9534f")
        self.toggle_button.configure(text="▶  Iniciar Servidor", state="normal")
        print(f"Error del servidor: {error_msg}")

    def toggle_server(self):
        if not self.server_running:
            self.toggle_button.configure(state="disabled", text="Iniciando...")
            self.server_thread = threading.Thread(target=self.start_server_thread, daemon=True)
            self.server_thread.start()
        else:
            self.on_closing()

    def update_clients_list(self):
        if self.server_running:
            try:
                # Hacemos una petición a nuestro propio servidor para obtener la lista
                response = requests.get(f"http://127.0.0.1:{PORT}/get_connected_clients", timeout=1)
                if response.status_code == 200:
                    clients = response.json().get("clients", [])
                    self.clients_listbox.configure(state="normal")
                    self.clients_listbox.delete("1.0", "end")
                    if clients:
                        self.clients_listbox.insert("1.0", "\n".join(clients))
                    else:
                        self.clients_listbox.insert("1.0", "Esperando conexiones...")
                    self.clients_listbox.configure(state="disabled")
            except requests.exceptions.RequestException:
                # Es normal que falle al principio mientras el servidor arranca
                pass
        else:
            self.clients_listbox.configure(state="normal")
            self.clients_listbox.delete("1.0", "end")
            self.clients_listbox.configure(state="disabled")

        # Programar la próxima actualización en 5 segundos
        self.after(5000, self.update_clients_list)

    def on_closing(self):
        print("Cerrando la aplicación...")
        self.destroy()

if __name__ == "__main__":
    app_gui = ServerControlApp()
    app_gui.mainloop()