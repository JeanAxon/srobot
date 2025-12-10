# run.py
import sys
import platform
import subprocess
from app import create_app
from app.hardware import robot

# Detectar IP para mostrar en consola (Utilidad visual)
def get_ip_address():
    if platform.system() == "Linux":
        try:
            output = subprocess.check_output(["hostname", "-I"]).decode().strip()
            # Devuelve la primera IP válida encontrada
            return output.split(" ")[0]
        except:
            return "127.0.0.1"
    else:
        # Método compatible con Windows para obtener IP real de red
        try:
            import socket
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return "127.0.0.1"

# Creamos la instancia de la aplicación usando la fábrica
app = create_app()

if __name__ == '__main__':
    # Configuración según README original (Puerto 80 preferido para RPi)
    PORT = 5000
    HOST = '0.0.0.0'
    
    ip_addr = get_ip_address()
    sistema = "Windows (Estudiante)" if platform.system() == "Windows" else "Raspberry Pi (Laboratorio)"
    
    print(f"----------------------------------------")
    print(f"🤖 S-Robot Iniciado en modo: {sistema}")
    print(f"🌍 Panel de Control: http://{ip_addr}:{PORT}")
    print(f"----------------------------------------")
    
    try:
        # IMPORTANTE: use_reloader=False evita que Flask cree un proceso hijo.
        # Esto es vital cuando iniciamos hilos de hardware (Serial/Cámara) en el arranque,
        # para evitar que se inicien dos veces y causen conflictos de "Access Denied".
        app.run(host=HOST, port=PORT, debug=True, use_reloader=False)
        
    except PermissionError:
        # Si no tenemos permisos de root en Linux para puerto 80, fallback a 5000
        print(f"⚠️  Permiso denegado en puerto {PORT}. Intentando en puerto 5000...")
        print(f"🌍 Nuevo Panel de Control: http://{ip_addr}:5000")
        app.run(host=HOST, port=5000, debug=True, use_reloader=False)
        
    finally:
        # Paridad con app.py original: Limpieza segura al salir (Ctrl+C)
        print("\n🛑 Cerrando la aplicación y liberando recursos...")
        
        if robot.modbus:
            robot.modbus.stop()
            print("✅ Conexión Modbus cerrada.")
            
        if robot.serial_port and robot.serial_port.is_open:
            robot.serial_port.close()
            print("✅ Puerto Serie cerrado.")
            
        # Liberamos recursos del brazo y banda si tienen métodos de limpieza
        # (Depende de tus módulos internos, pero es buena práctica)
        print("👋 S-Robot finalizado correctamente.")