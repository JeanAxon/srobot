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
import tensorflow as tf
import numpy as np
import serial
import serial.tools.list_ports
import logging

# --- FUNCIONES CRÍTICAS PARA RUTAS DE ARCHIVOS ---

def resource_path(relative_path):
    """ Obtiene la ruta absoluta a un recurso de SOLO LECTURA que se empaqueta con la app. """
    try:
        # PyInstaller crea una carpeta temporal y guarda la ruta en _MEIPASS
        base_path = sys._MEIPASS
    except AttributeError:
        # _MEIPASS no existe, estamos en modo desarrollo
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def app_data_path(filename):
    """ Obtiene la ruta a un archivo de datos que el usuario puede LEER y ESCRIBIR. Se guarda junto al .exe. """
    if getattr(sys, 'frozen', False):
        # Estamos ejecutando como un .exe empaquetado
        application_path = os.path.dirname(sys.executable)
    else:
        # Estamos ejecutando en modo desarrollo
        application_path = os.path.abspath(".")
    return os.path.join(application_path, filename)

# --- FIN DE FUNCIONES DE RUTAS ---

from modulos.banda_transportadora import BandaTransportadora
from modulos.ejecucion import iniciar_ejecucion, detener_ejecucion
from modulos.brazo_robotico import BrazoRobotico
from modulos.reconocimiento import reconocimiento_de_objetos
from modulos.cinematica_directa import forward_kinematics
from modulos.com_modbusTCP import ModbusBridge

logging.basicConfig(filename=app_data_path('ejecucion.log'), level=logging.INFO, format='%(asctime)s - %(message)s')

def cargar_modelo(model_path):
    interpreter = tf.lite.Interpreter(model_path=model_path)
    interpreter.allocate_tensors()
    return interpreter

def liberar_camara_linux():
    device = '/dev/video0'
    try:
        procesos = subprocess.check_output(['fuser', device], stderr=subprocess.DEVNULL)
        for pid in procesos.decode().split():
            os.system(f"kill -9 {pid}")
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    except Exception as e:
        print(f"Error al liberar cámara: {e}")

def inicializar_camara():
    if platform.system() == "Linux":
        if not os.environ.get('FLASK_DEBUG'):
            liberar_camara_linux()
        for device in ["/dev/video0", "/dev/video1", 0, 1]:
            cap = cv2.VideoCapture(device)
            if cap.isOpened():
                print(f"✅ Cámara Linux inicializada en {device}")
                os.system(f"v4l2-ctl -d {device} -c focus_automatic_continuous=0")
                os.system(f"v4l2-ctl -d {device} -c focus_absolute=100")
                return cap
    else:
        for i in range(5, -1, -1):
            cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
            if cap.isOpened():
                print(f"✅ Cámara Windows inicializada en el índice {i}")
                return cap
    raise Exception("❌ No se pudo inicializar ninguna cámara.")

cap = None
try:
    cap = inicializar_camara()
except Exception as e:
    print(e)

app = Flask(__name__, template_folder=resource_path('templates'), static_folder=resource_path('static'))

# --- REGISTRO DE CLIENTES CONECTADOS ---
# Usamos un diccionario para no tener IPs duplicadas y guardar la última vez que se vieron.
connected_clients = {}

@app.before_request
def track_clients():
    # Obtenemos la IP del cliente. request.remote_addr es la forma estándar.
    client_ip = request.remote_addr
    # Actualizamos el timestamp para este cliente.
    connected_clients[client_ip] = time.time()

@app.route("/get_connected_clients")
def get_connected_clients():
    """Un nuevo endpoint para que la GUI pida la lista de clientes."""
    # Filtramos clientes que no se han visto en los últimos 60 segundos.
    active_threshold = time.time() - 60
    active_clients = [ip for ip, last_seen in connected_clients.items() if last_seen > active_threshold]
    return jsonify(clients=active_clients)
# --- FIN DE REGISTRO DE CLIENTES ---

serial_connection, banda, brazo = None, BandaTransportadora(), BrazoRobotico()
modbus_bridge = ModbusBridge()
modbus_bridge.start()
form_interpreter, color_interpreter, form_labels, color_labels = None, None, [], []

try:
    form_model_path = resource_path('uploads/model_form/model_unquant.tflite')
    color_model_path = resource_path('uploads/model_color/model_unquant.tflite')
    form_labels_path = resource_path('uploads/model_form/labels.txt')
    color_labels_path = resource_path('uploads/model_color/labels.txt')
    if os.path.exists(form_model_path) and os.path.exists(form_labels_path):
        with open(form_labels_path, 'r', encoding='utf-8') as f: form_labels = f.read().splitlines()
        form_interpreter = cargar_modelo(form_model_path)
        print("✅ Modelo de formas cargado.")
    if os.path.exists(color_model_path) and os.path.exists(color_labels_path):
        with open(color_labels_path, 'r', encoding='utf-8') as f: color_labels = f.read().splitlines()
        color_interpreter = cargar_modelo(color_model_path)
        print("✅ Modelo de colores cargado.")
