import os
import zipfile
import time
import json
import threading  # <--- CORRECCIÓN 1: Importar threading para no bloquear la web
from flask import Flask, render_template, Response, request, jsonify, send_file
import cv2
from io import BytesIO
import base64
import numpy as np

# --- CORRECCIÓN 2: Importación compatible con Raspberry Pi y Windows ---
try:
    # Intenta importar la versión ligera (Raspberry Pi)
    import tflite_runtime.interpreter as tflite
except ImportError:
    # Si falla, usa la versión completa (Windows/PC)
    import tensorflow.lite as tflite
# -----------------------------------------------------------------------

# Importa la clase BandaTransportadora
from modulos.banda_transportadora import BandaTransportadora

# Importar la función de ejecución automática
from modulos.ejecucion import iniciar_ejecucion

# Importa la clase BrazoRobotico
from modulos.brazo_robotico import BrazoRobotico

# Importar librería serial
import serial
import serial.tools.list_ports

from modulos.reconocimiento import reconocimiento_de_objetos


# Función para cargar el modelo TensorFlow Lite
def cargar_modelo(model_path):
    """Carga el modelo TensorFlow Lite usando el alias 'tflite' definido arriba."""
    interpreter = tflite.Interpreter(model_path=model_path)
    interpreter.allocate_tensors()
    return interpreter


# --- CORRECCIÓN 3: INICIO TOLERANTE A FALLOS (Sin cámara) ---
cap = cv2.VideoCapture(0)
camera_available = False

if cap.isOpened():
    camera_available = True
    print("✅ Cámara detectada e iniciada.")
else:
    print("⚠️ ADVERTENCIA: No se detectó cámara. El servidor iniciará en modo 'Sin Video'.")
# ------------------------------------------------------------


app = Flask(__name__)

# Variable global para la conexión serial
serial_connection = None

# Instancia global de BandaTransportadora
banda = BandaTransportadora()

# Instancia global de Brazo Robotico
brazo = BrazoRobotico()


# Ruta para la página principal
@app.route("/")
def index():
    return render_template("index.html")


# Ruta para la página de opciones
@app.route("/opciones")
def opciones():
    # Verificar rutas de los modelos y etiquetas
    form_model_path = os.path.join('uploads', 'model_form', 'model_unquant.tflite')
    color_model_path = os.path.join('uploads', 'model_color', 'model_unquant.tflite')

    form_labels_path = os.path.join('uploads', 'model_form', 'labels.txt')
    color_labels_path = os.path.join('uploads', 'model_color', 'labels.txt')

    # Verificar si ambos modelos y etiquetas están disponibles
    if not os.path.exists(form_model_path) or not os.path.exists(color_model_path):
        return render_template(
            "opciones.html",
            message="Modelos no cargados. Por favor, sube los modelos de formas y colores.",
            model_loaded=False
        )

    # Leer etiquetas de formas y colores
    form_labels = []
    color_labels = []

    if os.path.exists(form_labels_path):
        with open(form_labels_path, 'r') as file:
            form_labels = file.read().splitlines()

    if os.path.exists(color_labels_path):
        with open(color_labels_path, 'r') as file:
            color_labels = file.read().splitlines()

    # Renderizar la página con las etiquetas cargadas
    return render_template(
        "opciones.html",
        form_labels=form_labels,
        color_labels=color_labels,
        model_loaded=True
    )


@app.route("/listar_puertos")
def listar_puertos():
    """Devuelve una lista en formato JSON con todos los puertos seriales disponibles."""
    ports = serial.tools.list_ports.comports()
    port_list = [port.device for port in ports]
    return jsonify(port_list)


@app.route("/conectar_serial/<string:puerto>", methods=["POST"])
def conectar_serial(puerto):
    global serial_connection

    # Cerrar si había una previa
    if serial_connection and serial_connection.is_open:
        serial_connection.close()
        serial_connection = None

    try:
        # Abre la conexión con el puerto que seleccionó el usuario
        serial_connection = serial.Serial(port=puerto, baudrate=9600, timeout=1)
        
        if serial_connection.is_open:
            # Asigna la conexión abierta a la banda y al brazo
            banda.set_connection(serial_connection)
            brazo.set_connection(serial_connection)

            return f"Conectado correctamente al puerto {puerto}"
        else:
            return f"No se pudo abrir el puerto {puerto}", 500

    except Exception as e:
        return f"Error al conectar al puerto {puerto}: {e}", 500


