# -*- coding: utf-8 -*-
import os
import shutil
import zipfile
import threading
import subprocess
import time
import json
import platform
import sys

from flask import Flask, render_template, Response, request, jsonify, send_file
import cv2
from io import BytesIO
import base64
import numpy as np
import serial
import serial.tools.list_ports
import logging

# --- Selección dinámica del backend de inferencia (TensorFlow vs tflite-runtime) ---

IS_WINDOWS = platform.system() == "Windows"
IS_LINUX = platform.system() == "Linux"
TFLITE_BACKEND = None  # Indica qué backend se está usando para TFLite

try:
    if IS_WINDOWS:
        # En Windows se usa TensorFlow completo como backend.
        import tensorflow as tf
        TFLITE_BACKEND = "tensorflow"
    else:
        # En Linux/Raspberry se usa el backend ligero tflite-runtime.
        import tflite_runtime.interpreter as tflite
        TFLITE_BACKEND = "tflite_runtime"
except ImportError:
    # Si falla la detección inicial se intenta TensorFlow como respaldo.
    try:
        import tensorflow as tf
        TFLITE_BACKEND = "tensorflow"
    except ImportError:
        # Si no hay ningún backend disponible se lanza un error claro.
        raise ImportError(
            "No se encontró ni 'tensorflow' ni 'tflite-runtime'. "
            "Debe instalar uno de los dos según el entorno (Windows o Raspberry Pi)."
        )

# --- Funciones de rutas de archivos ---

def resource_path(relative_path):
    """Obtiene la ruta absoluta a un recurso de solo lectura (pensado para empaquetado con PyInstaller)."""
    try:
        base_path = sys._MEIPASS  # Carpeta temporal creada por PyInstaller
    except AttributeError:
        base_path = os.path.abspath(".")  # Modo desarrollo
    return os.path.join(base_path, relative_path)

def app_data_path(filename):
    """Obtiene la ruta a un archivo de datos que el usuario puede leer y escribir (junto al ejecutable/proyecto)."""
    if getattr(sys, 'frozen', False):
        application_path = os.path.dirname(sys.executable)  # Ejecutable empaquetado
    else:
        application_path = os.path.abspath(".")             # Proyecto en desarrollo
    return os.path.join(application_path, filename)

# --- Importación de módulos propios ---

from modulos.banda_transportadora import BandaTransportadora
from modulos.ejecucion import iniciar_ejecucion, detener_ejecucion
from modulos.brazo_robotico import BrazoRobotico
from modulos.reconocimiento import reconocimiento_de_objetos
from modulos.cinematica_directa import forward_kinematics
from modulos.com_modbus import ModbusBridge

# --- Configuración de logging ---

logging.basicConfig(
    filename=app_data_path('ejecucion.log'),
    level=logging.INFO,
    format='%(asctime)s - %(message)s'
)

# --- Utilidades de modelos e IA ---

def cargar_modelo(model_path):
    """Carga un modelo TFLite usando el backend disponible (TensorFlow o tflite-runtime)."""
    if TFLITE_BACKEND == "tensorflow":
        interpreter = tf.lite.Interpreter(model_path=model_path)
    elif TFLITE_BACKEND == "tflite_runtime":
        interpreter = tflite.Interpreter(model_path=model_path)
    else:
        raise RuntimeError("Backend TFLite no ha sido inicializado correctamente.")
    interpreter.allocate_tensors()
    return interpreter

# --- Gestión de cámara ---

def liberar_camara_linux():
    """Libera la cámara /dev/video0 en Linux matando procesos que la estén usando."""
    device = '/dev/video0'
    try:
        procesos = subprocess.check_output(['fuser', device], stderr=subprocess.DEVNULL)
        for pid in procesos.decode().split():
            os.system(f"kill -9 {pid}")
    except subprocess.CalledProcessError:
        pass
    except Exception as e:
        print(f"Error al liberar la cámara: {e}")

def configurar_camara(nombre_camara):
    """Configura la cámara de vídeo; en Linux intenta liberar el dispositivo antes de abrirlo."""
    if platform.system() == 'Linux':
        liberar_camara_linux()
    sources = cv2.videoio_registry.getBackends()
    for source in sources:
        cap = cv2.VideoCapture(source, cv2.CAP_V4L2)
        if cap.isOpened():
            return cap
    camera_index = int(os.environ.get('CAMERA_INDEX', 0))
    cap = cv2.VideoCapture(camera_index)
    return cap

