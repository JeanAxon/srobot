# web/modulos/ejecucion.py
import time
import cv2
import os
import json
import logging
from .reconocimiento import reconocimiento_de_objetos
from .banda_transportadora import BandaTransportadora
from .brazo_robotico import BrazoRobotico

# Configuración del logging para mostrar solo el mensaje
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",  # Solo el mensaje, sin timestamps ni niveles
    filename=os.path.join("..", "ejecucion.log"),
    filemode="a"
)
console = logging.StreamHandler()
console.setLevel(logging.INFO)
formatter = logging.Formatter("%(message)s")
console.setFormatter(formatter)
logging.getLogger().addHandler(console)

# Constantes de configuración
VELOCIDAD_CONVERSION = 60.0
BUFFER_SEGURIDAD = 0.2
TIEMPO_ESPERA_ENTRE_MOVIMIENTOS = 1
TIEMPO_LIMPIEZA = 2.0  # Tiempo para despejar el área
MUESTRAS_VERIFICACION_VACIO = 5  # Muestras para confirmar vacío
UMBRAL_CONSISTENCIA_DETECCION = 3  # Detecciones consistentes requeridas
RUTA_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # web/
RUTA_LOGICA = os.path.join(RUTA_BASE, "logica_config.json")
RUTA_MOVIMIENTOS = os.path.join(RUTA_BASE, "movimientos")

# Bandera global
stop_execution = False

def calcular_tiempo_movimiento(current_angles, nuevos_angulos, velocidad):
    """Calcula tiempo de movimiento con precisión dinámica"""
    if velocidad <= 0 or not nuevos_angulos:
        return 0.0
    
    deltas = [abs(nuevos_angulos[servo] - current_angles.get(servo, 0)) for servo in nuevos_angulos]
    max_delta = max(deltas) if deltas else 0
    
    velocidad_efectiva = (velocidad / 100.0) * VELOCIDAD_CONVERSION
    return (max_delta / velocidad_efectiva) + BUFFER_SEGURIDAD if velocidad_efectiva > 0 else 0.0

def detener_ejecucion():
    global stop_execution
    stop_execution = True
    logging.info("Detención solicitada por usuario")

def procesar_movimiento(movimiento_path, brazo):
    """Ejecuta movimientos con sincronización inteligente"""
    try:
        if not os.path.exists(movimiento_path):
            logging.info(f"Error: Archivo de movimiento no encontrado: {movimiento_path}")
            return

        with open(movimiento_path, "r") as file:
            lineas = [l.strip() for l in file.readlines() if l.strip()]

        if not lineas:
            logging.info(f"Advertencia: Archivo de movimiento vacío: {movimiento_path}")
            return

        logging.info(f"Ejecutando movimiento: {os.path.basename(movimiento_path)}")
        
        for num_linea, linea in enumerate(lineas, 1):
            if stop_execution:
                logging.info("Ejecución interrumpida durante movimiento")
                break

            try:
                datos = json.loads(linea)
                velocidad = datos['velocidad']
                servos = datos['servos']
                
                if len(servos) != 6:
                    logging.info(f"Error en línea {num_linea}: Formato incorrecto")
                    continue

                angulos_objetivo = {i+1: servos[i] for i in range(6)}
                angulos_actuales = brazo.angulos_servos.copy()
                
                tiempo = calcular_tiempo_movimiento(angulos_actuales, angulos_objetivo, velocidad)
                logging.info(f"Moviendo servos a nueva posición")
                
                brazo.mover_servos(angulos_objetivo, velocidad)
                time.sleep(max(tiempo, 0.1))

            except Exception as e:
                logging.info(f"Error en línea {num_linea}: {str(e)}")
                continue

        logging.info("Movimiento finalizado correctamente")
        
    except Exception as e:
        logging.info(f"Error procesando movimiento: {str(e)}")