@app.route("/control_banda/<accion>", methods=["POST"])
def control_banda(accion):
    # Si no hay conexión abierta, avisa
    if not serial_connection or not serial_connection.is_open:
        return "No hay conexión activa con la banda", 400

    # Según la acción, llamamos a los métodos de la banda
    if accion == "activar":
        banda.activar()
        return "Banda activada"
    elif accion == "desactivar":
        banda.desactivar()
        return "Banda desactivada"
    elif accion == "derecha":
        banda.direccion_derecha()
        return "Banda girando a la derecha"
    elif accion == "izquierda":
        banda.direccion_izquierda()
        return "Banda girando a la izquierda"
    else:
        return "Acción no reconocida", 400


# Ruta para la página de tomar imagen
@app.route("/tomar_imagen")
def tomar_imagen():
    return render_template("tomar_imagen.html")


# Ruta para la página de entrenar
@app.route("/entrenar")
def entrenar():
    return render_template("entrenar.html")


# Ruta para subir el modelo generado
@app.route("/subir_modelo")
def subir_modelo():
    return render_template("subir_modelo.html")


# Ruta para manejar la subida del modelo
@app.route("/upload_model", methods=["POST"])
def upload_model():
    # Verificar que ambos archivos estén presentes
    if 'form_model' not in request.files or 'color_model' not in request.files:
        return "No se han enviado ambos archivos", 400

    form_model_file = request.files['form_model']
    color_model_file = request.files['color_model']

    if form_model_file.filename == '' or color_model_file.filename == '':
        return "No se seleccionaron ambos archivos", 400

    # Manejar el modelo de formas
    if form_model_file and form_model_file.filename.endswith('.zip'):
        form_model_path = os.path.join('uploads', 'model_form')
        if not os.path.exists(form_model_path):
            os.makedirs(form_model_path)

        # Extraer el contenido del ZIP
        with zipfile.ZipFile(form_model_file, 'r') as zip_ref:
            zip_ref.extractall(form_model_path)

    # Manejar el modelo de colores
    if color_model_file and color_model_file.filename.endswith('.zip'):
        color_model_path = os.path.join('uploads', 'model_color')
        if not os.path.exists(color_model_path):
            os.makedirs(color_model_path)

        # Extraer el contenido del ZIP
        with zipfile.ZipFile(color_model_file, 'r') as zip_ref:
            zip_ref.extractall(color_model_path)

    # Leer las etiquetas de ambos modelos
    form_labels_path = os.path.join('uploads', 'model_form', 'labels.txt')
    color_labels_path = os.path.join('uploads', 'model_color', 'labels.txt')

    form_labels = []
    color_labels = []

    if os.path.exists(form_labels_path):
        with open(form_labels_path, 'r') as file:
            form_labels = file.read().splitlines()

    if os.path.exists(color_labels_path):
        with open(color_labels_path, 'r') as file:
            color_labels = file.read().splitlines()

    # Devolver las etiquetas de ambos modelos
    return jsonify({
        'form_labels': form_labels,
        'color_labels': color_labels
    })


# Cargar los modelos e intérpretes al inicio
form_model_path = os.path.join('uploads', 'model_form', 'model_unquant.tflite')
color_model_path = os.path.join('uploads', 'model_color', 'model_unquant.tflite')

form_labels_path = os.path.join('uploads', 'model_form', 'labels.txt')
color_labels_path = os.path.join('uploads', 'model_color', 'labels.txt')

# Inicializar variables globales para los modelos e intérpretes
form_interpreter = None
color_interpreter = None
form_labels = []
color_labels = []

try:
    # Verificar la existencia de los modelos y etiquetas de formas
    if os.path.exists(form_model_path) and os.path.exists(form_labels_path):
        with open(form_labels_path, 'r') as file:
            form_labels = [label.split(' ')[1] for label in file.read().splitlines()]  # Limpiar etiquetas
        form_interpreter = cargar_modelo(form_model_path)
        print("Modelo de formas cargado correctamente.")
        print(f"Form Interpreter: {form_interpreter}")
        print(f"Form Labels: {form_labels}")

    # Verificar la existencia de los modelos y etiquetas de colores
    if os.path.exists(color_model_path) and os.path.exists(color_labels_path):
        with open(color_labels_path, 'r') as file:
            color_labels = [label.split(' ')[1] for label in file.read().splitlines()]  # Limpiar etiquetas
        color_interpreter = cargar_modelo(color_model_path)
        print("Modelo de colores cargado correctamente.")
        print(f"Color Interpreter: {color_interpreter}")
        print(f"Color Labels: {color_labels}")
