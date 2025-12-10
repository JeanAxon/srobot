# app/hardware.py
import os
import sys
import json
import platform
import logging
import cv2
import threading
import subprocess

# --- Importaciones de tus módulos de hardware ---
from modulos.banda_transportadora import BandaTransportadora
from modulos.brazo_robotico import BrazoRobotico
from modulos.com_modbus import ModbusBridge # Corregido: en tu original era com_modbusTCP

# --- Configuración de Entorno ---
IS_WINDOWS = platform.system() == "Windows"
IS_LINUX = platform.system() == "Linux"
CONFIG_FILE = "config.json" # Puedes mantenerlo o usar estado.json si prefieres la compatibilidad total

# --- Selección del Backend de IA ---
TFLITE_BACKEND = None
try:
    if IS_WINDOWS:
        import tensorflow as tf
        TFLITE_BACKEND = "tensorflow"
    else:
        import tflite_runtime.interpreter as tflite
        TFLITE_BACKEND = "tflite_runtime"
except ImportError:
    try:
        import tensorflow as tf
        TFLITE_BACKEND = "tensorflow"
    except ImportError:
        print("ADVERTENCIA: No se encontró backend de TensorFlow/TFlite.")

# --- FUNCIONES CRÍTICAS DE RUTAS (Restauradas del original) ---

def resource_path(relative_path):
    """
    Obtiene la ruta absoluta a un recurso de SOLO LECTURA (modelos, templates).
    Vital para que funcione cuando se congela con PyInstaller.
    """
    try:
        # PyInstaller crea una carpeta temporal y guarda la ruta en _MEIPASS
        base_path = sys._MEIPASS
    except AttributeError:
        # Modo desarrollo
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def app_data_path(filename):
    """
    Obtiene la ruta a archivos que el usuario ESCRIBE (fotos, movimientos, config).
    Se guarda junto al ejecutable o en la raíz en desarrollo.
    """
    if getattr(sys, 'frozen', False):
        # Estamos ejecutando como un .exe empaquetado
        application_path = os.path.dirname(sys.executable)
    else:
        # Estamos ejecutando en modo desarrollo
        application_path = os.path.abspath(".")
    return os.path.join(application_path, filename)

# --- Clase Gestora de Hardware (Singleton) ---
class RobotContext:
    def __init__(self):
        # Hardware
        self.arm = None
        self.conveyor = None
        self.modbus = None
        self.serial_port = None
        
        # IA y Modelos
        self.color_model = None
        self.shape_model = None
        # Necesitamos las etiquetas también para paridad con el original
        self.color_labels = [] 
        self.shape_labels = []
        
        # Estado de la Aplicación
        self.fps = 0
        self.current_frame = None
        self.total_objects = 0
        self.total_circles = 0
        self.last_classification = ""
        
        # Configuración persistente
        self.config_data = {
            "latest_objects": 0,
            "latest_fps": 0,
            "latest_classification": "",
            "latest_circles": 0,
            "latest_area": 0,
            "latest_position": {
                "max_object_distance": 100,
                "modbus_ip": "127.0.0.1",
                "modbus_port": 5020
            }
        }
        
        self.load_config()

    def load_config(self):
        path = app_data_path(CONFIG_FILE)
        if os.path.exists(path):
            try:
                with open(path, 'r') as f:
                    self.config_data.update(json.load(f))
            except Exception as e:
                logging.error(f"Error cargando config: {e}")

    def save_config(self):
        path = app_data_path(CONFIG_FILE)
        try:
            with open(path, 'w') as f:
                json.dump(self.config_data, f, indent=4)
        except Exception as e:
            logging.error(f"Error guardando config: {e}")

    def initialize_hardware(self):
        logging.info("Inicializando Hardware...")
        try:
            # Inicializamos objetos base (sin conexión serial aún)
            self.arm = BrazoRobotico()
            self.conveyor = BandaTransportadora()
            logging.info("Instancias de hardware creadas.")
            
            # Inicializar Modbus automáticamente si estaba configurado
            self.initialize_modbus()
            
            # Cargar modelos automáticamente
            self.load_models()
            
        except Exception as e:
            logging.error(f"Error inicializando hardware: {e}")

    def initialize_modbus(self):
        ip = self.config_data['latest_position'].get('modbus_ip', '127.0.0.1')
        port = self.config_data['latest_position'].get('modbus_port', 502)
        try:
            if self.modbus:
                self.modbus.stop() # El original usaba .stop() no .close()
            self.modbus = ModbusBridge(ip, port) # Asumiendo constructor con IP/Puerto o default
            self.modbus.start()
            logging.info(f"Modbus iniciado.")
        except Exception as e:
            logging.error(f"Error Modbus: {e}")

    def load_models(self):
        """Carga modelos usando resource_path para compatibilidad con .exe"""
        # Usamos resource_path para encontrar los modelos dentro del empaquetado o carpeta source
        form_model_path = resource_path('uploads/model_form/model_unquant.tflite')
        color_model_path = resource_path('uploads/model_color/model_unquant.tflite')
        form_labels_path = resource_path('uploads/model_form/labels.txt')
        color_labels_path = resource_path('uploads/model_color/labels.txt')

        self.shape_model = self._load_single_model(form_model_path)
        self.color_model = self._load_single_model(color_model_path)
        
        # Cargar etiquetas (labels)
        if os.path.exists(form_labels_path):
            with open(form_labels_path, 'r', encoding='utf-8') as f:
                self.shape_labels = f.read().splitlines()
        if os.path.exists(color_labels_path):
            with open(color_labels_path, 'r', encoding='utf-8') as f:
                self.color_labels = f.read().splitlines()

    def _load_single_model(self, path):
        if not os.path.exists(path):
            logging.warning(f"Modelo no encontrado en: {path}")
            return None
        try:
            if TFLITE_BACKEND == "tensorflow":
                interpreter = tf.lite.Interpreter(model_path=path)
            elif TFLITE_BACKEND == "tflite_runtime":
                interpreter = tflite.Interpreter(model_path=path)
            else:
                return None
            interpreter.allocate_tensors()
            return interpreter
        except Exception as e:
            logging.error(f"Error cargando modelo {path}: {e}")
            return None

    def get_camera(self):
        """
        Lógica robusta de recuperación de cámara (Paridad con app.py original)
        """
        if IS_LINUX:
            # Lógica Linux original
            try:
                subprocess.check_output(['fuser', '/dev/video0'], stderr=subprocess.DEVNULL)
                # Ojo: el original mataba procesos aquí con kill -9, simplificado por seguridad
            except: pass
            
            # Intentar abrir dispositivos
            for device in ["/dev/video0", "/dev/video1", 0, 1]:
                cap = cv2.VideoCapture(device)
                if cap.isOpened():
                    # Configuraciones v4l2 del original
                    os.system(f"v4l2-ctl -d {device} -c focus_automatic_continuous=0")
                    os.system(f"v4l2-ctl -d {device} -c focus_absolute=100")
                    return cap
            return None
            
        else: # WINDOWS
            # Lógica Windows original: Iterar hacia atrás para encontrar la mejor cámara
            for i in range(5, -1, -1):
                cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
                if cap.isOpened():
                    logging.info(f"Cámara Windows inicializada en índice {i}")
                    return cap
            return None

# Instancia Global
robot = RobotContext()