# app/routes_api.py
import os
import time
import json
import threading
import shutil
import zipfile
import base64
import logging
import serial
import serial.tools.list_ports
from flask import Blueprint, jsonify, request, send_file
from io import BytesIO

# --- Importaciones del Contexto Refactorizado ---
from app.hardware import robot, app_data_path

# --- Importaciones de Módulos de Lógica Existentes ---
from modulos.ejecucion import iniciar_ejecucion, detener_ejecucion
from modulos.cinematica_directa import forward_kinematics
# Nota: Importamos cinemática inversa dentro de la función para evitar errores si el archivo falta

api_bp = Blueprint('api', __name__)

# Diccionario global para rastrear clientes (IP -> Timestamp)
connected_clients = {}

@api_bp.before_app_request
def track_clients():
    """Registra la actividad de cualquier cliente que haga peticiones a la API o Web"""
    if request.endpoint != 'static': 
        client_ip = request.remote_addr
        connected_clients[client_ip] = time.time()

@api_bp.route("/get_connected_clients")
def get_connected_clients():
    """Endpoint consumido por la GUI de Windows"""
    active_threshold = time.time() - 60 # Clientes activos en el último minuto
    active_clients = [ip for ip, last_seen in connected_clients.items() 
                     if last_seen > active_threshold]
    return jsonify(clients=active_clients)


# ==========================================
# 1. GESTIÓN DE CONEXIÓN (SERIAL / MODBUS)
# ==========================================

@api_bp.route("/listar_puertos")
def listar_puertos():
    return jsonify([p.device for p in serial.tools.list_ports.comports()])

@api_bp.route("/conectar_serial/<path:puerto>", methods=["POST"])
def conectar_serial(puerto):
    # Lógica restaurada del app.py original
    if robot.serial_port and robot.serial_port.is_open:
        robot.serial_port.close()
    try:
        robot.serial_port = serial.Serial(port=puerto, baudrate=9600, timeout=1)
        time.sleep(2) # Espera a que Arduino reinicie
        
        if robot.serial_port.is_open:
            # Asignar la conexión a los objetos de hardware
            robot.conveyor.set_connection(robot.serial_port)
            robot.arm.set_connection(robot.serial_port)
            
            # Mover a posición segura al conectar
            posicion_segura = {"velocidad": 0, "servos": [90, 90, 90, 90, 90, 90]}
            robot.serial_port.write((json.dumps(posicion_segura) + "\n").encode())
            
            return f"Conectado a {puerto}"
        raise serial.SerialException("No se pudo abrir el puerto.")
    except Exception as e:
        return f"Error al conectar: {e}", 500

@api_bp.route("/status_connection")
def status_connection():
    if robot.serial_port and robot.serial_port.is_open:
        return jsonify({"connected": True, "port": robot.serial_port.port})
    return jsonify({"connected": False, "port": None})

@api_bp.route("/modbus/estado")
def estado_modbus():
    if robot.modbus:
        return jsonify(robot.modbus.get_status())
    return jsonify({"status": "Modbus no inicializado"})

@api_bp.route("/modbus/datos_plc")
def datos_plc():
    if robot.modbus:
        return jsonify({"datos": robot.modbus.get_plc_data(), "status": "success"})
    return jsonify({"datos": [], "status": "error"})

# ==========================================
# 2. CONTROL MANUAL DE HARDWARE
# ==========================================

@api_bp.route("/control_banda/<accion>", methods=["POST"])
def control_banda(accion):
    if not (robot.serial_port and robot.serial_port.is_open):
        return "No hay conexion", 400
        
    actions = {
        "activar": robot.conveyor.activar,
        "desactivar": robot.conveyor.desactivar,
        "derecha": robot.conveyor.direccion_derecha,
        "izquierda": robot.conveyor.direccion_izquierda
    }
    
    if accion in actions:
        actions[accion]()
        return f"Banda {accion}"
    return "Accion no reconocida", 400

