import time
import threading
import subprocess
from pyModbusTCP.server import ModbusServer
from pyModbusTCP.client import ModbusClient

class ModbusBridge:
    """
    Clase que actúa como puente entre la Raspberry Pi, el HMI y el PLC.
    
    - Servidor Modbus TCP para el HMI.
    - Cliente Modbus TCP para el PLC.
    - Verificación de conectividad por ping para PLC y HMI.
    """
    def __init__(self, 
                 server_ip="192.168.0.100", server_port=5020,
                 plc_ip="192.168.0.25", plc_port=502,
                 hmi_ip="192.168.0.13"):
        # Configuración del servidor Modbus en la Raspberry Pi
        self.server = ModbusServer(host=server_ip, port=server_port, no_block=True)
        # Configuración del cliente Modbus para conectarse al PLC
        self.plc_client = ModbusClient(host=plc_ip, port=plc_port, auto_open=True, auto_close=True)
        self.running = False

        # IPs para la verificación por ping
        self.plc_ip = plc_ip
        self.hmi_ip = hmi_ip

        # --- PLC -> HMI ---
        self.plc_read_start = 0      # Dirección inicial en el PLC a leer
        self.plc_read_count = 10     # Cantidad de registros a leer
        self.server_plc_data_start = 100  # Dirección en el servidor donde se almacenan los datos

        # --- HMI -> PLC ---
        self.hmi_write_start = 200   # Dirección en el servidor donde el HMI escribe comandos
        self.hmi_write_count = 10    # Cantidad de registros a leer del HMI
        self.plc_write_start = 10    # Dirección en el PLC donde se enviarán los comandos

        # --- Datos para servidor web ---
        self.web_data_start = 300
        self.web_data_count = 5

        # --- Estados de conexión ---
        self.plc_connected = False
        self.hmi_connected = False

    def start(self):
        """Inicia el servidor Modbus y la verificación de dispositivos."""
        self.server.start()
        print(f"Servidor Modbus TCP iniciado en {self.server.host}:{self.server.port}")
        self.running = True

        # Inicia el hilo principal del puente
        self.bridge_thread = threading.Thread(target=self.bridge_loop, daemon=True)
        self.bridge_thread.start()

    def bridge_loop(self):
        """Bucle principal que sincroniza datos entre PLC, HMI y servidor web."""
        while self.running:
            # --- Verificar conexión con el PLC mediante ping ---
            self.plc_connected = self.ping_device(self.plc_ip)

            # --- PLC -> HMI ---
            plc_data = self.plc_client.read_holding_registers(self.plc_read_start, self.plc_read_count)
            if plc_data:
                self.server.data_bank.set_holding_registers(self.server_plc_data_start, plc_data)

            # --- HMI -> PLC ---
            hmi_data = self.server.data_bank.get_holding_registers(self.hmi_write_start, self.hmi_write_count)
            if hmi_data:
                success = self.plc_client.write_multiple_registers(self.plc_write_start, hmi_data)
                if not success:
                    print("Error al enviar datos al PLC.")

            # --- Verificar conexión con el HMI mediante ping ---
            self.hmi_connected = self.ping_device(self.hmi_ip)

            # --- Mostrar estado de conexión ---
            print(f"Estado de Conexión -> PLC: {'Conectado' if self.plc_connected else 'Desconectado'}, "
                  f"HMI: {'Conectado' if self.hmi_connected else 'Desconectado'}")

            time.sleep(1)

    def stop(self):
        """Detiene el servidor Modbus."""
        self.running = False
        self.server.stop()
        print("Servidor Modbus TCP detenido")

    def ping_device(self, ip, timeout=1):
        """Ejecuta un ping al dispositivo con la IP dada. Retorna True si responde, False si no."""
        try:
            result = subprocess.run(
                ["ping", "-c", "1", "-W", str(timeout), ip],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            return result.returncode == 0
        except Exception as e:
            print(f"Error haciendo ping a {ip}: {e}")
            return False

    def get_status(self):
        """Retorna el estado de conexión del PLC y del HMI."""
        return {
            'plc': 'Conectado' if self.plc_connected else 'Desconectado',
            'hmi': 'Conectado' if self.hmi_connected else 'Desconectado'
        }

    def get_plc_data(self):
        """Obtiene los datos almacenados en el servidor Modbus provenientes del PLC."""
        return self.server.data_bank.get_holding_registers(self.server_plc_data_start, self.plc_read_count)

    def send_data_to_plc(self, data):
        """Recibe datos del servidor web y los almacena en el servidor Modbus para enviarlos al PLC."""
        self.server.data_bank.set_holding_registers(self.hmi_write_start, data)