# --- Guardado de datos recientes en config.json ---

def save_latest_fps_data(num_objects, fps):
    """Guarda el número de objetos detectados y los FPS más recientes en config.json."""
    data = None
    config_file = app_data_path(CONFIG_FILE)
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r') as file:
                data = json.load(file)
        except json.JSONDecodeError:
            logging.error("Error al leer config.json, se sobrescribirá el contenido.")
    if data is None:
        data = {}
    data['latest_objects'] = num_objects
    data['latest_fps'] = fps
    with open(config_file, 'w') as file:
        json.dump(data, file, indent=4)

def save_latest_classification(classification):
    """Guarda la última clasificación obtenida en config.json."""
    data = None
    config_file = app_data_path(CONFIG_FILE)
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r') as file:
                data = json.load(file)
        except json.JSONDecodeError:
            logging.error("Error al leer config.json, se sobrescribirá el contenido.")
    if data is None:
        data = {}
    data['latest_classification'] = classification
    with open(config_file, 'w') as file:
        json.dump(data, file, indent=4)

def save_latest_circle_data(num_circles, area):
    """Guarda el número de círculos detectados y el área total en config.json."""
    data = None
    config_file = app_data_path(CONFIG_FILE)
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r') as file:
                data = json.load(file)
        except json.JSONDecodeError:
            logging.error("Error al leer config.json, se sobrescribirá el contenido.")
    if data is None:
        data = {}
    data['latest_circles'] = num_circles
    data['latest_area'] = area
    with open(config_file, 'w') as file:
        json.dump(data, file, indent=4)

def save_latest_position_data(position_data):
    """Guarda información relacionada con la posición o parámetros del robot en config.json."""
    data = None
    config_file = app_data_path(CONFIG_FILE)
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r') as file:
                data = json.load(file)
        except json.JSONDecodeError:
            logging.error("Error al leer config.json, se sobrescribirá el contenido.")
    if data is None:
        data = {}
    data['latest_position'] = position_data
    with open(config_file, 'w') as file:
        json.dump(data, file, indent=4)

# --- IP del servidor (loopback / Ethernet / WiFi) ---

def get_interface_ip(ifname):
    """Obtiene la IP v4 de una interfaz (eth0, wlan0, etc.) en Linux."""
    if platform.system() != "Linux":
        return None
    try:
        output = subprocess.check_output(
            ["ip", "-4", "addr", "show", ifname],
            stderr=subprocess.DEVNULL,
            text=True
        )
    except subprocess.CalledProcessError:
        return None
    for line in output.splitlines():
        line = line.strip()
        if line.startswith("inet "):
            return line.split()[1].split("/")[0]
    return None

def get_server_addresses(port):
    """Construye un diccionario con las direcciones del servidor en loopback, Ethernet y WiFi."""
    ethernet_ip = get_interface_ip("eth0")
    wifi_ip = get_interface_ip("wlan0")
    return {
        "loopback": f"127.0.0.1:{port}",
        "ethernet": f"{ethernet_ip}:{port}" if ethernet_ip else None,
        "wifi": f"{wifi_ip}:{port}" if wifi_ip else None,
    }

def print_server_addresses(port):
    """Muestra en consola las direcciones donde está escuchando el servidor."""
    addrs = get_server_addresses(port)
    print(f"Servidor web en loopback: http://{addrs['loopback']}")
    if addrs["ethernet"]:
        print(f"Servidor web en Ethernet (eth0): http://{addrs['ethernet']}")
    else:
        print("Ethernet (eth0) sin IP o desconectado.")
    if addrs["wifi"]:
        print(f"Servidor web en WiFi (wlan0): http://{addrs['wifi']}")
    else:
        print("WiFi (wlan0) sin IP o desconectado.")

# --- Inicialización de Flask y configuración global ---

app = Flask(__name__, template_folder='templates')
app.secret_key = 'your_secret_key'
CONFIG_FILE = "config.json"

