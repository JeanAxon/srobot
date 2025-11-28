🤖 S-Robot: Plataforma Educativa de Robótica Híbrida

S-Robot es una plataforma educativa de robótica que implementa un sistema híbrido de control. Permite operar un brazo robótico de 5 grados de libertad (5 GDL) y una banda transportadora, integrando visión artificial (TensorFlow Lite), cinemática inversa y comunicación industrial (Modbus TCP).

🏗️ Arquitectura del Sistema

El sistema utiliza una arquitectura de doble entorno, diseñada para facilitar tanto el aprendizaje seguro como el despliegue en un entorno de laboratorio.

🖥️ Entorno Estudiante (Windows)

Archivo principal: ServidorMPS.py

Descripción: Aplicación de escritorio con interfaz gráfica (GUI).
Permite simular la lógica del sistema, generar trayectorias y probar algoritmos de visión sin interactuar físicamente con el hardware.

Objetivo principal: Proveer un entorno de experimentación segura para el desarrollo y prueba de algoritmos.

🍓 Entorno Laboratorio (Raspberry Pi)

Archivo principal: app.py (ejecución automática mediante servicio del sistema).

Descripción: Servidor headless (sin monitor) optimizado para rendimiento.
Controla los GPIO, la cámara USB y la comunicación serial con el microcontrolador (Arduino) en tiempo real.

Objetivo principal: Operación física del sistema en entorno real de laboratorio.

📂 Estructura de Archivos y Carpetas

A continuación se describe la estructura general del proyecto y el propósito de los archivos principales.

🔴 Archivos Principales

app.py (Raspberry Pi):
Servidor Flask principal. Gestiona la cámara, los hilos de ejecución y las rutas web.

ServidorMPS.py (Windows):
Interfaz gráfica de usuario que encapsula la lógica del servidor para su uso en PC.

requirements_windows.txt:
Lista de dependencias para entorno Windows (incluye GUI y versión completa de OpenCV).

requirements_rpi.txt:
Lista de dependencias optimizadas para Raspberry Pi (modo headless, sin GUI).

🔵 Módulos de Lógica (/modulos)

reconocimiento.py:
Procesa imágenes y utiliza TensorFlow Lite para la detección de color y forma.

ejecucion.py:
Implementa la máquina de estados que controla el ciclo automático
(banda transportadora → captura de imagen → brazo robótico).

cinematica_inversa.py:
Implementa un algoritmo por CCD (Cyclic Coordinate Descent) para calcular los ángulos de los servos a partir de coordenadas cartesianas (X, Y, Z).

cinematica_inversa_local.py:
Variante del cálculo de cinemática inversa utilizando scipy.optimize.

generador_trayectoria.py:
Genera trayectorias suaves (por ejemplo, mediante splines) entre puntos de posición.

🟢 Módulos de Hardware (/modulos)

brazo_robotico.py:
Envía comandos seriales (por ejemplo, A,90...) al Arduino para el control del brazo robótico.

banda_transportadora.py:
Controla el motor de la banda transportadora mediante comandos específicos (por ejemplo, P, A).

com_modbus.py:
Implementa la comunicación Modbus TCP para la integración con PLCs industriales.

📁 Carpetas de Datos y Firmware

uploads/:
Directorio de almacenamiento de datos.
Se utiliza para guardar automáticamente las imágenes capturadas para entrenamiento y los modelos .tflite cargados desde la interfaz web.

movimientos/:
Almacena las secuencias de movimiento generadas por el usuario en archivos de texto (.txt).

Servo_Motor/:
Contiene el código fuente del microcontrolador Arduino (Servo_Motor.ino).
Sirve como respaldo y base para modificar el comportamiento de bajo nivel (por ejemplo, velocidades máximas y aceleraciones), pudiendo cargarse directamente desde la Raspberry Pi.

📄 Archivos de Configuración

logica_config.json:
Define las reglas de automatización del sistema.
Ejemplo: "Si se detecta [Círculo Azul] -> ejecutar [Movimiento B]".

