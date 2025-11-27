# 🤖 S-Robot: Sistema de Control Robótico con IA

![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)
![Python](https://img.shields.io/badge/Python-3.11-yellow.svg)
![Platform](https://img.shields.io/badge/Raspberry%20Pi-4-red.svg)

Este proyecto implementa un servidor web autónomo en una Raspberry Pi 4 para el control de un **Brazo Robótico de 5 GDL** y una **Banda Transportadora**. Utiliza Inteligencia Artificial (TensorFlow Lite) para clasificar objetos en tiempo real y ejecutar decisiones lógicas.

El sistema está diseñado para funcionar como un **Servicio del Sistema (Daemon)**, iniciando automáticamente al encender la Raspberry Pi, con o sin conexión de red.

---

## 📋 Características Principales

* 🌐 **Interfaz Web Responsiva:** Control total desde cualquier dispositivo (PC/Móvil) sin instalar apps.
* 👁️ **Visión Artificial:** Detección de objetos usando modelos TFLite optimizados.
* 🛡️ **Tolerancia a Fallos:** Inicio seguro incluso sin cámara o Arduino conectados.
* 🦾 **Control de Hardware:** Gestión de servos y motores a pasos mediante Arduino + Power Shield.
* 🧠 **Modo Entrenamiento:** Captura de datasets y validación de modelos integrada.
* ⚙️ **Ejecución Continua:** Funciona en segundo plano como servicio de Linux (`systemd`).

---

## 🛠️ Requisitos de Hardware

| Componente | Especificación |
| :--- | :--- |
| **Servidor** | Raspberry Pi 4 (2GB+ RAM) |
| **Microcontrolador** | Arduino Uno/Mega + **Power Shield** |
| **Cámara** | Webcam USB estándar |
| **Actuador 1** | Brazo Robótico (5 Grados de Libertad) |
| **Actuador 2** | Banda Transportadora (Motor a Pasos) |
| **Conectividad** | Cable Ethernet (IP Estática) / Wi-Fi |

---

## 💻 Guía de Conexión Remota

Antes de empezar, verifica la comunicación desde tu PC (Windows).

### 1. Test de Conexión (Windows CMD)
Abre el Símbolo del sistema (`Win + R` -> `cmd`) y ejecuta:
```cmd
ping 192.168.137.50
Si recibes respuesta, la conexión física es correcta.

2. Conectar con VS Code (Recomendado para Programar)
Instala la extensión Remote - SSH (Microsoft).

Presiona F1 -> Remote-SSH: Connect to Host...

Escribe: ssh mps@192.168.137.50

Contraseña: mps123

3. Conectar con PuTTY (Solo Terminal)
Host Name: 192.168.137.50

Port: 22

Type: SSH

🚀 Instalación en Raspberry Pi
Optimizado para Raspberry Pi OS Legacy (64-bit) Lite (Debian Bookworm).

1. Preparar Sistema
Bash

sudo apt update && sudo apt upgrade -y
sudo apt install libgl1 libglib2.0-0 libatlas-base-dev git -y
2. Clonar Repositorio
Bash

git clone [https://github.com/JeanAxon/srobot.git](https://github.com/JeanAxon/srobot.git)
cd srobot
3. Configurar Entorno Virtual
Bash

python3 -m venv venv
source venv/bin/activate
4. Instalar Dependencias
Bash

pip install -r requirements.txt
⚙️ Configuración del Servicio (Arranque Automático)
Para que el robot inicie solo al conectar la energía, configuramos un servicio systemd.

1. Crear archivo de servicio:

Bash

sudo nano /etc/systemd/system/srobot.service
(Pegar el contenido proporcionado en la documentación del proyecto).

2. Activar servicio:

Bash

sudo systemctl enable srobot.service
sudo systemctl start srobot.service
🛠️ Flujo de Trabajo: Modificaciones y Pruebas
⚠️ IMPORTANTE: Como el sistema corre automáticamente en segundo plano, no puedes simplemente editar y dar "Run". Debes seguir este orden para evitar errores de "Puerto ocupado":

Detener el Servicio: sudo systemctl stop srobot.service

Editar código: Realiza tus cambios en VS Code.

Prueba Manual: python app.py (Para ver errores en pantalla).

Reactivar Servicio: sudo systemctl start srobot.service

🔄 Guía de Desarrollo (Git)
Comandos rápidos para mantener tu código sincronizado.

Descargar actualizaciones (En la Raspberry Pi)
Si hiciste cambios en tu PC y quieres traerlos al robot:

Bash

git pull
Subir cambios (Desde Raspberry Pi o PC)
Si modificaste código y quieres guardarlo en GitHub:

Bash

git add .
git commit -m "Describe aquí tu cambio"
git push
🔌 Direcciones de Acceso Web
El servidor escucha en el puerto 5000.

🔸 Opción A: Cable Ethernet (IP Estática)
URL: http://192.168.137.50:5000

🔹 Opción B: Wi-Fi
URL: http://[TU_IP_WIFI]:5000

🚑 Solución de Problemas
Error "Address already in use": El servidor ya está corriendo en segundo plano. Ejecuta sudo systemctl stop srobot.service.

Cámara no detectada: El sistema iniciará en "Modo Sin Video". Revisa el USB y reinicia el servicio.

Git pide contraseña: GitHub requiere un Personal Access Token. Para guardarlo permanentemente: git config --global credential.helper store.