app.config["TOTAL_OBJECTS_FOUND"] = 0
app.config["TOTAL_CIRCLES_FOUND"] = 0
app.config["LAST_CLASSIFICATION"] = ""
app.config["FPS"] = 0
app.config["FRAME"] = None
app.config["FRAME_CIRCLE"] = None
app.config["SERIAL_PORT"] = None
app.config["MODBUS_BRIDGE"] = None
app.config["COLOR_MODEL"] = None
app.config["SHAPE_MODEL"] = None
app.config["ROBOTIC_ARM"] = None
app.config["BAND_CONVEYOR"] = None
app.config["MAX_OBJECT_DISTANCE"] = 100
app.config["MAX_VEL"] = [0, 0, 0]
app.config["ROBOT_MODEL"] = "simple_robot"
app.config["MODBUS_IP"] = "127.0.0.1"
app.config["MODBUS_PORT"] = 502
app.config["FRAME_WIDTH"] = 640
app.config["FRAME_HEIGHT"] = 480

# --- Inicialización de modelos y hardware ---

def initialize_models():
    """
    Inicializa los modelos de color y forma desde la carpeta uploads.
    Se asume:
    - uploads/model_color/model_unquant.tflite
    - uploads/model_form/model_unquant.tflite
    """
    base_dir = os.path.dirname(os.path.abspath(__file__))
    color_model_path = os.path.join(base_dir, "uploads", "model_color", "model_unquant.tflite")
    shape_model_path = os.path.join(base_dir, "uploads", "model_form", "model_unquant.tflite")
    if os.path.exists(color_model_path):
        app.config["COLOR_MODEL"] = cargar_modelo(color_model_path)
        logging.info(f"Modelo de color cargado desde {color_model_path}")
    else:
        logging.error(f"Modelo de color no encontrado en {color_model_path}")
    if os.path.exists(shape_model_path):
        app.config["SHAPE_MODEL"] = cargar_modelo(shape_model_path)
        logging.info(f"Modelo de forma cargado desde {shape_model_path}")
    else:
        logging.error(f"Modelo de forma no encontrado en {shape_model_path}")

def initialize_robotic_arm():
    """Inicializa el objeto que representa el brazo robótico."""
    app.config["ROBOTIC_ARM"] = BrazoRobotico()

def initialize_band_conveyor():
    """Inicializa el objeto que representa la banda transportadora."""
    app.config["BAND_CONVEYOR"] = BandaTransportadora()

def initialize_modbus_bridge():
    """Inicializa el puente Modbus TCP con la IP y puerto configurados."""
    ip = app.config["MODBUS_IP"]
    port = app.config["MODBUS_PORT"]
    app.config["MODBUS_BRIDGE"] = ModbusBridge(ip, port)

def initialize_system():
    """Inicializa modelos, brazo robótico, banda y comunicación Modbus."""
    initialize_models()
    initialize_robotic_arm()
    initialize_band_conveyor()
    initialize_modbus_bridge()

# --- Rutas de páginas (HTML) ---

@app.route('/')
def index():
    """Renderiza la página principal de la interfaz web."""
    return render_template('index.html')

@app.route('/opciones')
def opciones():
    """Muestra el menú principal de opciones."""
    return render_template('opciones.html')

@app.route('/entrenar')
def entrenar():
    """Muestra el menú de entrenamiento (toma de imágenes y subida de modelos)."""
    return render_template('entrenar.html')

@app.route('/configurar_movimientos')
def configurar_movimientos():
    """Muestra la página para configurar movimientos del brazo."""
    return render_template('configurar_movimientos.html')

@app.route('/configurar_movimientos_CI')
def configurar_movimientos_CI():
    """Muestra la página para configurar movimientos con cinemática inversa."""
    return render_template('configurar_movimientos_CI.html')

@app.route('/configurar_logica')
def configurar_logica():
    """Muestra la página para configurar la lógica de reglas."""
    return render_template('configurar_logica.html')

@app.route('/tomar_imagen')
def tomar_imagen():
    """Muestra la página para capturar imágenes de entrenamiento."""
    return render_template('tomar_imagen.html')

@app.route('/subir_modelo')
def subir_modelo():
    """Muestra la página para subir modelos entrenados."""
    return render_template('subir_modelo.html')

@app.route('/verificar_reconocimiento')
def verificar_reconocimiento():
    """Muestra la página para verificar el reconocimiento."""
    return render_template('verificar_reconocimiento.html')

