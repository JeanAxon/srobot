import customtkinter as ctk
import socket
import threading
import webbrowser
import qrcode
import requests 
import time
import sys
import os
from PIL import Image
from waitress import serve

# --- Importamos la fábrica de la aplicación ---
from app import create_app

class ServerControlApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("S-Robot Control (Windows)")
        self.geometry("500x620") 
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

        self.server_thread = None
        self.server_running = False
        
        # Detectar IP local y definir puerto inicial
        self.local_ip = self.get_local_ip()
        self.port = 80 # Intentaremos el 80 primero, si falla, usaremos 5000
        
        # Crear instancia de Flask (pero no iniciarla aún)
        self.flask_app = create_app()

        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("green")

        # --- Interfaz Gráfica ---
        self.setup_ui()
        
        # Generar QR inicial (se actualizará si cambia el puerto)
        self.update_connection_info()
        
        # Iniciar bucle de actualización de clientes
        self.update_clients_list()

    def setup_ui(self):
        self.main_frame = ctk.CTkFrame(self)
        self.main_frame.pack(pady=15, padx=15, fill="both", expand=True)
        self.main_frame.grid_columnconfigure(0, weight=1)

        # Título
        self.title_label = ctk.CTkLabel(self.main_frame, text="Servidor S-Robot", font=ctk.CTkFont(size=22, weight="bold"))
        self.title_label.grid(row=0, column=0, pady=(10, 5), sticky="ew")

        # Estado
        self.status_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.status_frame.grid(row=1, column=0, pady=5)
        ctk.CTkLabel(self.status_frame, text="Estado:", font=ctk.CTkFont(size=14)).pack(side="left", padx=(0, 5))
        self.status_indicator_label = ctk.CTkLabel(self.status_frame, text="Detenido", text_color="#d9534f", font=ctk.CTkFont(size=14, weight="bold"))
        self.status_indicator_label.pack(side="left")

        # Botón Principal
        self.toggle_button = ctk.CTkButton(self.main_frame, text="▶  Iniciar Servidor", command=self.toggle_server, height=45, font=ctk.CTkFont(size=14, weight="bold"))
        self.toggle_button.grid(row=2, column=0, pady=15, sticky="ew")

        # Panel de Acceso (QR + IP)
        self.access_frame = ctk.CTkFrame(self.main_frame)
        self.access_frame.grid(row=3, column=0, pady=10, sticky="ew")
        self.access_frame.grid_columnconfigure(0, weight=1)
        self.access_frame.grid_columnconfigure(1, weight=3)

        self.qr_code_label = ctk.CTkLabel(self.access_frame, text="")
        self.qr_code_label.grid(row=0, column=0, rowspan=2, padx=15, pady=10)
        
        self.info_label = ctk.CTkLabel(self.access_frame, text="Escanee para conectar:", justify="left", font=ctk.CTkFont(size=12))
        self.info_label.grid(row=0, column=1, sticky="sw", padx=10)
        
        self.ip_entry = ctk.CTkEntry(self.access_frame, font=ctk.CTkFont(family="Courier New", size=14))
        self.ip_entry.grid(row=1, column=1, sticky="nw", padx=10, pady=(0, 10))

        # Lista de Clientes
        self.clients_label = ctk.CTkLabel(self.main_frame, text="Clientes Activos:", font=ctk.CTkFont(size=14, weight="bold"))
        self.clients_label.grid(row=4, column=0, pady=(10, 5), sticky="w")
        
        self.clients_listbox = ctk.CTkTextbox(self.main_frame, height=150, state="disabled", font=ctk.CTkFont(family="Courier New"))
        self.clients_listbox.grid(row=5, column=0, sticky="nsew", padx=5, pady=5)

    def get_local_ip(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return "127.0.0.1"

    def update_connection_info(self):
        """Genera el QR y actualiza el texto de la IP basado en el puerto actual"""
        url = f"http://{self.local_ip}:{self.port}"
        
        # Generar QR
        qr = qrcode.QRCode(box_size=10, border=2)
        qr.add_data(url)
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color="black", back_color="white")
        
        # Redimensionar para UI
        qr_img = qr_img.resize((100, 100), Image.Resampling.LANCZOS)
        self.qr_ctk_image = ctk.CTkImage(light_image=qr_img, dark_image=qr_img, size=(100, 100))
        self.qr_code_label.configure(image=self.qr_ctk_image)
        
        # Actualizar Entry
        self.ip_entry.configure(state="normal")
        self.ip_entry.delete(0, "end")
        self.ip_entry.insert(0, url)
        self.ip_entry.configure(state="disabled")

    def check_port(self, port):
        """Verifica si un puerto está libre"""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            return s.connect_ex(('localhost', port)) != 0

    def start_waitress(self):
        """Lógica para iniciar Waitress con fallback de puerto"""
        try:
            # Intento 1: Puerto por defecto (80)
            if not self.check_port(self.port):
                print(f"Puerto {self.port} ocupado. Cambiando a 5000...")
                self.port = 5000
            
            # Actualizar UI con el puerto final decidido
            self.after(0, self.update_connection_info)
            self.after(0, self.on_server_started)
            
            # Iniciar servidor (Bloqueante)
            print(f"Iniciando Waitress en {self.local_ip}:{self.port}")
            serve(self.flask_app, host='0.0.0.0', port=self.port, threads=8)
            
        except OSError as e:
            self.server_running = False
            self.after(0, lambda: self.update_status_on_error(f"Error de puerto: {e}"))
        except Exception as e:
            self.server_running = False
            self.after(0, lambda: self.update_status_on_error(str(e)))

    def on_server_started(self):
        self.server_running = True
        self.status_indicator_label.configure(text=f"ONLINE (Puerto {self.port})", text_color="#5cb85c")
        self.toggle_button.configure(text="■  Servidor Ejecutándose", state="disabled", fg_color="#555555")
        
        # Abrir navegador automáticamente
        try:
            webbrowser.open(f"http://localhost:{self.port}")
        except: pass

    def update_status_on_error(self, error_msg):
        self.status_indicator_label.configure(text="Error al iniciar", text_color="#d9534f")
        self.toggle_button.configure(text="▶  Reintentar", state="normal")
        self.clients_listbox.configure(state="normal")
        self.clients_listbox.insert("end", f"\nError: {error_msg}")
        self.clients_listbox.configure(state="disabled")

    def toggle_server(self):
        if not self.server_running:
            self.toggle_button.configure(state="disabled", text="Iniciando...")
            self.server_thread = threading.Thread(target=self.start_waitress, daemon=True)
            self.server_thread.start()

    def update_clients_list(self):
        """Consulta a la API local para ver quién está conectado"""
        if self.server_running:
            try:
                url = f"http://127.0.0.1:{self.port}/get_connected_clients"
                response = requests.get(url, timeout=0.5)
                
                if response.status_code == 200:
                    data = response.json()
                    clients = data.get("clients", [])
                    
                    text_content = ""
                    if clients:
                        text_content = "Dispositivos conectados:\n" + "\n".join([f"• {ip}" for ip in clients])
                    else:
                        text_content = "Esperando conexiones..."
                        
                    self.clients_listbox.configure(state="normal")
                    self.clients_listbox.delete("1.0", "end")
                    self.clients_listbox.insert("1.0", text_content)
                    self.clients_listbox.configure(state="disabled")
            except Exception:
                pass # Silenciar errores de conexión si el servidor se está cerrando
                
        self.after(2000, self.update_clients_list)

    def on_closing(self):
        # Waitress es difícil de matar limpiamente, así que forzamos la salida del proceso
        self.destroy()
        os._exit(0)

if __name__ == "__main__":
    app_gui = ServerControlApp()
    app_gui.mainloop()