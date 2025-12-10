# app/routes_web.py
import time
import cv2
import json
import os
import numpy as np
from flask import Blueprint, render_template, Response, request
from app.hardware import robot, app_data_path

# Creamos el Blueprint 'web'
web_bp = Blueprint('web', __name__)

# --- Generadores de Video ---

def gen_raw_frames():
    """Genera video crudo sin procesamiento (para camera_feed)."""
    cap = robot.get_camera()
    # Si la cámara está ocupada por otro hilo (ej. ejecución automática),
    # intentamos usar el frame global si existe.
    if not cap or not cap.isOpened():
        while True:
            if robot.current_frame is not None:
                yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + robot.current_frame + b'\r\n')
            time.sleep(0.1)
        return

    while True:
        success, frame = cap.read()
        if not success:
            time.sleep(0.1)
            continue
        
        # Actualizar estado global para otros consumidores
        _, buffer = cv2.imencode('.jpg', frame)
        robot.current_frame = buffer.tobytes() 

        yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
    
    cap.release()

def gen_overlay_frames():
    """
    Genera video con superposición de datos (FPS, detecciones).
    Replica la lógica de 'gen_frames' del app.py original.
    """
    # Intentamos obtener cámara, si falla, usamos el frame global
    # (Esto permite ver el video incluso si el robot está ejecutando su ciclo en background)
    local_cap = robot.get_camera()
    
    while True:
        frame = None
        
        # 1. Obtener imagen
        if local_cap and local_cap.isOpened():
            success, read_frame = local_cap.read()
            if success:
                frame = read_frame
        
        # Si no tenemos cámara local (quizás ocupada por el hilo de ejecución), usamos el global
        if frame is None and robot.current_frame:
            nparr = np.frombuffer(robot.current_frame, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if frame is None:
            # Generar imagen negra de espera
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            cv2.putText(frame, "ESPERANDO CAMARA...", (50, 240), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
            time.sleep(0.5)
        else:
            # 2. Superponer Información (Paridad con app.py)
            # Si hay una clasificación reciente, la pintamos
            if robot.last_classification and robot.last_classification != "vacio":
                cv2.putText(frame, robot.last_classification, (10, 60), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
            
            # Si hay modelos cargados o no
            if not (robot.shape_model and robot.color_model):
                cv2.putText(frame, "Modelos NO cargados", (10, 30), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
            
            # FPS (calculados en hardware o localmente)
            cv2.putText(frame, f"FPS: {robot.fps:.1f}", (500, 30), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 2)

        # 3. Codificar y Enviar
        ret, buffer = cv2.imencode('.jpg', frame)
        yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')

# --- Rutas de Streaming ---

@web_bp.route("/camera_feed")
def camera_feed():
    """Feed crudo para procesos de visión pura"""
    return Response(gen_raw_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@web_bp.route("/video_feed")
def video_feed():
    """Feed con overlays para la UI humana"""
    return Response(gen_overlay_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

# --- Rutas de Navegación (HTML con Contexto) ---

@web_bp.route("/")
def index(): 
    return render_template("index.html")

@web_bp.route("/opciones")
def opciones():
    """
    Carga configuración lógica y etiquetas para los dropdowns.
    CORRECCIÓN CRÍTICA: El original leía 'logica_config.json' y pasaba labels.
    """
    # 1. Cargar configuración lógica
    logic_config_path = app_data_path("logica_config.json")
    logic_config = []
    if os.path.exists(logic_config_path):
        with open(logic_config_path, "r", encoding='utf-8') as file:
            try: 
                logic_config = json.load(file)
            except: 
                logic_config = []
    
    # 2. Asegurar que labels estén cargados en memoria
    if not robot.shape_labels or not robot.color_labels:
        robot.load_models()

    # 3. Renderizar con contexto completo
    return render_template("opciones.html", 
                           form_labels=robot.shape_labels, 
                           color_labels=robot.color_labels, 
                           model_loaded=(robot.shape_model and robot.color_model), 
                           logic_config=logic_config)

@web_bp.route("/tomar_imagen")
def tomar_imagen(): 
    return render_template("tomar_imagen.html")

@web_bp.route("/entrenar")
def entrenar(): 
    return render_template("entrenar.html")

@web_bp.route("/subir_modelo")
def subir_modelo():
    origen = request.args.get('origen', 'panel')
    return render_template("subir_modelo.html", origen=origen)


@web_bp.route("/verificar_reconocimiento")
def verificar_reconocimiento():
    # Paridad: Verifica si hay modelos y pasa lista completa de etiquetas
    if not (robot.shape_model and robot.color_model):
        # En el original retornaba un error 400 string, aquí podemos renderizar o dar error
        # Para ser amigable, renderizamos igual pero las listas estarán vacías si falla la carga
        robot.load_models()
    
    combined_labels = robot.shape_labels + robot.color_labels
    return render_template("verificar_reconocimiento.html", labels=combined_labels)

@web_bp.route("/configurar_movimientos")
def configurar_movimientos(): 
    return render_template("configurar_movimientos.html")

@web_bp.route("/configurar_movimientos_CI")
def configurar_movimientos_CI(): 
    return render_template("configurar_movimientos_CI.html")

@web_bp.route("/configurar_logica")
def configurar_logica():
    """
    Necesita listar los archivos de movimientos .txt para el dropdown.
    """
    mov_path = app_data_path("movimientos")
    os.makedirs(mov_path, exist_ok=True)
    
    # Listar movimientos sin la extensión .txt
    movs = [f.replace(".txt", "") for f in os.listdir(mov_path) if f.endswith(".txt")]
    
    # Asegurar labels
    if not robot.shape_labels: 
        robot.load_models()

    return render_template("configurar_logica.html", 
                           form_labels=robot.shape_labels, 
                           color_labels=robot.color_labels, 
                           movimientos=movs)