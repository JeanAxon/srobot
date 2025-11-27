# 🤖 S-Robot: Sistema de Control Robótico con IA

![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)
![Python](https://img.shields.io/badge/Python-3.11-yellow.svg)
![Platform](https://img.shields.io/badge/Raspberry%20Pi-4-red.svg)

Sistema autónomo en Raspberry Pi 4 para controlar un **Brazo Robótico (5 GDL)** y una **Banda Transportadora** mediante clasificación de imágenes con TensorFlow Lite.

---

## 📡 Fase 1: Verificación de Red (Windows CMD)
*Antes de intentar conectarte, verifica que tu PC ve a la Raspberry Pi a través del cable Ethernet o Wi-Fi.*

1. Conecta el cable Ethernet o asegúrate de estar en la misma red Wi-Fi.
2. Abre el Símbolo del Sistema en Windows (`Win + R` -> `cmd`).
3. Ejecuta el ping:

```cmd
ping 192.168.137.50
✅ Éxito: Si recibes Respuesta desde 192.168.137.50: bytes=32 tiempo<1m, pasa a la Fase 2.❌ Fallo: Si dice "Tiempo de espera agotado" o "Host inaccesible", revisa tu cable Ethernet o la IP estática en Windows.📟 Fase 2: Acceso por Terminal (PuTTY)Utiliza esta opción si solo necesitas reiniciar el servicio, apagar la Raspberry o ejecutar comandos rápidos sin interfaz gráfica.Host Name (or IP address): 192.168.137.50Port: 22Connection type: SSHAl conectar, usa las credenciales:User: mpsPassword: mps123💻 Fase 3: Entorno de Desarrollo (VS Code)Recomendado para editar código (app.py, brazo.py) directamente en la Raspberry Pi desde tu PC.Instala la extensión Remote - SSH en VS Code.Presiona F1 y busca: Remote-SSH: Connect to Host...Ingresa el comando de conexión:Bashssh mps@192.168.137.50
Ingresa la contraseña (mps123) cuando se solicite.Abre la carpeta del proyecto: /home/mps/srobot.🐙 Gestión de Versiones y Actualizaciones (Git)Comandos para ejecutar dentro de la Raspberry Pi (vía PuTTY o Terminal de VS Code) para gestionar el código.📥 Actualizar a la última versiónSi subiste cambios desde otra PC y quieres descargarlos en el robot:Bashcd /home/mps/srobot
git pull origin main
🔄 Cambiar de Versión (Rama/Tag)Si necesitas volver a una versión anterior o probar una rama de desarrollo:Bash# Ver lista de ramas disponibles
git branch -a

# Cambiar a una rama especifica
git checkout nombre-de-la-rama
🧐 Verificar estado actualPara saber si modificaste algo localmente o en qué versión estás:Bashgit status
git log --oneline -n 5
⚙️ Gestión del Servicio (Daemon)El robot funciona como un servicio de fondo. Usa estos comandos para controlarlo.AcciónComandoDetener Robot (Para editar código)sudo systemctl stop srobot.serviceIniciar Robot (Modo producción)sudo systemctl start srobot.serviceVer Logs (Ver errores/prints)journalctl -u srobot.service -fReiniciarsudo systemctl restart srobot.service🚀 Instalación desde Cero (Solo nueva SD)Si necesitas instalar todo en una Raspberry Pi limpia (Debian Bookworm 64-bit):1. Instalar dependencias del sistema:Bashsudo apt update && sudo apt upgrade -y
sudo apt install libgl1 libglib2.0-0 libatlas-base-dev git -y
2. Clonar y configurar Python:Bashgit clone [https://github.com/JeanAxon/srobot.git](https://github.com/JeanAxon/srobot.git)
cd srobot
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
3. Instalar Servicio de Auto-Arranque:Bash# Editar ruta si es necesario dentro del archivo srobot.service
sudo cp srobot.service /etc/systemd/system/
sudo systemctl enable srobot.service
sudo systemctl start srobot.service

### Cambios realizados para arreglar tu problema visual:
1.  **Bloques de Código Fenced:** Usé las tres tildes ( \`\`\` ) estrictamente separadas del texto por líneas en blanco. Esto evita que el texto se "coma" el código como pasaba en tu imagen.
2.  **Jerarquía Clara:** Usé "Fase 1", "Fase 2", etc., para que el lector entienda que son métodos distintos de conexión, no pasos consecutivos obligatorios.
3.  **Sección Git Aislada:** Ahora los comandos de git (`pull`, `checkout`, `status`) 