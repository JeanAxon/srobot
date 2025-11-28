🤖 S-Robot: Plataforma Educativa de Robótica Híbrida

Este proyecto implementa un sistema híbrido de control robótico educativo. Permite controlar un Brazo Robótico de 5 GDL y una Banda Transportadora utilizando visión artificial (TensorFlow Lite), cinemática inversa y comunicación industrial (Modbus TCP).

🏗️ Arquitectura del Sistema

El sistema utiliza una Arquitectura de Doble Entrada para facilitar tanto el aprendizaje seguro como el despliegue industrial:

Entorno Estudiante (Windows):

Archivo: ServidorMPS.py

Función: Aplicación de escritorio con interfaz gráfica (GUI) moderna. Permite simular la lógica, generar trayectorias y probar algoritmos de visión sin riesgo de dañar el hardware real.

Objetivo: Experimentación segura y desarrollo de algoritmos.

Entorno Laboratorio (Raspberry Pi):

Archivo: app.py (ejecutado automáticamente).

Función: Servidor "Headless" (sin monitor) optimizado para rendimiento. Controla los GPIOs, la cámara USB y la comunicación serial con el Arduino en tiempo real.

Objetivo: Control físico y producción.

📂 Diccionario de Archivos y Carpetas

Guía para entender la estructura del proyecto:

🔴 Principales

app.py: (Solo Pi) Servidor Flask principal. Gestiona la cámara, hilos y rutas web.

ServidorMPS.py: (Solo Windows) Interfaz gráfica que envuelve el servidor para facilitar el uso en PC.

requirements_windows.txt: Librerías para PC (incluye GUI, OpenCV full).

requirements_rpi.txt: Librerías optimizadas para Pi (headless, sin GUI).

🔵 Lógica (/modulos)

reconocimiento.py: Procesa la imagen y usa TFLite para detectar color/forma.

ejecucion.py: Máquina de estados que controla el ciclo automático (Banda -> Cámara -> Brazo).

cinematica_inversa.py: Algoritmo CCD para calcular ángulos de servos desde coordenadas (X,Y,Z).

cinematica_inversa_local.py: Algoritmo alternativo usando scipy.optimize.

generador_trayectoria.py: Crea movimientos suaves (Splines) entre dos puntos.

🟢 Hardware (/modulos)

brazo_robotico.py: Envía comandos seriales (A,90...) al Arduino.

banda_transportadora.py: Controla el motor de la banda (P, A).

com_modbus.py: Puente para conectar con PLCs industriales.

📂 Carpetas de Datos y Firmware

uploads/: Directorio de almacenamiento. Aquí se guardan automáticamente las fotos capturadas para entrenamiento y los modelos .tflite subidos desde la web.

movimientos/: Almacena las secuencias de movimiento creadas por el usuario en formato .txt.

Servo_Motor/: Contiene el código fuente del Arduino (Servo_Motor.ino). Sirve como respaldo y permite modificar el comportamiento de bajo nivel del microcontrolador (velocidades máximas, aceleración) cargándolo directamente desde la Pi.

📄 Configuración

logica_config.json: Base de datos de reglas automáticas (Ej: "Si veo [Círculo Azul] -> Ejecutar [Movimiento B]").

estado.json: Guarda la última posición conocida de los servos y la velocidad para no perder la calibración al reiniciar.

🔌 Parte 1: Conexión Inicial (Obligatorio Ethernet)

⚠️ IMPORTANTE: Para la primera conexión, o si cambias de red, usa siempre el cable Ethernet.

1. Preparar tu PC (Windows)

Configura tu computadora para compartir internet con el robot (ICS). Esto asigna la IP correcta al robot.

Conecta tu PC al Wi-Fi.

Presiona Win + R, escribe ncpa.cpl y pulsa Enter.

Clic derecho en tu adaptador Wi-Fi -> Propiedades -> Pestaña Uso compartido.

Marca "Permitir que los usuarios de otras redes se conecten...".

En "Conexión de red doméstica", selecciona tu adaptador Ethernet.

Acepta.

🚑 Solución: ¿Problemas al conectar después de reiniciar?

Si apagas la PC y al volver no conecta, Windows suele "congelar" el servicio de compartir.

Vuelve a ncpa.cpl -> Propiedades Wi-Fi -> Uso compartido.

DESMARCA la casilla y acepta.

Espera 5 segundos.

VUELVE A MARCARLA y acepta.

Esto reinicia el servidor DHCP de Windows.

2. Verificar Conexión

Conecta el cable Ethernet.

Abre cmd y ejecuta:

ping 192.168.137.50


(Si responde, estás listo. Si no, intenta ping mps.local).

3. Diagnóstico con PuTTY

Usa PuTTY para verificar el estado interno y obtener la IP del Wi-Fi.