@api_bp.route("/control_brazo/mover_servos_global", methods=["POST"])
def mover_servos_global():
    if not (robot.serial_port and robot.serial_port.is_open):
        return "No hay conexion", 400
    
    data = request.get_json()
    if not data or "velocidad" not in data or "servos" not in data or len(data["servos"]) != 6:
        return "Datos incorrectos.", 400
        
    # Mapeo de lista a diccionario {1:val, 2:val...} que espera la clase Brazo
    servos_dict = {i + 1: s for i, s in enumerate(data["servos"])}
    robot.arm.mover_servos(servos_dict, data["velocidad"])
    return "Comando enviado.", 200

# ==========================================
# 3. GESTIÓN DE ARCHIVOS (MOVIMIENTOS)
# ==========================================

@api_bp.route("/guardar_movimiento", methods=["POST"])
def guardar_movimiento():
    data = request.get_json()
    folder_path = app_data_path("movimientos")
    os.makedirs(folder_path, exist_ok=True)
    
    file_path = os.path.join(folder_path, f"{data['movementName']}.txt")
    with open(file_path, "w", encoding='utf-8') as f:
        for pos in data['posiciones']:
            f.write(f"{json.dumps(pos)}\n")
    return "Movimiento guardado."

@api_bp.route("/obtener_movimientos", methods=["GET"])
def obtener_movimientos():
    folder_path = app_data_path("movimientos")
    os.makedirs(folder_path, exist_ok=True)
    return jsonify([f for f in os.listdir(folder_path) if f.endswith(".txt")])

@api_bp.route("/borrar_movimiento/<nombre>", methods=["DELETE"])
def borrar_movimiento(nombre):
    file_path = app_data_path(os.path.join("movimientos", nombre))
    if os.path.exists(file_path):
        os.remove(file_path)
        return f"Movimiento '{nombre}' eliminado."
    return f"Movimiento no encontrado.", 404

@api_bp.route("/cargar_movimiento/<nombre>", methods=["POST"])
def cargar_movimiento(nombre):
    path = app_data_path(os.path.join("movimientos", nombre))
    if not os.path.exists(path):
        return jsonify({"error": "No encontrado"}), 404
    with open(path, "r", encoding='utf-8') as f:
        return jsonify([json.loads(line) for line in f if line.strip()])