estado.json:
Almacena la última posición conocida de los servomotores y las velocidades, con el fin de mantener la calibración entre reinicios del sistema.

🔌 Parte 1: Conexión Inicial (Uso de Ethernet)

⚠️ Para la primera configuración, o cuando se cambia la red de trabajo, se recomienda utilizar siempre conexión por cable Ethernet.

1. Preparación del PC (Windows)

Para conectar la Raspberry Pi a través de la PC, se utiliza Internet Connection Sharing (ICS) de Windows. Esto permite asignar una dirección IP adecuada a la Raspberry Pi.

Pasos generales:

Conectar el PC a la red Wi-Fi.

Abrir el cuadro Ejecutar con Win + R, escribir ncpa.cpl y pulsar Enter.

Hacer clic derecho sobre el adaptador Wi-Fi y seleccionar Propiedades.

Ir a la pestaña Uso compartido.

Activar la opción
“Permitir que los usuarios de otras redes se conecten a través de la conexión a Internet de este equipo”.

En “Conexión de red doméstica”, seleccionar el adaptador Ethernet.

Confirmar los cambios.

Reinicio del servicio de compartición (en caso de fallo tras reiniciar)

En algunos casos, después de reiniciar el PC, el servicio de compartición de internet puede quedar inestable.

Para restablecerlo:

Volver a abrir ncpa.cpl.

Abrir Propiedades del adaptador Wi-Fi y acceder a la pestaña Uso compartido.

Desmarcar la casilla de uso compartido y aceptar.

Esperar unos segundos.

Volver a marcar la casilla y aceptar.

Con esto se reinicia el servicio DHCP que asigna la dirección IP a la Raspberry Pi.

2. Verificación de Conectividad

Conectar el cable Ethernet entre el PC y la Raspberry Pi.

Abrir una terminal de comandos (cmd) en Windows.

Ejecutar:

ping 192.168.137.50


Si no se obtiene respuesta, se puede intentar:

ping mps.local

3. Diagnóstico con PuTTY

Para comprobar el estado interno del sistema y obtener información de red, se puede utilizar PuTTY.

Parámetros de conexión:

Host: 192.168.137.50

Puerto: 22

Tipo: SSH

Usuario: mps

Contraseña: mps123

Comandos útiles:

ip -c a


Muestra las direcciones IP de las interfaces de red.
La IP de wlan0 puede utilizarse para conexiones posteriores por Wi-Fi.

sudo systemctl status srobot.service


Verifica el estado del servicio principal del robot.

ping -c 2 8.8.8.8


Comprueba la conectividad a internet desde la Raspberry Pi.

💻 Parte 2: Entorno de Desarrollo (Windows)

Esta sección describe cómo configurar el entorno de simulación en un equipo con Windows para uso del estudiante.

1. Requisitos Previos

Git instalado.

Python 3.11 instalado.

Visual Studio Code (VS Code) instalado.

2. Clonado del Repositorio

En una carpeta de trabajo (por ejemplo, en el escritorio), se recomienda:

git clone https://github.com/JeanAxon/srobot.git
cd srobot

3. Creación del Entorno Virtual e Instalación de Dependencias
# Crear entorno virtual
python -m venv venv

# Activar entorno virtual (Windows)
.\venv\Scripts\activate

# Instalar dependencias para Windows (con GUI)
pip install -r requirements_windows.txt

4. Ejecución del Simulador
python ServidorMPS.py


Al ejecutar este comando, se abrirá el panel de control de la aplicación.
Desde allí, es posible probar la lógica, simular trayectorias y generar archivos de movimiento sin utilizar el hardware real.

🚀 Parte 3: Programación sobre la Raspberry Pi (VS Code Remoto)

Esta sección describe el procedimiento para editar y probar el código directamente en la Raspberry Pi utilizando VS Code Remote - SSH, manteniendo la configuración del sistema bajo control.