Host: 192.168.137.50 | Port: 22 | Type: SSH

Usuario: mps

Contraseña: mps123

Comandos Útiles en PuTTY:

ip -c a: Muestra las IPs. Anota la IP de wlan0 si quieres conectarte por Wi-Fi luego.

sudo systemctl status srobot.service: Verifica si el robot está corriendo.

ping -c 2 8.8.8.8: Verifica si el robot tiene internet.

💻 Parte 2: Entorno de Desarrollo (Windows)

Pasos para que el estudiante instale el simulador en su propia PC.

1. Requisitos Previos

Tener instalado Git y Python 3.11.

Tener instalado VS Code.

2. Clonar el Repositorio

Crea una carpeta en tu escritorio.

Abre una terminal ahí y ejecuta:

git clone [https://github.com/JeanAxon/srobot.git](https://github.com/JeanAxon/srobot.git)
cd srobot


3. Configurar Entorno

# Crear entorno virtual
python -m venv venv
.\venv\Scripts\activate

# Instalar dependencias completas (Versión Windows con GUI)
pip install -r requirements_windows.txt


4. Ejecutar Simulador

python ServidorMPS.py


Se abrirá el Panel de Control. Puedes probar la lógica y generar archivos de movimiento aquí.

🚀 Parte 3: Programación en el Robot (VS Code Remoto)

Cómo cargar y probar tu código en la Raspberry Pi sin romper la configuración.

1. Configurar SSH en VS Code

Instala la extensión Remote - SSH.

Clic en el icono verde >< -> "Open SSH Configuration File...".

Copia y pega esto al final del archivo (Evita errores de huella/fingerprint):

# Conexión Segura por Cable
Host Robot-Cable
    HostName 192.168.137.50
    User mps
    StrictHostKeyChecking no
    UserKnownHostsFile /dev/null

# Conexión por Wi-Fi (IP Variable, revísala en PuTTY)
Host Robot-Wifi
    HostName 192.168.1.XX
    User mps
    StrictHostKeyChecking no
    UserKnownHostsFile /dev/null


2. Cargar y Editar

Conéctate a Robot-Cable. Introduce la contraseña mps123.

Puedes editar los archivos directamente.

O arrastrar tus archivos modificados desde Windows a la carpeta /home/mps/srobot (sobrescribir).

⚠️ Protocolo de Prueba (Obligatorio)

El servicio automático bloquea la cámara y el puerto. Sigue este orden:

DETENER SERVICIO: En la terminal de VS Code:

sudo systemctl stop srobot.service


EJECUTAR MANUALMENTE: (Verás los errores en tiempo real)

source venv/bin/activate
python app.py


(Presiona Ctrl+C para detener la prueba manual).

REACTIVAR: Al terminar la clase, deja el robot listo:

sudo systemctl start srobot.service


👨‍🏫 Parte 4: Gestión del Repositorio (Guía para el Profesor)

Comandos para actualizar la Raspberry Pi con cambios del repositorio remoto o subir cambios locales al repositorio.

Actualizar la Pi desde el Repositorio (Descargar cambios)

Si has actualizado el código en GitHub desde tu PC y quieres que la Raspberry Pi tenga la última versión:

Conéctate a la Pi (por SSH en VS Code o PuTTY).

Ve a la carpeta del proyecto:

cd ~/srobot


Descarga los cambios:

git pull


(Si hay conflictos locales, git te avisará. Si solo quieres sobrescribir todo con lo del repositorio, usa el Botón de Pánico abajo).

Si hubo cambios en las librerías, actualízalas:

source venv/bin/activate
pip install -r requirements_rpi.txt


Reinicia el servicio para aplicar los cambios:

sudo systemctl restart srobot.service


Subir Cambios desde la Pi al Repositorio (Cargar cambios)

Si hiciste correcciones directamente en la Raspberry Pi y quieres guardarlas en GitHub:

Verifica qué archivos has modificado:

git status


Añade los archivos al "paquete" de subida:

git add .


Guarda el paquete con un mensaje descriptivo:

git commit -m "Descripción de los cambios realizados en la Pi"


Sube los cambios a GitHub:

git push


(Te pedirá usuario y contraseña/token si no has configurado el guardado de credenciales).

🔁 Parte 5: Botón de Pánico (Restauración)

Este repositorio actúa como la "Imagen Maestra". Si modificas el código en la Pi y el sistema deja de funcionar, NO INTENTES ARREGLARLO MANUALMENTE.

Ejecuta estos comandos en la terminal de la Raspberry Pi para volver a la versión original del profesor:

cd ~/srobot
git fetch origin
git reset --hard origin/main


*El sistema descargará el código original de GitHub y descartará tus cambios locales