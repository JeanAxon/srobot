# app/__init__.py
from flask import Flask
from app.hardware import robot, resource_path

def create_app():
    """
    Fábrica de Aplicación: Inicializa Flask con rutas compatibles para .exe y Hardware.
    """
    
    # 1. Definimos las rutas absolutas usando resource_path.
    # Esto asegura que Flask encuentre los HTML/CSS incluso dentro del .exe compilado.
    template_dir = resource_path('templates')
    static_dir = resource_path('static')

    # 2. Inicializamos Flask pasando explícitamente estas carpetas
    app = Flask(__name__, 
                template_folder=template_dir, 
                static_folder=static_dir)
    
    app.secret_key = 'your_secret_key'

    # 3. Inicializamos el hardware
    # Usamos app_context para que cualquier error de inicio quede registrado
    with app.app_context():
        # Inicializa conexiones físicas y carga config.json
        robot.initialize_hardware()
        robot.load_config()

    # 4. Registramos los Blueprints (Rutas)
    # Importamos aquí para evitar importaciones circulares
    from app.routes_web import web_bp
    from app.routes_api import api_bp
    
    app.register_blueprint(web_bp)
    app.register_blueprint(api_bp)

    return app