1. Configuración de SSH en VS Code

Instalar la extensión Remote - SSH en VS Code.

Abrir la configuración de SSH desde el icono verde >< → “Open SSH Configuration File…”.

Añadir las siguientes entradas al archivo de configuración:

# Conexión segura por cable
Host Robot-Cable
    HostName 192.168.137.50
    User mps
    StrictHostKeyChecking no
    UserKnownHostsFile /dev/null

# Conexión por Wi-Fi (IP variable, consultar en PuTTY)
Host Robot-Wifi
    HostName 192.168.1.XX
    User mps
    StrictHostKeyChecking no
    UserKnownHostsFile /dev/null


La IP correspondiente a Robot-Wifi debe consultarse mediante el comando ip -c a en la Raspberry Pi (interfaz wlan0).

2. Edición y Transferencia de Archivos

Una vez configurada la conexión:

Es posible conectarse a Robot-Cable desde VS Code introduciendo la contraseña mps123.

Los archivos del proyecto ubicados en /home/mps/srobot pueden:

Editarse directamente desde VS Code, o

Sustituirse arrastrando archivos desde Windows a dicha carpeta.

⚠️ Protocolo de Pruebas en la Raspberry Pi

El servicio principal del sistema utiliza la cámara y el puerto serie.
Para realizar pruebas manuales sin conflicto de recursos, se recomienda seguir el siguiente orden:

1. Detener el servicio
sudo systemctl stop srobot.service

2. Ejecutar la aplicación de forma manual
source venv/bin/activate
python app.py


De esta forma es posible observar en la consola los errores o mensajes de depuración en tiempo real.
La ejecución puede detenerse con Ctrl + C.

3. Reactivar el servicio al finalizar
sudo systemctl start srobot.service


Con esto, el sistema queda nuevamente en modo automático para uso normal en el laboratorio.

👨‍🏫 Parte 4: Gestión del Repositorio (Uso del Profesor)

Esta sección está orientada a la administración del código en la Raspberry Pi y su sincronización con el repositorio remoto.

🔽 Actualización de la Raspberry Pi desde el Repositorio Remoto

Cuando se hayan realizado cambios en GitHub desde otro equipo (por ejemplo, el PC del profesor) y se desee actualizar la Raspberry Pi:

Conectarse a la Raspberry Pi mediante SSH (VS Code o PuTTY).

Acceder a la carpeta del proyecto:

cd ~/srobot


Descargar los cambios:

git pull


En caso de existir conflictos locales, git lo indicará.
Si se desea forzar la restauración completa, se puede utilizar el procedimiento de restauración descrito en la sección Botón de Pánico (Parte 5).

Actualizar dependencias en caso de ser necesario:

source venv/bin/activate
pip install -r requirements_rpi.txt


Reiniciar el servicio para aplicar los cambios:

sudo systemctl restart srobot.service

🔼 Envío de Cambios desde la Raspberry Pi al Repositorio Remoto

Si se realizan modificaciones directamente en la Raspberry Pi y se desea conservarlas en GitHub:

Verificar los archivos modificados:

git status


Añadir los cambios al índice:

git add .


Crear un commit con un mensaje descriptivo:

git commit -m "Descripción de los cambios realizados en la Raspberry Pi"


Enviar los cambios al repositorio remoto:

git push


Si no se han configurado credenciales, Git solicitará usuario y contraseña o un token de acceso.

🔁 Parte 5: Botón de Pánico (Restauración del Estado Original)

El repositorio remoto actúa como imagen maestra del proyecto.
En caso de que las modificaciones locales en la Raspberry Pi provoquen fallos y se desee volver al estado original, se recomienda realizar una restauración completa desde el repositorio remoto.

Procedimiento:

cd ~/srobot
git fetch origin
git reset --hard origin/main


Con estos comandos, se descartan los cambios locales y se restablece el proyecto exactamente a la versión almacenada en la rama main del repositorio remoto.