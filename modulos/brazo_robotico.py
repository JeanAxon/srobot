# archivo: modulos/brazo_robotico.py

import serial
import time

class BrazoRobotico:
    def __init__(self):
        """
        No abrimos el puerto aquí. Simplemente guardamos
        una referencia para usar la misma conexión que abre app.py.
        """
        self.serial_connection = None

    def set_connection(self, connection):
        """
        Recibe la conexión serial abierta por app.py (o cualquier otro módulo)
        y la almacena para enviarle comandos.
        """
        self.serial_connection = connection
        print("Conexión serial asignada a BrazoRobotico.")

    def mover_servo(self, servo_num, angulo, velocidad):
        """
        Ajusta primero la velocidad de los servos, y luego mueve
        un servo específico (1..6) a un ángulo (0..270).

        - servo_num: int, número de servo (1..6)
        - angulo: int (0..270)
        - velocidad: int (1..100)
        """
        if not self.serial_connection or not self.serial_connection.is_open:
            print("No hay conexión serial abierta para mover el servo.")
            return

        # 1. Ajustar la velocidad de TODOS los servos
        comando_vel = f"V,{velocidad}\n"
        self.serial_connection.write(comando_vel.encode('utf-8'))
        time.sleep(0.05)  # Pequeña pausa para que Arduino procese

        # 2. Mover servo (servo_num, angulo)
        comando_servo = f"{servo_num},{angulo}\n"
        self.serial_connection.write(comando_servo.encode('utf-8'))
        time.sleep(0.05)

        print(f"Servo {servo_num} movido a {angulo}° con velocidad {velocidad}.")