# --- Vídeo y detección ---

@app.route('/video_feed')
def video_feed():
    """Devuelve un stream MJPEG con el vídeo de la cámara y los FPS."""
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/camera_feed')
def camera_feed():
    """Alias de vídeo para la página de toma de imágenes."""
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

def generate_frames():
    """Genera frames de la cámara, calcula FPS y los envía como stream MJPEG."""
    cap = configurar_camara("default")
    if not cap or not cap.isOpened():
        logging.error("No se pudo abrir la cámara.")
        return
    prev_time = time.time()
    frame_count = 0
    while True:
        success, frame = cap.read()
        if not success:
            break
        frame_count += 1
        current_time = time.time()
        elapsed_time = current_time - prev_time
        fps = frame_count / elapsed_time if elapsed_time > 0 else 0
        app.config["FPS"] = fps
        _, buffer = cv2.imencode('.jpg', frame)
        frame_bytes = buffer.tobytes()
        app.config["FRAME"] = frame_bytes
        save_latest_fps_data(app.config["TOTAL_OBJECTS_FOUND"], fps)
        frame_with_fps = frame.copy()
        cv2.putText(
            frame_with_fps,
            f"FPS: {fps:.2f}",
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (0, 255, 0),
            2
        )
        ret, buffer = cv2.imencode('.jpg', frame_with_fps)
        if not ret:
            continue
        frame_with_fps_bytes = buffer.tobytes()
        yield (
            b'--frame\r\n'
            b'Content-Type: image/jpeg\r\n\r\n' + frame_with_fps_bytes + b'\r\n'
        )
    cap.release()

@app.route('/start_detection', methods=['POST'])
def start_detection():
    """Inicia un hilo de detección de objetos o círculos según el tipo elegido."""
    detection_type = request.form.get('detection_type', 'objects')
    cap = configurar_camara("default")
    if not cap or not cap.isOpened():
        return jsonify({"success": False, "message": "No se pudo abrir la cámara"}), 500
    if detection_type == 'objects':
        detection_thread = threading.Thread(target=detection_loop, args=(cap,))
        detection_thread.start()
        return jsonify({"success": True, "message": "Detección de objetos iniciada"})
    elif detection_type == 'circles':
        detection_thread = threading.Thread(target=circle_detection_loop, args=(cap,))
        detection_thread.start()
        return jsonify({"success": True, "message": "Detección de círculos iniciada"})
    else:
        return jsonify({"success": False, "message": "Tipo de detección inválido"}), 400

def detection_loop(cap):
    """Bucle de detección de objetos que actualiza conteo y clasificación."""
    while True:
        success, frame = cap.read()
        if not success:
            break
        num_objects, classification = reconocimiento_de_objetos(
            frame,
            app.config["COLOR_MODEL"],
            app.config["SHAPE_MODEL"],
            app.config["ROBOTIC_ARM"]
        )
        app.config["TOTAL_OBJECTS_FOUND"] = num_objects
        app.config["LAST_CLASSIFICATION"] = classification
        save_latest_classification(classification)
        _, buffer = cv2.imencode('.jpg', frame)
        app.config["FRAME"] = buffer.tobytes()
        time.sleep(0.03)
    cap.release()

def circle_detection_loop(cap):
    """Bucle de detección de círculos usando transformada de Hough."""
    while True:
        success, frame = cap.read()
        if not success:
            break
        frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        frame_gray = cv2.medianBlur(frame_gray, 5)
        circles = cv2.HoughCircles(
            frame_gray,
            cv2.HOUGH_GRADIENT,
            dp=1.2,
            minDist=50,
            param1=50,
            param2=30,
            minRadius=10,
            maxRadius=100
        )
        num_circles = 0
        total_area = 0
        if circles is not None:
            circles = np.round(circles[0, :]).astype("int")
            num_circles = len(circles)
            for (x, y, r) in circles:
                total_area += np.pi * (r ** 2)
                cv2.circle(frame, (x, y), r, (0, 255, 0), 4)
                cv2.rectangle(frame, (x - 5, y - 5), (x + 5, y + 5), (0, 128, 255), -1)
        app.config["TOTAL_CIRCLES_FOUND"] = num_circles
        save_latest_circle_data(num_circles, total_area)
        _, buffer = cv2.imencode('.jpg', frame)
        app.config["FRAME_CIRCLE"] = buffer.tobytes()
        time.sleep(0.03)
    cap.release()