except Exception as e:
    print(f"Error al cargar modelos: {e}")


# Verificar la existencia de los modelos y etiquetas (Redundancia por si falló el bloque anterior)
if os.path.exists(form_model_path) and os.path.exists(form_labels_path) and form_interpreter is None:
    with open(form_labels_path, 'r') as file:
        form_labels = file.read().splitlines()
    form_interpreter = cargar_modelo(form_model_path)

if os.path.exists(color_model_path) and os.path.exists(color_labels_path) and color_interpreter is None:
    with open(color_labels_path, 'r') as file:
        color_labels = file.read().splitlines()
    color_interpreter = cargar_modelo(color_model_path)


# Ruta para mostrar video de la cámara conectada al servidor (CON reconocimiento)
def gen_frames():
    # --- MODO SIN CÁMARA O MODELOS: Generar imagen negra ---
    if form_interpreter is None or color_interpreter is None:
        frame = np.zeros((480, 640, 3), dtype=np.uint8)  # Crear un frame negro
        mensaje = "Modelos no cargados"
        cv2.putText(frame, mensaje, (50, 240), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2, cv2.LINE_AA)
        ret, buffer = cv2.imencode('.jpg', frame)
        frame = buffer.tobytes()
        yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
        return

    while True:
        if camera_available:
            success, frame = cap.read()
            if not success:
                break
        else:
            # Generar frame negro si no hay cámara
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            cv2.putText(frame, "CAMARA NO CONECTADA", (100, 240), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)
            time.sleep(0.1)  # Simular espera para no saturar CPU

        try:
            # Solo intentamos reconocer si tenemos una imagen real (cámara conectada)
            if camera_available:
                # Reconocimiento de forma
                forma = reconocimiento_de_objetos(frame, form_interpreter, form_labels)
                # Reconocimiento de color
                color = reconocimiento_de_objetos(frame, color_interpreter, color_labels)

                # Manejar el caso de "vacio"
                if forma == "vacio" or color == "vacio":
                    etiqueta = "Sin detección"
                else:
                    etiqueta = f"{forma}_{color}"

                cv2.putText(frame, etiqueta, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2, cv2.LINE_AA)
            
        except Exception as e:
            # print(f"Error en la predicción: {e}") # Comentado para no saturar la consola
            pass

        ret, buffer = cv2.imencode('.jpg', frame)
        frame = buffer.tobytes()
        yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')