def iniciar_ejecucion(form_interpreter, color_interpreter, form_labels, color_labels, cap, banda, brazo):
    global stop_execution
    stop_execution = False

    logging.info("Iniciando ejecución")

    if not banda or not banda.serial_connection.is_open:
        logging.info("Error: Banda no inicializada")
        return

    try:
        banda.activar()
        logging.info("Banda activada")
        logica = json.load(open(RUTA_LOGICA, "r"))
        contador_vacios = 0
        contador_detecciones = 0
        objeto_en_proceso = False
        ultimo_objeto = None

        while not stop_execution:
            ret, frame = cap.read()
            if not ret:
                logging.info("Error: Fallo de captura de cámara")
                break

            if objeto_en_proceso:
                continue

            resultado = reconocimiento_de_objetos(
                frame, form_interpreter, form_labels, color_interpreter, color_labels
            )

            if resultado == "vacio_vacio":
                contador_vacios += 1
                contador_detecciones = 0
                if contador_vacios % 30 == 0:
                    logging.info("Esperando objeto...")
                time.sleep(0.1)
                continue
            else:
                if resultado == ultimo_objeto:
                    contador_detecciones += 1
                else:
                    contador_detecciones = 1
                    ultimo_objeto = resultado

                if contador_detecciones < UMBRAL_CONSISTENCIA_DETECCION:
                    logging.info(f"Detección preliminar: {resultado}")
                    time.sleep(0.1)
                    continue

                try:
                    forma, color = resultado.split('_')
                    regla = next((r for r in logica if r["shape"] == forma and r["color"] == color), None)
                    
                    if not regla:
                        logging.info(f"Objeto no configurado: {resultado}")
                        contador_detecciones = 0
                        ultimo_objeto = None
                        continue

                    objeto_en_proceso = True
                    logging.info(f"Procesando objeto: forma={forma}, color={color}")
                    banda.desactivar()
                    logging.info("Banda desactivada")

                    ruta_movimiento = os.path.join(RUTA_MOVIMIENTOS, f"{regla['movement']}.txt")
                    if os.path.exists(ruta_movimiento):
                        procesar_movimiento(ruta_movimiento, brazo)
                    else:
                        logging.info(f"Error: Movimiento no existe: {regla['movement']}")

                    # Limpieza post-procesamiento
                    logging.info("Limpiando área de trabajo...")
                    banda.activar()
                    logging.info("Banda activada para limpieza")
                    inicio_limpieza = time.time()
                    
                    while (time.time() - inicio_limpieza) < TIEMPO_LIMPIEZA:
                        ret, _ = cap.read()  # Limpiar buffer de cámara
                        time.sleep(0.1)

                    # Verificación de vacío
                    verificaciones_vacio = 0
                    for _ in range(MUESTRAS_VERIFICACION_VACIO):
                        ret, frame = cap.read()
                        if reconocimiento_de_objetos(frame, form_interpreter, form_labels, color_interpreter, color_labels) == "vacio_vacio":
                            verificaciones_vacio += 1
                        time.sleep(0.2)

                    if verificaciones_vacio < MUESTRAS_VERIFICACION_VACIO:
                        logging.info(f"Advertencia: El objeto podría permanecer en el área ({verificaciones_vacio}/{MUESTRAS_VERIFICACION_VACIO} vacíos)")

                    objeto_en_proceso = False
                    contador_detecciones = 0
                    ultimo_objeto = None
                    time.sleep(TIEMPO_ESPERA_ENTRE_MOVIMIENTOS)

                except ValueError:
                    logging.info(f"Error: Formato inválido en resultado: {resultado}")
                    objeto_en_proceso = False
                except Exception as e:
                    logging.info(f"Error general: {str(e)}")
                    objeto_en_proceso = False

    except Exception as e:
        logging.info(f"Error en ejecución principal: {str(e)}")
    finally:
        banda.desactivar()
        logging.info("Banda desactivada")
        logging.info("Ejecución finalizada")