# --- Endpoints JSON de datos recientes ---

@app.route('/get_latest_fps_data')
def get_latest_fps_data():
    """Devuelve los últimos FPS y conteo de objetos guardados en config.json."""
    config_file = app_data_path(CONFIG_FILE)
    if not os.path.exists(config_file):
        return jsonify({"latest_objects": 0, "latest_fps": 0})
    with open(config_file, 'r') as file:
        data = json.load(file)
    latest_objects = data.get('latest_objects', 0)
    latest_fps = data.get('latest_fps', 0)
    return jsonify({"latest_objects": latest_objects, "latest_fps": latest_fps})

@app.route('/get_latest_classification')
def get_latest_classification():
    """Devuelve la última clasificación guardada."""
    config_file = app_data_path(CONFIG_FILE)
    if not os.path.exists(config_file):
        return jsonify({"latest_classification": ""})
    with open(config_file, 'r') as file:
        data = json.load(file)
    latest_classification = data.get('latest_classification', "")
    return jsonify({"latest_classification": latest_classification})

@app.route('/get_latest_circle_data')
def get_latest_circle_data():
    """Devuelve el último conteo de círculos y área total guardados."""
    config_file = app_data_path(CONFIG_FILE)
    if not os.path.exists(config_file):
        return jsonify({"latest_circles": 0, "latest_area": 0})
    with open(config_file, 'r') as file:
        data = json.load(file)
    latest_circles = data.get('latest_circles', 0)
    latest_area = data.get('latest_area', 0)
    return jsonify({"latest_circles": latest_circles, "latest_area": latest_area})

@app.route('/get_latest_position_data')
def get_latest_position_data():
    """Devuelve la última información de posición/parámetros guardada."""
    config_file = app_data_path(CONFIG_FILE)
    if not os.path.exists(config_file):
        return jsonify({"latest_position": {}})
    with open(config_file, 'r') as file:
        data = json.load(file)
    latest_position = data.get('latest_position', {})
    return jsonify({"latest_position": latest_position})

# --- Modbus TCP ---

@app.route('/start_modbus', methods=['POST'])
def start_modbus():
    """Inicializa la conexión Modbus TCP."""
    initialize_modbus_bridge()
    return jsonify({"success": True, "message": "Conexión Modbus inicializada"})

@app.route('/stop_modbus', methods=['POST'])
def stop_modbus():
    """Cierra la conexión Modbus TCP si está activa."""
    modbus_bridge = app.config["MODBUS_BRIDGE"]
    if modbus_bridge:
        modbus_bridge.close()
        app.config["MODBUS_BRIDGE"] = None
        return jsonify({"success": True, "message": "Conexión Modbus cerrada"})
    else:
        return jsonify({"success": False, "message": "Conexión Modbus no está activa"}), 400

@app.route('/send_modbus_command', methods=['POST'])
def send_modbus_command():
    """Envía un comando sencillo de escritura a un registro Modbus."""
    modbus_bridge = app.config["MODBUS_BRIDGE"]
    if not modbus_bridge:
        return jsonify({"success": False, "message": "Conexión Modbus no inicializada"}), 400
    data = request.get_json()
    slave_id = data.get("slave_id", 1)
    address = data.get("address", 0)
    value = data.get("value", 0)
    try:
        modbus_bridge.write_single_register(slave_id, address, value)
        return jsonify({"success": True, "message": f"Escrito valor {value} en dirección {address}"}), 200
    except Exception as e:
        logging.error(f"Error al escribir en Modbus: {e}")
        return jsonify({"success": False, "message": "Error al escribir en Modbus"}), 500

# --- Serial ---

@app.route('/get_serial_ports')
def get_serial_ports():
    """Lista los puertos serie disponibles."""
    ports = serial.tools.list_ports.comports()
    port_list = [port.device for port in ports]
    return jsonify({"ports": port_list})