def gen_raw_frames():
    """Genera frames crudos o imagen de error si no hay cámara."""
    while True:
        if camera_available:
            success, frame = cap.read()  # Leer frame de la cámara
            if not success:
                break
        else:
            # Imagen de espera
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            cv2.putText(frame, "NO HAY CAMARA", (180, 240), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
            time.sleep(0.1)

        ret, buffer = cv2.imencode('.jpg', frame)
        frame = buffer.tobytes()
        yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')


@app.route("/camera_feed")
def camera_feed():
    """Ruta para el feed de cámara sin reconocimiento."""
    return Response(gen_raw_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')


@app.route("/video_feed")
def video_feed():
    return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')


@app.route("/guardar_imagenes", methods=["POST"])
def guardar_imagenes():
    data = request.get_json()
    folder_name = data['folder_name']
    photos = data['photos']

    folder_path = os.path.join("uploads", folder_name)

    if not os.path.exists(folder_path):
        os.makedirs(folder_path)

    for i, photo in enumerate(photos):
        # Decodificar la imagen base64
        image_data = photo.split(',')[1]  # Eliminar el encabezado base64
        image_bytes = base64.b64decode(image_data)  # Decodificar base64 a bytes

        # Guardar la imagen como un archivo .jpg
        with open(os.path.join(folder_path, f"{folder_name}_{i+1}.jpg"), "wb") as file:
            file.write(image_bytes)

    return "Fotos guardadas exitosamente"


@app.route("/obtener_carpetas")
def obtener_carpetas():
    """Devuelve una lista de todas las carpetas disponibles en 'uploads/'."""
    folder_path = 'uploads'

    # Crear la carpeta principal si no existe
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)

    # Listar todas las carpetas
    folders = [f for f in os.listdir(folder_path) if os.path.isdir(os.path.join(folder_path, f))]

    return jsonify(folders)


@app.route("/descargar/<folder_name>")
def descargar(folder_name):
    """Comprime y descarga la carpeta seleccionada como .zip."""
    folder_path = os.path.join("uploads", folder_name)

    if not os.path.exists(folder_path):
        return "La carpeta no existe", 404

    zip_filename = f"{folder_name}.zip"
    zip_file = BytesIO()

    with zipfile.ZipFile(zip_file, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, _, files in os.walk(folder_path):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, folder_path)
                zipf.write(file_path, arcname)

    zip_file.seek(0)
    return send_file(zip_file, as_attachment=True, download_name=zip_filename)


@app.route("/verificar_reconocimiento")
def verificar_reconocimiento():
    form_model_path = os.path.join('uploads', 'model_form', 'model_unquant.tflite')
    color_model_path = os.path.join('uploads', 'model_color', 'model_unquant.tflite')
    form_labels_path = os.path.join('uploads', 'model_form', 'labels.txt')
    color_labels_path = os.path.join('uploads', 'model_color', 'labels.txt')

    if os.path.exists(form_model_path) and os.path.exists(color_model_path):
        labels = []
        if os.path.exists(form_labels_path):
            with open(form_labels_path, 'r') as file:
                labels.extend(file.read().splitlines())
        if os.path.exists(color_labels_path):
            with open(color_labels_path, 'r') as file:
                labels.extend(file.read().splitlines())

        return render_template("verificar_reconocimiento.html", labels=labels)
    else:
        return "Modelo no cargado correctamente.", 400


@app.route("/configurar_movimientos")
def configurar_movimientos():
    return render_template("configurar_movimientos.html")

@app.route("/status_connection")
def status_connection():
    global serial_connection
    if serial_connection and serial_connection.is_open:
        return jsonify({"connected": True, "port": serial_connection.port})
    else:
        return jsonify({"connected": False, "port": None})


@app.route("/control_brazo/mover_servo/<int:servo_num>/<int:angulo>/<int:vel>", methods=["POST"])
def mover_servo(servo_num, angulo, vel):
    if not serial_connection or not serial_connection.is_open:
        return "No hay conexión activa con el brazo", 400
    
    brazo.mover_servo(servo_num, angulo, vel)
    return f"Servo {servo_num} => {angulo}° con velocidad {vel} OK"


@app.route("/guardar_movimiento", methods=["POST"])
def guardar_movimiento():
    data = request.get_json()
    movement_name = data.get("movementName")
    posiciones = data.get("posiciones")

    if not movement_name or not posiciones:
        return "Nombre del movimiento o posiciones inválidas.", 400

    folder_path = os.path.join("movimientos")
    os.makedirs(folder_path, exist_ok=True)
    file_path = os.path.join(folder_path, f"{movement_name}.txt")

    try:
        with open(file_path, "w") as file:
            for posicion in posiciones:
                file.write(f"{posicion}\n")
        return f"Movimiento '{movement_name}' guardado exitosamente."
    except Exception as e:
        return f"Error al guardar el movimiento: {e}", 500


@app.route("/obtener_movimientos", methods=["GET"])
def obtener_movimientos():
    folder_path = "movimientos"
    os.makedirs(folder_path, exist_ok=True)
    movimientos = [f for f in os.listdir(folder_path) if f.endswith(".txt")]
    return jsonify(movimientos)


@app.route("/borrar_movimiento/<nombre>", methods=["DELETE"])
def borrar_movimiento(nombre):
    folder_path = "movimientos"
    file_path = os.path.join(folder_path, nombre)
    if os.path.exists(file_path):
        os.remove(file_path)
        return f"Movimiento '{nombre}' eliminado exitosamente."
    return f"El movimiento '{nombre}' no existe.", 404


@app.route("/ejecutar_movimiento/<nombre>", methods=["POST"])
def ejecutar_movimiento(nombre):
    folder_path = "movimientos"
    file_path = os.path.join(folder_path, nombre)

    if not os.path.exists(file_path):
        return f"El movimiento '{nombre}' no existe.", 404

    try:
        with open(file_path, "r") as file:
            for line in file:
                line = line.strip()

                if "Velocidad:" in line and "Servos:" in line:
                    try:
                        velocidad = int(line.split("Velocidad:")[1].split(",")[0].strip())
                        servos_str = line.split("Servos:")[1].strip().strip("[]")
                        servos = [int(angle.strip()) for angle in servos_str.split(",")]

                        for i, angulo in enumerate(servos, start=1):
                            brazo.mover_servo(i, angulo, velocidad)
                            time.sleep(0.2) 

                    except Exception as e:
                        print(f"Error procesando la línea: {line} -> {e}")
                        continue

        return f"Movimiento '{nombre}' ejecutado exitosamente."
    except Exception as e:
        return f"Error al ejecutar el movimiento: {e}", 500


@app.route("/configurar_logica")
def configurar_logica():
    # Cargar etiquetas de formas y colores
    form_labels_path = os.path.join('uploads', 'model_form', 'labels.txt')
    color_labels_path = os.path.join('uploads', 'model_color', 'labels.txt')

    form_labels = []
    color_labels = []

    if os.path.exists(form_labels_path):
        with open(form_labels_path, 'r') as file:
            form_labels = file.read().splitlines()

    if os.path.exists(color_labels_path):
        with open(color_labels_path, 'r') as file:
            color_labels = file.read().splitlines()

    # Cargar movimientos guardados
    movimientos_path = "movimientos"
    movimientos = [f.replace(".txt", "") for f in os.listdir(movimientos_path) if f.endswith(".txt")]

    return render_template("configurar_logica.html", form_labels=form_labels, color_labels=color_labels, movimientos=movimientos)


@app.route("/guardar_logica", methods=["POST"])
def guardar_logica():
    reglas = request.get_json()
    logica_path = "logica_config.json"

    try:
        with open(logica_path, "w") as file:
            json.dump(reglas, file, indent=4)
        return "Configuración de lógica guardada exitosamente."
    except Exception as e:
        return f"Error al guardar la configuración: {e}", 500


@app.route("/cargar_logica", methods=["GET"])
def cargar_logica():
    logica_path = "logica_config.json"
    if not os.path.exists(logica_path):
        return jsonify([]) 

    with open(logica_path, "r") as file:
        reglas = json.load(file)
    return jsonify(reglas)


@app.route("/ejecutar", methods=["POST"])
def ejecutar():
    """
    Inicia el proceso automático en un HILO SEPARADO para no bloquear Flask.
    """
    try:
        if form_interpreter is None or color_interpreter is None:
            return "Modelos no cargados. Por favor, asegúrate de que los modelos están correctamente configurados.", 400

        if not serial_connection or not serial_connection.is_open:
            return "Conexión serial no establecida. Por favor, conecta el dispositivo antes de ejecutar.", 400

        # --- CORRECCIÓN IMPORTANTE: Ejecutar en hilo separado ---
        thread = threading.Thread(
            target=iniciar_ejecucion,
            args=(form_interpreter, color_interpreter, form_labels, color_labels, cap, banda, brazo)
        )
        thread.daemon = True # El hilo se cerrará si se cierra el programa principal
        thread.start()
        # ---------------------------------------------------------

        return "Ejecución iniciada correctamente en segundo plano.", 200
    except Exception as e:
        return f"Error durante la ejecución: {e}", 500


if __name__ == "__main__":
    # --- MENSAJE INFORMATIVO AL INICIAR ---
    print("\n" + "="*50)
    print("  SERVIDOR ROBOT LISTO 🤖")
    print("  Accede desde tu navegador en estas direcciones:")
    print("  (Copia la IP y añade :5000 al final)")
    print("-" * 50)
    
    # Muestra las IPs limpias
    os.system("hostname -I") 
    
    print("-" * 50)
    print("  Ejemplo Cable: http://192.168.137.50:5000")
    print("  Ejemplo Wi-Fi: http://192.168.1.147:5000  (La tuya puede variar)")
    print("="*50 + "\n")
    # ---------------------------------------

    app.run(debug=True, host="0.0.0.0", port=5000)