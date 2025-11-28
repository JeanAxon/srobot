import serial
import time

class BandaTransportadora:
    def __init__(self, port=None, baudrate=9600, timeout=1):

        self.serial_connection = None
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        
    def set_connection(self, connection):
        """
        Asigna una conexión serial abierta (creada en app.py) a este objeto,
        en lugar de abrirla aquí.
        """
        self.serial_connection = connection
        print("Conexión serial asignada a BandaTransportadora.")
        
    def inicializar_conexion(self):
        """
        Inicializa la conexión serial solo si no está ya abierta.
        """
        if self.serial_connection and self.serial_connection.is_open:
            print("La conexión ya está abierta.")
            return

        try:
            self.serial_connection = serial.Serial(self.port, self.baudrate, timeout=self.timeout)
            time.sleep(2)  # Esperar para que el Arduino inicialice
            print(f"Conexión establecida en el puerto {self.port} a {self.baudrate} baud.")
        except serial.SerialException as e:
            print(f"No se pudo establecer la conexión serial: {e}")

    def cerrar_conexion(self):
        """
        Cierra la conexión serial si está abierta.
        """
        if self.serial_connection and self.serial_connection.is_open:
            self.serial_connection.close()
            print("Conexión serial cerrada correctamente.")
        else:
            print("La conexión ya estaba cerrada o no existente.")


    def enviar_comando(self, comando):
        """
        Envía un comando al Arduino a través de serial.
        :param comando: Comando a enviar (string).
        """
        if self.serial_connection and self.serial_connection.is_open:
            try:
                self.serial_connection.write(f"{comando}\n".encode('utf-8'))
                print(f"Comando enviado: {comando}")
            except Exception as e:
                print(f"Error al enviar comando: {e}")
        else:
            print("La conexión serial no está abierta.")

    def activar(self):
        """Activa el movimiento de la banda transportadora."""
        self.enviar_comando("P")

    def desactivar(self):
        """Detiene el movimiento de la banda transportadora."""
        self.enviar_comando("S")

    def direccion_derecha(self):
        """Cambia la dirección de la banda transportadora a la derecha."""
        self.enviar_comando("D")

    def direccion_izquierda(self):
        """Cambia la dirección de la banda transportadora a la izquierda."""
        self.enviar_comando("I")