@app.route('/connect_serial', methods=['POST'])
def connect_serial():
    """Abre un puerto serie con la velocidad indicada."""
    port = request.form.get('port')
    baudrate = int(request.form.get('baudrate', 9600))
    try:
        ser = serial.Serial(port, baudrate, timeout=1)
        app.config["SERIAL_PORT"] = ser
        return jsonify({"success": True, "message": f"Conectado al puerto {port}"})
    except Exception as e:
        logging.error(f"Error al conectar al puerto serie: {e}")
        return jsonify({"success": False, "message": "Error al conectar al puerto serie"}), 500

@app.route('/disconnect_serial', methods=['POST'])
def disconnect_serial():
    """Cierra el puerto serie si está abierto."""
    ser = app.config["SERIAL_PORT"]
    if ser and ser.is_open:
        ser.close()
        app.config["SERIAL_PORT"] = None
        return jsonify({"success": True, "message": "Puerto serie desconectado"})
    else:
        return jsonify({"success": False, "message": "No hay puerto serie conectado"}), 400

@app.route('/send_serial', methods=['POST'])
def send_serial():
    """Envía datos por el puerto serie conectado."""
    ser = app.config["SERIAL_PORT"]
    if not ser or not ser.is_open:
        return jsonify({"success": False, "message": "Puerto serie no está conectado"}), 400
    data = request.form.get('data', '')
    try:
        ser.write(data.encode())
        ser.flush()
        return jsonify({"success": True, "message": f"Enviado: {data}"})
    except Exception as e:
        logging.error(f"Error al enviar datos por el puerto serie: {e}")
        return jsonify({"success": False, "message": "Error al enviar datos por el puerto serie"}), 500

@app.route('/status_connection')
def status_connection():
    """Devuelve el estado actual de la conexión serie para la interfaz web."""
    ser = app.config.get("SERIAL_PORT")
    if ser and ser.is_open:
        return jsonify({"connected": True, "port": ser.port})
    return jsonify({"connected": False, "port": None})

# --- Archivos y capturas ---

@app.route('/open_folder', methods=['POST'])
def open_folder():
    """Abre la carpeta de capturas en el explorador del sistema."""
    folder_path = app_data_path("capturas")
    os.makedirs(folder_path, exist_ok=True)
    if platform.system() == 'Windows':
        os.startfile(folder_path)
    elif platform.system() == 'Darwin':
        subprocess.call(['open', folder_path])
    else:
        subprocess.call(['xdg-open', folder_path])
    return jsonify({"success": True, "message": "Carpeta de capturas abierta"})

@app.route('/download_last_image')
def download_last_image():
    """Descarga la última imagen capturada desde el stream de vídeo."""
    frame = app.config.get("FRAME")
    if frame is None:
        return jsonify({"success": False, "message": "No hay imagen disponible"}), 404
    img = cv2.imdecode(np.frombuffer(frame, dtype=np.uint8), cv2.IMREAD_COLOR)
    _, buffer = cv2.imencode('.jpg', img)
    return send_file(
        BytesIO(buffer),
        mimetype='image/jpeg',
        as_attachment=True,
        download_name='ultima_captura.jpg'
    )

@app.route('/save_frame', methods=['POST'])
def save_frame():
    """Guarda el frame actual del vídeo en la carpeta de capturas."""
    frame = app.config.get("FRAME")
    if frame is None:
        return jsonify({"success": False, "message": "No hay frame disponible"}), 404
    capture_folder = app_data_path("capturas")
    os.makedirs(capture_folder, exist_ok=True)
    img = cv2.imdecode(np.frombuffer(frame, dtype=np.uint8), cv2.IMREAD_COLOR)
    filename = f"captura_{int(time.time())}.jpg"
    img_path = os.path.join(capture_folder, filename)
    cv2.imwrite(img_path, img)
    return jsonify({"success": True, "message": f"Captura guardada como {filename}"})

@app.route('/download_log')
def download_log():
    """Permite descargar el archivo de log de ejecución."""
    log_file_path = app_data_path('ejecucion.log')
    if os.path.exists(log_file_path):
        return send_file(log_file_path, as_attachment=True)
    else:
        return jsonify({"success": False, "message": "No hay archivo de log disponible"}), 404