except Exception as e:
    print(f"❌ Error al cargar modelos: {e}")

@app.route("/")
def index(): return render_template("index.html")

@app.route("/opciones")
def opciones():
    logic_config_path = app_data_path("logica_config.json")
    logic_config = []
    if os.path.exists(logic_config_path):
        with open(logic_config_path, "r", encoding='utf-8') as file:
            try: logic_config = json.load(file)
            except: logic_config = []
    return render_template("opciones.html", form_labels=form_labels, color_labels=color_labels, model_loaded=(form_interpreter and color_interpreter), logic_config=logic_config)

@app.route("/listar_puertos")
def listar_puertos(): return jsonify([p.device for p in serial.tools.list_ports.comports()])

@app.route("/conectar_serial/<path:puerto>", methods=["POST"])
def conectar_serial(puerto):
    global serial_connection
    if serial_connection and serial_connection.is_open: serial_connection.close()
    try:
        serial_connection = serial.Serial(port=puerto, baudrate=9600, timeout=1)
        time.sleep(2)
        if serial_connection.is_open:
            banda.set_connection(serial_connection); brazo.set_connection(serial_connection)
            posicion_segura = {"velocidad": 0, "servos": [90, 90, 90, 90, 90, 90]}
            serial_connection.write((json.dumps(posicion_segura) + "\n").encode())
            return f"Conectado a {puerto}"
        raise serial.SerialException("No se pudo abrir el puerto.")
    except Exception as e: return f"Error al conectar: {e}", 500

@app.route("/control_banda/<accion>", methods=["POST"])
def control_banda(accion):
    if not (serial_connection and serial_connection.is_open): return "No hay conexion", 400
    actions = {"activar": banda.activar, "desactivar": banda.desactivar, "derecha": banda.direccion_derecha, "izquierda": banda.direccion_izquierda}
    if accion in actions:
        actions[accion](); return f"Banda {accion}"
    return "Accion no reconocida", 400

@app.route("/tomar_imagen")
def tomar_imagen(): return render_template("tomar_imagen.html")
@app.route("/entrenar")
def entrenar(): return render_template("entrenar.html")
@app.route("/subir_modelo")
def subir_modelo(): return render_template("subir_modelo.html")

@app.route("/upload_model", methods=["POST"])
def upload_model():
    return jsonify({'message': 'Subir modelos no soportado en .exe. Recompile la app.'}), 400

