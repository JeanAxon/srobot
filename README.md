# 🤖 S-Robot: Sistema de Control Robótico con IA

![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)
![Python](https://img.shields.io/badge/Python-3.11-yellow.svg)
![Platform](https://img.shields.io/badge/Raspberry%20Pi-4-red.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

Este proyecto implementa un servidor web autónomo en una **Raspberry Pi 4** para el control de un **Brazo Robótico de 5 GDL** y una **Banda Transportadora**. Utiliza Inteligencia Artificial (**TensorFlow Lite**) para clasificar objetos en tiempo real y ejecutar decisiones lógicas basadas en visión artificial.

El sistema está diseñado para funcionar como un **Servicio del Sistema (Daemon)**, iniciando automáticamente al encender la Raspberry Pi, asegurando robustez con o sin conexión de red.



---

## 📋 Características Principales

* 🌐 **Interfaz Web Responsiva:** Panel de control total accesible desde cualquier navegador (PC/Móvil) sin instalar aplicaciones.
* 👁️ **Visión Artificial:** Detección de objetos en el borde (Edge AI) usando modelos TFLite optimizados.
* 🛡️ **Tolerancia a Fallos:** Arquitectura defensiva que permite el inicio seguro incluso si la cámara o el Arduino están desconectados.
* 🦾 **Control de Hardware:** Orquestación de servos y motores a pasos mediante comunicación serial con **Arduino + Power Shield**.
* 🧠 **Modo Entrenamiento:** Herramientas integradas para captura de datasets y validación de modelos.
* ⚙️ **Ejecución Continua:** Funciona en segundo plano como servicio nativo de Linux (`systemd`).

---

## 🛠️ Requisitos de Hardware

| Componente | Especificación |
| :--- | :--- |
| **Servidor** | Raspberry Pi 4 (Recomendado 2GB+ RAM) |
| **Microcontrolador** | Arduino Uno/Mega + **Power Shield** |
| **Cámara** | Webcam USB estándar (Logitech C270 o similar) |
| **Actuador 1** | Brazo Robótico (5 Grados de Libertad) |
| **Actuador 2** | Banda Transportadora (Motor a Pasos NEMA) |
| **Conectividad** | Cable Ethernet (IP Estática) / Wi-Fi |

---

## 💻 Guía de Conexión Remota

Antes de empezar, verifica la comunicación desde tu PC (Windows).

### 1. Test de Conexión (Windows CMD)
Abre el Símbolo del sistema (`Win + R` -> `cmd`) y ejecuta:
```cmd
ping 192.168.137.50
Nota: Si recibes respuesta (bytes=32 time<1ms), la conexión física es correcta.2. Conectar con VS Code (Recomendado para Desarrollo)Instala la extensión Remote - SSH de Microsoft.Presiona F1 -> Selecciona Remote-SSH: Connect to Host...Escribe: ssh mps@192.168.137.50Contraseña: mps1233. Conectar con PuTTY (Solo Terminal)Host Name: 192.168.137.50Port: 22Type: SSH🚀 Instalación en Raspberry PiOptimizado para Raspberry Pi OS Legacy (64-bit) Lite (Debian Bookworm).1. Preparar SistemaInstala las librerías necesarias para OpenCV y compilación:Bashsudo apt update && sudo apt upgrade -y
sudo apt install libgl1 libglib2.0-0 libatlas-base-dev git -y
2. Clonar RepositorioBashgit clone [https://github.com/JeanAxon/srobot.git](https://github.com/JeanAxon/srobot.git)
cd srobot
3. Configurar Entorno VirtualEs buena práctica aislar las dependencias de Python:Bashpython3 -m venv venv
source venv/bin/activate
4. Instalar DependenciasBashpip install -r requirements.txt
⚙️ Configuración del Servicio (Arranque Automático)Para que el robot inicie solo al conectar la energía, configuramos un servicio systemd.1. Crear archivo de servicioBashsudo nano /etc/systemd/system/srobot.service
Pega el siguiente contenido (ajusta la ruta /home/mps/srobot si tu usuario es diferente):Ini, TOML[Unit]
Description=S-Robot Control System
After=network.target

[Service]
User=mps
WorkingDirectory=/home/mps/srobot
ExecStart=/home/mps/srobot/venv/bin/python3 /home/mps/srobot/app.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
2. Activar servicioBashsudo systemctl daemon-reload
sudo systemctl enable srobot.service
sudo systemctl start srobot.service
🛠️ Flujo de Trabajo: Modificaciones y Pruebas⚠️ IMPORTANTE: El sistema corre automáticamente en segundo plano. No puedes simplemente editar y dar "Run" o tendrás errores de "Puerto ocupado".Sigue este orden estricto para desarrollar:Detener el Servicio: Libera la cámara y el puerto web.Bashsudo systemctl stop srobot.service
Editar código: Realiza tus cambios en VS Code.Prueba Manual: Ejecuta manualmente para ver errores en consola.Bashsource venv/bin/activate
python app.py
(Presiona Ctrl + C para detener cuando termines).Reactivar Servicio: Para dejarlo funcionando autónomamente.Bashsudo systemctl start srobot.service
🔄 Guía de Desarrollo (Git)Comandos rápidos para mantener tu código sincronizado.⬇️ Descargar actualizaciones (En la Raspberry Pi)Si hiciste cambios en tu PC y quieres traerlos al robot:Bashgit pull
⬆️ Subir cambios (Desde Raspberry Pi o PC)Si modificaste código y quieres guardarlo en GitHub:Bashgit add .
git commit -m "Descripción de tu cambio"
git push
🔌 Direcciones de Acceso WebEl servidor escucha por defecto en el puerto 5000.🔸 Opción A: Cable Ethernet (IP Estática)URL: http://192.168.137.50:5000🔹 Opción B: Wi-FiURL: http://[TU_IP_WIFI]:5000🚑 Solución de ProblemasErrorCausa ProbableSoluciónAddress already in useEl servicio sigue corriendo en fondo.Ejecuta sudo systemctl stop srobot.service.Cámara no detectadaUSB desconectado o bloqueado.El sistema iniciará en "Modo Sin Video". Revisa el USB y reinicia el servicio.Git pide contraseñaFalta token de acceso.Configura el helper: git config --global credential.helper store.