@app.route('/compress_and_download')
def compress_and_download():
    """Crea un ZIP con la última captura y el log, y lo ofrece para descarga."""
    capture_folder = app_data_path("capturas")
    log_file_path = app_data_path('ejecucion.log')
    cap = configurar_camara("default")
    if not os.path.exists(capture_folder):
        os.makedirs(capture_folder)
    _, buffer = cap.read()
    img_path = os.path.join(capture_folder, "ultima_captura.jpg")
    cv2.imwrite(img_path, buffer)
    zip_file_path = app_data_path('capturas_y_log.zip')
    with zipfile.ZipFile(zip_file_path, 'w') as zipf:
        if os.path.exists(img_path):
            zipf.write(img_path, os.path.basename(img_path))
        if os.path.exists(log_file_path):
            zipf.write(log_file_path, os.path.basename(log_file_path))
    return send_file(zip_file_path, as_attachment=True)

# --- Configuración general y reportes ---

@app.route('/get_config')
def get_config():
    """Devuelve el contenido completo de config.json."""
    config_file = app_data_path(CONFIG_FILE)
    if not os.path.exists(config_file):
        return jsonify({"error": "Configuración no encontrada"})
    with open(config_file, 'r') as file:
        data = json.load(file)
    return jsonify(data)

@app.route('/update_config', methods=['POST'])
def update_config():
    """Sobrescribe config.json con los datos enviados."""
    data = request.get_json()
    config_file = app_data_path(CONFIG_FILE)
    with open(config_file, 'w') as file:
        json.dump(data, file, indent=4)
    return jsonify({"success": True, "message": "Configuración actualizada"})

@app.route('/reset_config', methods=['POST'])
def reset_config():
    """Restaura valores predeterminados en config.json y en app.config."""
    default_config = {
        "TOTAL_OBJECTS_FOUND": 0,
        "TOTAL_CIRCLES_FOUND": 0,
        "LAST_CLASSIFICATION": "",
        "FPS": 0,
        "MAX_OBJECT_DISTANCE": 100,
        "MAX_VEL": [0, 0, 0],
        "ROBOT_MODEL": "simple_robot",
        "MODBUS_IP": "127.0.0.1",
        "MODBUS_PORT": 502,
        "FRAME_WIDTH": 640,
        "FRAME_HEIGHT": 480
    }
    config_file = app_data_path(CONFIG_FILE)
    with open(config_file, 'w') as file:
        json.dump(default_config, file, indent=4)
    app.config.update(default_config)
    return jsonify({"success": True, "message": "Configuración restablecida a los valores predeterminados"})

@app.route('/set_max_object_distance', methods=['POST'])
def set_max_object_distance():
    """Actualiza la distancia máxima de objeto configurada."""
    max_distance = request.form.get('max_distance', type=int)
    app.config["MAX_OBJECT_DISTANCE"] = max_distance
    save_latest_position_data({"max_object_distance": max_distance})
    return jsonify({"success": True, "message": f"Distancia máxima de objeto establecida en {max_distance}"})

@app.route('/set_max_velocities', methods=['POST'])
def set_max_velocities():
    """Actualiza las velocidades máximas configuradas para el robot."""
    max_vel_x = request.form.get('max_vel_x', type=float)
    max_vel_y = request.form.get('max_vel_y', type=float)
    max_vel_z = request.form.get('max_vel_z', type=float)
    app.config["MAX_VEL"] = [max_vel_x, max_vel_y, max_vel_z]
    save_latest_position_data({"max_velocities": [max_vel_x, max_vel_y, max_vel_z]})
    return jsonify({"success": True, "message": f"Velocidades máximas establecidas en {max_vel_x}, {max_vel_y}, {max_vel_z}"})

@app.route('/update_robot_model', methods=['POST'])
def update_robot_model():
    """Actualiza el nombre del modelo de robot usado en la configuración."""
    robot_model = request.form.get('robot_model')
    app.config["ROBOT_MODEL"] = robot_model
    save_latest_position_data({"robot_model": robot_model})
    return jsonify({"success": True, "message": f"Modelo de robot actualizado a {robot_model}"})

@app.route('/update_modbus_config', methods=['POST'])
def update_modbus_config():
    """Actualiza la IP y el puerto Modbus usados por el sistema."""
    ip = request.form.get('ip')
    port = request.form.get('port', type=int)
    app.config["MODBUS_IP"] = ip
    app.config["MODBUS_PORT"] = port
    save_latest_position_data({"modbus_ip": ip, "modbus_port": port})
    return jsonify({"success": True, "message": f"Configuración Modbus actualizada a {ip}:{port}"})