def gen_frames():
    global cap
    while True:
        frame = None
        if not (cap and cap.isOpened()):
            frame = np.zeros((480, 640, 3), dtype=np.uint8); cv2.putText(frame, "CAMARA NO DETECTADA", (50, 240), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 0, 255), 3)
        else:
            success, frame = cap.read()
            if not success: time.sleep(0.5); continue
            if form_interpreter and color_interpreter:
                try:
                    resultado = reconocimiento_de_objetos(frame, form_interpreter, form_labels, color_interpreter, color_labels)
                    cv2.putText(frame, resultado if resultado != "vacio" else "Sin deteccion", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                except Exception as e: cv2.putText(frame, "Error en prediccion", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
            else: cv2.putText(frame, "Modelos no cargados", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
        if frame is not None:
            ret, buffer = cv2.imencode('.jpg', frame); yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')

def gen_raw_frames():
    global cap
    while True:
        if not (cap and cap.isOpened()):
            frame = np.zeros((480, 640, 3), dtype=np.uint8); cv2.putText(frame, "CAMARA NO DETECTADA", (50, 240), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 0, 255), 3)
        else:
            success, frame = cap.read()
            if not success: time.sleep(0.5); continue
        ret, buffer = cv2.imencode('.jpg', frame); yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')

@app.route("/camera_feed")
def camera_feed(): return Response(gen_raw_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')
@app.route("/video_feed")
def video_feed(): return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route("/guardar_imagenes", methods=["POST"])
def guardar_imagenes():
    data = request.get_json(); folder_path = app_data_path(os.path.join("uploads", data['folder_name'])); os.makedirs(folder_path, exist_ok=True)
    for i, photo in enumerate(data['photos']):
        with open(os.path.join(folder_path, f"{data['folder_name']}_{i+1}.jpg"), "wb") as f: f.write(base64.b64decode(photo.split(',')[1]))
    return "Fotos guardadas."

@app.route("/obtener_carpetas")
def obtener_carpetas():
    folder_path = app_data_path('uploads'); os.makedirs(folder_path, exist_ok=True)
    return jsonify([f for f in os.listdir(folder_path) if os.path.isdir(os.path.join(folder_path, f)) and f not in ['model_color', 'model_form']])

@app.route("/descargar/<folder_name>")
def descargar(folder_name):
    folder_path = app_data_path(os.path.join("uploads", folder_name))
    if not os.path.exists(folder_path): return "Carpeta no existe", 404
    zip_path = app_data_path(f"{folder_name}.zip")
    with zipfile.ZipFile(zip_path, 'w') as zf:
        for root, _, files in os.walk(folder_path):
            for file in files: zf.write(os.path.join(root, file), os.path.relpath(os.path.join(root, file), folder_path))
    return send_file(zip_path, as_attachment=True, download_name=f"{folder_name}.zip")

@app.route("/verificar_reconocimiento")
def verificar_reconocimiento():
    if not (form_interpreter and color_interpreter): return "Modelo no cargado", 400
    return render_template("verificar_reconocimiento.html", labels=form_labels + color_labels)

@app.route("/configurar_movimientos")
def configurar_movimientos(): return render_template("configurar_movimientos.html")

@app.route("/status_connection")
def status_connection():
    if serial_connection and serial_connection.is_open: return jsonify({"connected": True, "port": serial_connection.port})
    return jsonify({"connected": False, "port": None})

@app.route("/control_brazo/mover_servos_global", methods=["POST"])
def mover_servos_global():
    if not (serial_connection and serial_connection.is_open): return "No hay conexion", 400
    data = request.get_json()
    if not data or "velocidad" not in data or "servos" not in data or len(data["servos"]) != 6: return "Datos incorrectos.", 400
    brazo.mover_servos({i + 1: s for i, s in enumerate(data["servos"])}, data["velocidad"]); return "Comando enviado.", 200

@app.route("/guardar_movimiento", methods=["POST"])
def guardar_movimiento():
    data = request.get_json(); folder_path = app_data_path("movimientos"); os.makedirs(folder_path, exist_ok=True)
    file_path = os.path.join(folder_path, f"{data['movementName']}.txt")
    with open(file_path, "w", encoding='utf-8') as f:
        for pos in data['posiciones']: f.write(f"{json.dumps(pos)}\n")
    return "Movimiento guardado."

@app.route("/obtener_movimientos", methods=["GET"])
def obtener_movimientos():
    folder_path = app_data_path("movimientos"); os.makedirs(folder_path, exist_ok=True)
    return jsonify([f for f in os.listdir(folder_path) if f.endswith(".txt")])

@app.route("/borrar_movimiento/<nombre>", methods=["DELETE"])
def borrar_movimiento(nombre):
    file_path = app_data_path(os.path.join("movimientos", nombre))
    if os.path.exists(file_path): os.remove(file_path); return f"Movimiento '{nombre}' eliminado."
    return f"Movimiento no encontrado.", 404

@app.route("/ejecutar_movimiento/<nombre>", methods=["POST"])
def ejecutar_movimiento(nombre):
    file_path = app_data_path(os.path.join("movimientos", nombre))
    if not os.path.exists(file_path): return jsonify({"error": "Movimiento no encontrado"}), 404
    with open(file_path, "r", encoding='utf-8') as f:
        for line in f:
            if line.strip():
                pos = json.loads(line); brazo.mover_servos({i+1: s for i, s in enumerate(pos['servos'])}, pos['velocidad']); time.sleep(0.5)
    return jsonify({"mensaje": "Movimiento ejecutado."})

@app.route("/configurar_logica")
def configurar_logica():
    mov_path = app_data_path("movimientos"); os.makedirs(mov_path, exist_ok=True)
    movs = [f.replace(".txt", "") for f in os.listdir(mov_path) if f.endswith(".txt")]
    return render_template("configurar_logica.html", form_labels=form_labels, color_labels=color_labels, movimientos=movs)

@app.route("/guardar_logica", methods=["POST"])
def guardar_logica():
    reglas = request.get_json(); logica_path = app_data_path("logica_config.json")
    with open(logica_path, "w", encoding='utf-8') as f: json.dump(reglas, f, indent=4)
    return "Configuracion guardada."

@app.route("/cargar_logica", methods=["GET"])
def cargar_logica():
    path = app_data_path("logica_config.json")
    if not os.path.exists(path): return jsonify([])
    with open(path, "r", encoding='utf-8') as f:
        try: return jsonify(json.load(f))
        except: return jsonify([])

@app.route("/iniciar_ejecucion", methods=["POST"])
def iniciar_ejecucion_route():
    threading.Thread(target=iniciar_ejecucion, args=(form_interpreter, color_interpreter, form_labels, color_labels, cap, banda, brazo), daemon=True).start()
    return jsonify(status='enviado')

@app.route("/detener_ejecucion", methods=["POST"])
def detener_ejecucion_route():
    detener_ejecucion(); return jsonify(status='enviado')

@app.route("/cargar_movimiento/<nombre>", methods=["POST"])
def cargar_movimiento(nombre):
    path = app_data_path(os.path.join("movimientos", nombre));
    if not os.path.exists(path): return jsonify({"error": "No encontrado"}), 404
    with open(path, "r", encoding='utf-8') as f: return jsonify([json.loads(line) for line in f if line.strip()])

@app.route("/guardar_punto", methods=["POST"])
def guardar_punto():
    data = request.get_json(); folder_path = app_data_path("puntos_guardados"); os.makedirs(folder_path, exist_ok=True)
    file_path = os.path.join(folder_path, f"{data['name']}.txt")
    contenido = f"Nombre: {data['name']}\nPosicion: X={data['x']}, Y={data['y']}, Z={data['z']}\nOrientacion: Roll={data['roll']}°, Pitch={data['pitch']}°, Yaw={data['yaw']}°\n"
    with open(file_path, "w", encoding='utf-8') as f: f.write(contenido)
    return f"Punto '{data['name']}' guardado."

@app.route("/listar_puntos", methods=["GET"])
def listar_puntos():
    path = app_data_path("puntos_guardados"); os.makedirs(path, exist_ok=True)
    return jsonify([f.replace(".txt", "") for f in os.listdir(path) if f.endswith(".txt")])

@app.route("/borrar_punto/<string:point_name>", methods=["DELETE"])
def borrar_punto(point_name):
    path = app_data_path(os.path.join("puntos_guardados", f"{point_name}.txt"))
    if os.path.exists(path): os.remove(path); return f"Punto '{point_name}' borrado."
    return f"Punto no encontrado.", 404

@app.route("/ver_punto/<string:point_name>", methods=["GET"])
def ver_punto(point_name):
    path = app_data_path(os.path.join("puntos_guardados", f"{point_name}.txt"))
    if not os.path.exists(path): return f"Punto no encontrado.", 404
    with open(path, "r", encoding='utf-8') as f: return f.read()

@app.route("/configurar_movimientos_CI")
def configurar_movimientos_CI(): return render_template("configurar_movimientos_CI.html")

@app.route("/calcular_angulos", methods=["POST"])
def calcular_angulos_servos():
    data = request.get_json()
    from modulos.cinematica_inversa import calcular_angulos
    angulos = calcular_angulos(data['x'], data['y'], data['z'], data['roll'], data['pitch'], data['yaw'])
    return jsonify({"angulos": angulos})

@app.route("/borrar_carpeta/<folder_name>", methods=["DELETE"])
def borrar_carpeta(folder_name):
    path = app_data_path(os.path.join("uploads", folder_name))
    if os.path.exists(path): shutil.rmtree(path); return f"Carpeta '{folder_name}' borrada."
    return "Carpeta no encontrada.", 404

@app.route("/borrar_todas_carpetas", methods=["DELETE"])
def borrar_todas_carpetas():
    path = app_data_path("uploads")
    if os.path.exists(path): shutil.rmtree(path); return "Carpetas de 'uploads' borradas."
    return "La carpeta 'uploads' no existe.", 404

@app.route("/logs", methods=["GET"])
def obtener_logs():
    path = app_data_path("ejecucion.log")
    try:
        with open(path, "r", encoding='utf-8') as f: logs = f.readlines()
        return jsonify(logs=logs[-1].strip() if logs else "")
    except FileNotFoundError: return jsonify(logs="No hay logs.")
    except Exception as e: return jsonify(logs=f"Error al leer logs: {e}"), 500

@app.route("/modbus/estado")
def estado_modbus(): return jsonify(modbus_bridge.get_status())
@app.route("/modbus/datos_plc")
def datos_plc(): return jsonify({"datos": modbus_bridge.get_plc_data(), "status": "success"})

@app.route("/calcular_posicion_gripper", methods=["POST"])
def calcular_posicion_gripper():
    data = request.get_json()
    if not data or "servos" not in data or len(data["servos"]) < 5: return jsonify({"error": "Faltan datos"}), 400
    return jsonify(forward_kinematics(data["servos"][:5]))

@app.route("/obtener_estado", methods=["GET"])
def obtener_estado():
    path = app_data_path("estado.json")
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f: return jsonify(json.load(f))
    return jsonify({"velocidad": 50, "servos": [90, 90, 90, 90, 90, 90]})

@app.route('/obtener_area_trabajo', methods=['GET'])
def obtener_area_trabajo():
    points = [{"x": x/100, "y": y/100, "z": z/100} for x, y, z in [(0, 0, 0), (100, 100, 100), (200, 200, 200)]]
    return jsonify({"points": points})

if __name__ == '__main__':
    try:
        app.run(host='0.0.0.0', port=80, debug=True)
    finally:
        print("Cerrando la aplicación y los recursos...")
        if cap: cap.release()
        modbus_bridge.stop()