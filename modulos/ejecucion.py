import time
import cv2
import os
import json
from modulos.reconocimiento import reconocimiento_de_objetos  # Importación correcta
from modulos.banda_transportadora import BandaTransportadora
from modulos.brazo_robotico import BrazoRobotico


def iniciar_ejecucion(form_interpreter, color_interpreter, form_labels, color_labels, cap, banda, brazo):
    """
    Función principal para ejecutar el proceso de reconocimiento y manipulación automática.
    """
    print("Activando banda transportadora...")
    if not banda.serial_connection or not banda.serial_connection.is_open:
        print("La conexión serial de la banda no está abierta.")
        return

    # Estado inicial de la banda
    banda_activada = False
    banda.activar()
    banda_activada = True

    logica_path = "logica_config.json"

    # Verificar que exista el archivo de lógica configurada
    if not os.path.exists(logica_path):
        print("No se encontró el archivo logica_config.json. Deteniendo ejecución.")
        banda.desactivar()
        return

    with open(logica_path, "r") as file:
        logica = json.load(file)

    print("Ejecución en curso...")
    try:
        while True:
            # Capturar un frame de la cámara
            ret, frame = cap.read()
            if not ret:
                print("Error al capturar frame de la cámara. Deteniendo ejecución.")
                break

            # Realizar el reconocimiento de forma y color solo si la banda está activa
            if banda_activada:
                forma = reconocimiento_de_objetos(frame, form_interpreter, form_labels)
                color = reconocimiento_de_objetos(frame, color_interpreter, color_labels)

                if forma == "vacio" or color == "vacio":
                    print("No se detectaron objetos. Continuando...")
                    time.sleep(0.1)
                    continue

                print(f"Objeto detectado: {forma} {color}")

                # Pausar la banda para procesar el objeto
                banda.desactivar()
                banda_activada = False

                # Consultar la lógica configurada
                objeto_encontrado = False
                for regla in logica:
                    if regla["shape"] == forma and regla["color"] == color:
                        movimiento = regla["movement"]
                        print(f"Ejecutando movimiento para: {forma} {color} -> {movimiento}")

                        movimiento_path = os.path.join("movimientos", f"{movimiento}.txt")
                        if os.path.exists(movimiento_path):
                            procesar_movimiento(movimiento_path, brazo)
                        else:
                            print(f"Movimiento '{movimiento}' no encontrado.")
                        objeto_encontrado = True
                        break

                if not objeto_encontrado:
                    print(f"No se encontró una lógica configurada para el objeto detectado: {forma} {color}")

                # Reactivar la banda una vez finalizado el movimiento
                print("Reactivando banda transportadora...")
                banda.activar()
                banda_activada = True  # Asegura que la banda está activa
                time.sleep(1)  # Pausa para evitar procesar el mismo objeto repetidamente

    except KeyboardInterrupt:
        print("Ejecución detenida manualmente.")
    except Exception as e:
        print(f"Error durante la ejecución: {e}")
    finally:
        print("Deteniendo banda transportadora y liberando recursos.")
        banda.desactivar()



def procesar_movimiento(movimiento_path, brazo):
    """
    Procesa un archivo de movimiento con múltiples líneas en el formato:
    Velocidad: 100, Servos: [0, 45, 180, 0, 90, 90]

    Envía los ángulos y la velocidad al brazo robótico.

    - movimiento_path: str, ruta al archivo que contiene las instrucciones.
    - brazo: objeto BrazoRobotico, para enviar los comandos.
    """
    try:
        with open(movimiento_path, "r") as file:
            lines = file.readlines()

        for line in lines:
            line = line.strip()
            if not line:
                continue

            try:
                # Dividir la línea en partes
                parts = line.split(", Servos: ")
                velocidad = int(parts[0].split(":")[1].strip())  # Extraer velocidad
                servos = eval(parts[1].strip())  # Convertir lista de servos a Python

                # Validar longitud de la lista de servos
                if len(servos) != 6:
                    print(f"Error: Se esperaban 6 servos, pero se encontraron {len(servos)}.")
                    continue

                # Mover cada servo
                for i, angulo in enumerate(servos, start=1):
                    brazo.mover_servo(i, angulo, velocidad)
                    time.sleep(0.2)  # Pausa entre movimientos para evitar conflictos

            except ValueError:
                print(f"Línea inválida en el archivo: {line}")
                continue

        print("Movimiento ejecutado con éxito.")
    except FileNotFoundError:
        print(f"Archivo de movimiento no encontrado: {movimiento_path}")
    except Exception as e:
        print(f"Error al procesar movimiento: {e}")