@api_bp.route("/ejecutar_movimiento/<nombre>", methods=["POST"])
def ejecutar_movimiento(nombre):
    file_path = app_data_path(os.path.join("movimientos", nombre))
    if not os.path.exists(file_path):
        return jsonify({"error": "Movimiento no encontrado"}), 404
        
    def run_sequence():
        with open(file_path, "r", encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    pos = json.loads(line)
                    servos_dict = {i+1: s for i, s in enumerate(pos['servos'])}
                    robot.arm.mover_servos(servos_dict, pos['velocidad'])
                    time.sleep(0.5)
    
    # Ejecutar en hilo para no bloquear el servidor
    threading.Thread(target=run_sequence, daemon=True).start()
    return jsonify({"mensaje": "Movimiento ejecutado."})

# ==========================================
# 4. GESTIÓN DE LÓGICA Y CONFIGURACIÓN
# ==========================================

@api_bp.route("/guardar_logica", methods=["POST"])
def guardar_logica():
    reglas = request.get_json()
    logica_path = app_data_path("logica_config.json")
    with open(logica_path, "w", encoding='utf-8') as f:
        json.dump(reglas, f, indent=4)
    return "Configuracion guardada."

@api_bp.route("/cargar_logica", methods=["GET"])
def cargar_logica():
    path = app_data_path("logica_config.json")
    if not os.path.exists(path):
        return jsonify([])
    with open(path, "r", encoding='utf-8') as f:
        try: return jsonify(json.load(f))
        except: return jsonify([])

@api_bp.route("/obtener_estado", methods=["GET"])
def obtener_estado():
    # Intenta leer el archivo estado.json que escribe el backend
    path = app_data_path("estado.json")
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            return jsonify(json.load(f))
    return jsonify({"velocidad": 50, "servos": [90, 90, 90, 90, 90, 90]})

@api_bp.route("/logs", methods=["GET"])
def obtener_logs():
    path = app_data_path("ejecucion.log")
    try:
        with open(path, "r", encoding='utf-8') as f:
            logs = f.readlines()
        return jsonify(logs=logs[-1].strip() if logs else "")
    except FileNotFoundError:
        return jsonify(logs="No hay logs.")
    except Exception as e:
        return jsonify(logs=f"Error al leer logs: {e}"), 500

# ==========================================
# 5. GESTIÓN DE IMÁGENES (DATASET)
# ==========================================

@api_bp.route("/guardar_imagenes", methods=["POST"])
def guardar_imagenes():
    data = request.get_json()
    folder_path = app_data_path(os.path.join("uploads", data['folder_name']))
    os.makedirs(folder_path, exist_ok=True)
    
    for i, photo in enumerate(data['photos']):
        # Decodificar Base64
        header, encoded = photo.split(",", 1)
        data_bytes = base64.b64decode(encoded)
        with open(os.path.join(folder_path, f"{data['folder_name']}_{i+1}.jpg"), "wb") as f:
            f.write(data_bytes)
    return "Fotos guardadas."

@api_bp.route("/obtener_carpetas")
def obtener_carpetas():
    folder_path = app_data_path('uploads')
    os.makedirs(folder_path, exist_ok=True)
    # Filtramos para no mostrar las carpetas de modelos
    return jsonify([f for f in os.listdir(folder_path) 
                   if os.path.isdir(os.path.join(folder_path, f)) 
                   and f not in ['model_color', 'model_form']])

@api_bp.route("/descargar/<folder_name>")
def descargar(folder_name):
    folder_path = app_data_path(os.path.join("uploads", folder_name))
    if not os.path.exists(folder_path):
        return "Carpeta no existe", 404
        
    zip_path = app_data_path(f"{folder_name}.zip")
    with zipfile.ZipFile(zip_path, 'w') as zf:
        for root, _, files in os.walk(folder_path):
            for file in files:
                zf.write(os.path.join(root, file), 
                        os.path.relpath(os.path.join(root, file), folder_path))
                        
    return send_file(zip_path, as_attachment=True, download_name=f"{folder_name}.zip")

@api_bp.route("/borrar_carpeta/<folder_name>", methods=["DELETE"])
def borrar_carpeta(folder_name):
    path = app_data_path(os.path.join("uploads", folder_name))
    if os.path.exists(path):
        shutil.rmtree(path)
        return f"Carpeta '{folder_name}' borrada."
    return "Carpeta no encontrada.", 404

@api_bp.route("/borrar_todas_carpetas", methods=["DELETE"])
def borrar_todas_carpetas():
    path = app_data_path("uploads")
    if os.path.exists(path):
        # Borrar contenido pero intentar mantener estructura si es necesario
        # (Aquí replicamos el comportamiento original de borrar todo)
        shutil.rmtree(path)
        os.makedirs(path, exist_ok=True) # Recrear carpeta vacía
        return "Carpetas de 'uploads' borradas."
    return "La carpeta 'uploads' no existe.", 404

# ==========================================
# 6. PUNTOS Y CINEMÁTICA
# ==========================================

@api_bp.route("/guardar_punto", methods=["POST"])
def guardar_punto():
    data = request.get_json()
    folder_path = app_data_path("puntos_guardados")
    os.makedirs(folder_path, exist_ok=True)
    
    file_path = os.path.join(folder_path, f"{data['name']}.txt")
    contenido = (f"Nombre: {data['name']}\n"
                 f"Posicion: X={data['x']}, Y={data['y']}, Z={data['z']}\n"
                 f"Orientacion: Roll={data['roll']}°, Pitch={data['pitch']}°, Yaw={data['yaw']}°\n")
                 
    with open(file_path, "w", encoding='utf-8') as f:
        f.write(contenido)
    return f"Punto '{data['name']}' guardado."

@api_bp.route("/listar_puntos", methods=["GET"])
def listar_puntos():
    path = app_data_path("puntos_guardados")
    os.makedirs(path, exist_ok=True)
    return jsonify([f.replace(".txt", "") for f in os.listdir(path) if f.endswith(".txt")])

@api_bp.route("/borrar_punto/<string:point_name>", methods=["DELETE"])
def borrar_punto(point_name):
    path = app_data_path(os.path.join("puntos_guardados", f"{point_name}.txt"))
    if os.path.exists(path):
        os.remove(path)
        return f"Punto '{point_name}' borrado."
    return f"Punto no encontrado.", 404

@api_bp.route("/ver_punto/<string:point_name>", methods=["GET"])
def ver_punto(point_name):
    path = app_data_path(os.path.join("puntos_guardados", f"{point_name}.txt"))
    if not os.path.exists(path):
        return f"Punto no encontrado.", 404
    with open(path, "r", encoding='utf-8') as f:
        return f.read()

@api_bp.route("/calcular_angulos", methods=["POST"])
def calcular_angulos_servos():
    data = request.get_json()
    # Importación local para evitar errores si no existe el módulo
    try:
        from modulos.cinematica_inversa import calcular_angulos
        angulos = calcular_angulos(data['x'], data['y'], data['z'], 
                                   data['roll'], data['pitch'], data['yaw'])
        return jsonify({"angulos": angulos})
    except ImportError:
        return jsonify({"error": "Módulo de cinemática inversa no encontrado"}), 500

@api_bp.route("/calcular_posicion_gripper", methods=["POST"])
def calcular_posicion_gripper():
    data = request.get_json()
    if not data or "servos" not in data or len(data["servos"]) < 5:
        return jsonify({"error": "Faltan datos"}), 400
    return jsonify(forward_kinematics(data["servos"][:5]))

@api_bp.route('/obtener_area_trabajo', methods=['GET'])
def obtener_area_trabajo():
    # Datos estáticos del app.py original
    points = [{"x": x/100, "y": y/100, "z": z/100} 
              for x, y, z in [(0, 0, 0), (100, 100, 100), (200, 200, 200)]]
    return jsonify({"points": points})

# ==========================================
# 7. EJECUCIÓN DEL PROCESO PRINCIPAL
# ==========================================

@api_bp.route("/iniciar_ejecucion", methods=["POST"])
def iniciar_ejecucion_route():
    """
    Inicia la máquina de estados que controla todo el proceso.
    Recuperamos los objetos desde 'robot' (hardware.py).
    """
    cap = robot.get_camera() # Obtener cámara limpia
    
    # Lanzamos el hilo de ejecución pasando los objetos globales
    # Nota: Aseguramos que los labels estén cargados
    if not robot.shape_labels or not robot.color_labels:
        robot.load_models()

    threading.Thread(
        target=iniciar_ejecucion, 
        args=(
            robot.shape_model, 
            robot.color_model, 
            robot.shape_labels, 
            robot.color_labels, 
            cap, 
            robot.conveyor, 
            robot.arm
        ), 
        daemon=True
    ).start()
    
    return jsonify(status='enviado')

@api_bp.route("/detener_ejecucion", methods=["POST"])
def detener_ejecucion_route():
    detener_ejecucion()
    return jsonify(status='enviado')

# ==========================================
# 8. SUBIDA DE MODELOS (STUB)
# ==========================================

@api_bp.route("/upload_model", methods=["POST"])
def upload_model():
    return jsonify({'message': 'Subir modelos no soportado en ejecución compilada. Recompile la app.'}), 400