@app.route('/generate_report')
def generate_report():
    """Genera un informe JSON con información resumida de la ejecución."""
    config_file = app_data_path(CONFIG_FILE)
    if not os.path.exists(config_file):
        return jsonify({"success": False, "message": "No hay datos disponibles"}), 404
    with open(config_file, 'r') as file:
        data = json.load(file)
    report = {
        "total_objects_found": data.get('latest_objects', 0),
        "total_circles_found": data.get('latest_circles', 0),
        "last_classification": data.get('latest_classification', ""),
        "max_object_distance": data.get('latest_position', {}).get('max_object_distance', app.config["MAX_OBJECT_DISTANCE"]),
        "max_velocities": data.get('latest_position', {}).get('max_velocities', app.config["MAX_VEL"]),
        "robot_model": data.get('latest_position', {}).get('robot_model', app.config["ROBOT_MODEL"]),
        "modbus_ip": data.get('latest_position', {}).get('modbus_ip', app.config["MODBUS_IP"]),
        "modbus_port": data.get('latest_position', {}).get('modbus_port', app.config["MODBUS_PORT"])
    }
    report_file_path = app_data_path('informe.json')
    with open(report_file_path, 'w') as report_file:
        json.dump(report, report_file, indent=4)
    return send_file(report_file_path, as_attachment=True)

@app.route('/backup_project', methods=['POST'])
def backup_project():
    """Crea un archivo ZIP con una copia de seguridad del proyecto."""
    backup_folder = app_data_path("backups")
    os.makedirs(backup_folder, exist_ok=True)
    backup_file_path = os.path.join(backup_folder, f"backup_{int(time.time())}.zip")
    with zipfile.ZipFile(backup_file_path, 'w') as backup_zip:
        for foldername, subfolders, filenames in os.walk(app_data_path(".")):
            for filename in filenames:
                file_path = os.path.join(foldername, filename)
                if "backups" not in file_path and not filename.endswith(".zip"):
                    backup_zip.write(file_path, os.path.relpath(file_path, app_data_path(".")))
    return jsonify({"success": True, "message": "Backup creado correctamente", "backup_file": backup_file_path})

@app.route('/restore_project', methods=['POST'])
def restore_project():
    """Restaura un backup del proyecto desde un archivo ZIP subido."""
    backup_file = request.files.get('backup_file')
    if backup_file is None:
        return jsonify({"success": False, "message": "No se ha proporcionado un archivo de backup"}), 400
    backup_folder = app_data_path("backups")
    os.makedirs(backup_folder, exist_ok=True)
    backup_file_path = os.path.join(backup_folder, backup_file.filename)
    backup_file.save(backup_file_path)
    with zipfile.ZipFile(backup_file_path, 'r') as backup_zip:
        backup_zip.extractall(app_data_path("."))
    return jsonify({"success": True, "message": "Backup restaurado correctamente"})

# --- Seguimiento de clientes conectados ---

connected_clients = {}

@app.before_request
def track_clients():
    """Registra la IP del cliente y la última vez que se vio activa."""
    client_ip = request.remote_addr
    connected_clients[client_ip] = time.time()

@app.route("/get_connected_clients")
def get_connected_clients():
    """Devuelve una lista de IPs de clientes activos en el último minuto."""
    active_threshold = time.time() - 60
    active_clients = [ip for ip, last_seen in connected_clients.items() if last_seen > active_threshold]
    return jsonify({"clients": active_clients})

@app.route("/server_info")
def server_info():
    """Devuelve en JSON las IP y puertos del servidor en loopback, Ethernet y WiFi."""
    port = app.config.get("SERVER_PORT", 5000)
    return jsonify(get_server_addresses(port))

# --- Ejecución principal ---

if __name__ == '__main__':
    """Punto de entrada principal: inicializa el sistema y levanta el servidor Flask."""
    port = 5000
    app.config["SERVER_PORT"] = port
    initialize_system()
    print_server_addresses(port)
    app.run(host='0.0.0.0', port=port, debug=True)