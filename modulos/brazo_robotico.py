# archivo: modulos/brazo_robotico.py

import serial
import time

class BrazoRobotico:
    def __init__(self):
        """
        Inicializa los ángulos de los 6 servos en 90°.
        """
        self.serial_connection = None
        self.angulos_servos = {1: 90.0, 2: 90.0, 3: 90.0, 4: 90.0, 5: 90.0, 6: 90.0}
        self.velocidad_actual = 50  # Valor inicial de velocidad (1-100)
        self.controlling_logical = [0, 1, 2, 4, 3, 5, 6]  # Para servos físicos 1 a 6, el servo lógico que los controla
        self.physical_servo_for_logical = {1: 1, 2: 2, 3: 4, 4: 3, 5: 5, 6: 6}

    def set_connection(self, connection):
        """
        Asigna la conexión serial ya abierta.
        """
        self.serial_connection = connection
        print("Conexión serial asignada a BrazoRobotico.")

    def mover_servos(self, nuevos_angulos, velocidad):
        """
        Envía un único comando global para mover todos los servos.
        
        Formato: "A,angulo1,angulo2,angulo3,angulo4,angulo5,angulo6,velocidad\n"
        
        :param nuevos_angulos: dict con claves 1..6 y valores en [0, 180]
        :param velocidad: int de 1 a 100
        """
        if not self.serial_connection or not self.serial_connection.is_open:
            print("No hay conexión serial abierta para mover los servos.")
            return

        # Validar que los ángulos estén en rango
        for servo in nuevos_angulos:
            if nuevos_angulos[servo] < 0 or nuevos_angulos[servo] > 180:
                print(f"Error: Ángulo {nuevos_angulos[servo]} fuera de rango para servo {servo}.")
                return

        # Actualizar el estado interno
        self.angulos_servos = nuevos_angulos.copy()

        # Construir y enviar el comando global con el mapeo
        angles_for_command = [nuevos_angulos[self.controlling_logical[i]] for i in range(1, 7)]
        comando = "A," + ",".join(map(str, angles_for_command)) + f",{velocidad}\n"
        self.serial_connection.write(comando.encode('utf-8'))
        print(f"Comando enviado: {comando.strip()}")

    def mover_servo_individual(self, servo_num, angulo, velocidad=None):
        """
        Envía un comando individual para mover un servo.
        Formato: "S,servo_num,angulo\n"
        
        Si se especifica velocidad y es distinta a la actual, se envía un comando global
        que actualiza solo ese servo.
        """
        if not self.serial_connection or not self.serial_connection.is_open:
            print("No hay conexión serial abierta para mover los servos.")
            return

        if angulo < 0 or angulo > 180:
            print(f"Error: Ángulo {angulo} fuera de rango para servo {servo_num}.")
            return

        if velocidad is not None and velocidad != self.velocidad_actual:
            intended_angles = self.angulos_servos.copy()
            intended_angles[servo_num] = angulo
            angles_for_command = [intended_angles[self.controlling_logical[i]] for i in range(1, 7)]
            comando = "A," + ",".join(map(str, angles_for_command)) + f",{velocidad}\n"
            self.serial_connection.write(comando.encode('utf-8'))
            self.velocidad_actual = velocidad
            print(f"Comando global individual: servo {servo_num} actualizado a {angulo} con velocidad {velocidad}.")
        else:
            physical_servo = self.physical_servo_for_logical[servo_num]
            comando = f"S,{physical_servo},{angulo}\n"
            self.serial_connection.write(comando.encode('utf-8'))
            print(f"Servo {servo_num} (físico {physical_servo}) movido individualmente a {angulo}.")

        # Actualizar el estado interno
        self.angulos_servos[servo_num] = angulo