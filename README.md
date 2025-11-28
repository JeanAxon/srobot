# 🤖 S-Robot: Plataforma Educativa de Robótica Híbrida

S-Robot es una plataforma educativa de robótica que implementa un sistema híbrido de control. Permite operar un **brazo robótico de 5 grados de libertad (5 GDL)** y una **banda transportadora**, integrando **visión artificial (TensorFlow Lite)**, **cinemática inversa** y **comunicación industrial (Modbus TCP)**.

La lógica principal del sistema es **compartida** entre Windows y Raspberry Pi: los módulos de `/modulos`, las plantillas de `templates/` y los recursos de `static/` se utilizan en ambos entornos.

Las principales diferencias entre plataformas son:

* En **Windows**, el archivo `ServidorMPS.py` actúa como lanzador con interfaz gráfica.
* En **Raspberry Pi**, el archivo `app.py` se ejecuta de forma directa como servicio principal (`srobot.service`).
* Existen archivos de dependencias separados para cada entorno (`requirements_windows.txt` y `requirements_rpi.txt`), adaptados a las capacidades de cada plataforma.

---

## 🏗️ Arquitectura del Sistema

El sistema utiliza una **arquitectura de doble entorno**, diseñada para facilitar tanto el aprendizaje seguro como el despliegue en un entorno de laboratorio.

### 🖥️ Entorno Estudiante (Windows)

* **Archivo principal:** `ServidorMPS.py`
* **Descripción:** Aplicación de escritorio con interfaz gráfica (GUI).

  * Inicia el servidor interno.
  * Permite simular la lógica del sistema.
  * Permite generar trayectorias y probar algoritmos de visión sin interactuar físicamente con el hardware.
* **Objetivo principal:** Proporcionar un entorno de experimentación segura para el desarrollo y prueba de algoritmos.

### 🍓 Entorno Laboratorio (Raspberry Pi)

* **Archivo principal:** `app.py` (ejecución automática mediante servicio del sistema `srobot.service`).
* **Descripción:** Servidor **headless** (sin monitor) optimizado para rendimiento.

  * Controla los GPIO.
  * Gestiona la cámara USB.
  * Se comunica por puerto serie con el microcontrolador (Arduino).
* **Objetivo principal:** Operación física del sistema en entorno real de laboratorio.

---

## 📂 Estructura de Archivos y Carpetas

Descripción general de la estructura del proyecto y el propósito de los elementos principales.

### 🔴 Archivos Principales

* `app.py` (Raspberry Pi):
  Servidor Flask principal. Gestiona la cámara, los hilos de ejecución y las rutas web.
* `ServidorMPS.py` (Windows):
  Interfaz gráfica de usuario que encapsula la lógica del servidor para su uso en PC.
* `requirements_windows.txt`:
  Lista de dependencias para entorno Windows (incluye GUI y versión completa de OpenCV).
* `requirements_rpi.txt`:
  Lista de dependencias optimizadas para Raspberry Pi (modo headless, sin GUI).
* `README.md`:
  Documentación del proyecto.
* `LICENSE`:
  Licencia del proyecto (MIT, salvo indicación en contrario).

### 🔵 Módulos de Lógica (`/modulos`)

* `reconocimiento.py`:
  Procesa imágenes y utiliza TensorFlow Lite para la detección de color y forma.
* `ejecucion.py`:
  Implementa la máquina de estados que controla el ciclo automático
  (banda transportadora → captura de imagen → brazo robótico).
* `cinematica_inversa.py`:
  Implementa un algoritmo por CCD (Cyclic Coordinate Descent) para calcular los ángulos de los servos a partir de coordenadas cartesianas (X, Y, Z).
* `cinematica_inversa_local.py`:
  Variante del cálculo de cinemática inversa utilizando `scipy.optimize`.
* `generador_trayectoria.py`:
  Genera trayectorias suaves (por ejemplo, mediante splines) entre puntos de posición.

### 🟢 Módulos de Hardware (`/modulos`)

* `brazo_robotico.py`:
  Envía comandos seriales (por ejemplo, `A,90...`) al Arduino para el control del brazo robótico.
* `banda_transportadora.py`:
  Controla el motor de la banda transportadora mediante comandos específicos (por ejemplo, `P`, `A`).
* `com_modbus.py`:
  Implementa la comunicación Modbus TCP para la integración con PLCs industriales.

### 📁 Carpetas de Datos y Firmware

* `uploads/`:
  Directorio de almacenamiento de datos.
  Se utiliza para guardar automáticamente las imágenes capturadas para entrenamiento y los modelos `.tflite` cargados desde la interfaz web.
* `movimientos/`:
  Almacena las secuencias de movimiento generadas por el usuario en archivos de texto (`.txt`).
* `Servo_Motor/`:
  Contiene el código fuente del microcontrolador Arduino (`Servo_Motor.ino`).
  Este archivo funciona como **respaldo de firmware** y puede recargarse en el Arduino directamente desde la Raspberry Pi.

### 📄 Archivos de Configuración

* `logica_config.json`:
  Define las reglas de automatización del sistema.
  Ejemplo: `Si se detecta [Círculo Azul] -> ejecutar [Movimiento B]`.
* `estado.json`:
  Almacena la última posición conocida de los servomotores y las velocidades, con el fin de mantener la calibración entre reinicios del sistema.

---

## 🧭 Diagramas Textuales del Sistema

### 1. Mapa General de Componentes

```text
Usuario
│
├─ PC Windows (Entorno Estudiante)
│   └─ ServidorMPS.py
│       ├─ Inicia servidor local
│       ├─ Simulación de lógica y trayectorias
│       ├─ Interfaz gráfica (panel de control)
│       └─ Gestión de archivos de movimientos (*.txt)
│
└─ Raspberry Pi (Entorno Laboratorio)
    ├─ Servicio srobot.service
    │   └─ Ejecuta app.py al iniciar el sistema
    ├─ app.py
    │   ├─ Servidor Flask (API / interfaz web)
    │   ├─ Control de cámara USB
    │   ├─ Gestión de hilos y bucles de control
    │   └─ Uso de módulos de /modulos
    ├─ Arduino (microcontrolador)
    │   └─ Firmware Servo_Motor.ino (control de servomotores)
    └─ PLC / Modbus TCP (opcional)
        └─ Integración con celdas o sistemas externos
```

### 2. Relación entre Módulos de Lógica y Hardware

```text
app.py / ServidorMPS.py
├─ Lógica (/modulos)
│   ├─ ejecucion.py
│   │   └─ Máquina de estados (ciclo automático)
│   ├─ reconocimiento.py
│   │   └─ Detección de piezas (color / forma) con TFLite
│   ├─ cinematica_inversa.py / cinematica_inversa_local.py
│   │   └─ Cálculo de ángulos de servos
│   └─ generador_trayectoria.py
│       └─ Trayectorias suaves entre puntos
│
└─ Hardware (/modulos)
    ├─ brazo_robotico.py
    │   └─ Envío de comandos al Arduino
    ├─ banda_transportadora.py
    │   └─ Control de banda: arranque, parada, avance
    └─ com_modbus.py
        └─ Comunicación con PLCs industriales
```

### 3. Flujo Básico del Ciclo Automático

```text
[Inicio ciclo automático]
        │
        ▼
[Arranque de banda transportadora]
        │
        ▼
[Pieza en zona de cámara]
        │
        ▼
[Captura de imagen]
        │
        ▼
[reconocimiento.py]
  └─ Clasificación por color / forma
        │
        ▼
[logica_config.json]
  └─ Selección de movimiento asociado
        │
        ▼
[cinematica_inversa + generador_trayectoria]
  └─ Cálculo de ángulos y trayectorias
        │
        ▼
[brazo_robotico.py]
  └─ Ejecución de movimiento sobre el brazo
        │
        ▼
[Fin de ciclo / siguiente pieza]
```

---

## 🧰 Requisitos de Software e Instalación de Herramientas (Windows)

Para utilizar el entorno de simulación en un PC con Windows se recomienda instalar:

* Git
* Visual Studio Code
* Python 3.11 (rama 3.11.x)

### 1. Instalación de Git

1. Acceder al sitio oficial de descarga de Git:
   [https://git-scm.com/downloads](https://git-scm.com/downloads)
2. Seleccionar la opción correspondiente a **Windows**.
3. Ejecutar el instalador descargado y seguir los pasos del asistente, manteniendo las opciones predeterminadas salvo que se requiera una configuración específica.
4. Al finalizar, abrir **cmd** o **PowerShell** y verificar la instalación con:

   ```bash
   git --version
   ```

### 2. Instalación de Visual Studio Code

1. Acceder al sitio oficial de Visual Studio Code:
   [https://code.visualstudio.com/download](https://code.visualstudio.com/download)
2. Descargar el instalador para **Windows**.
3. Ejecutar el instalador y completar el asistente de instalación (se recomienda habilitar las opciones de integración con el menú contextual y la variable de entorno PATH).
4. Verificar la instalación abriendo **Visual Studio Code** desde el menú Inicio o ejecutando:

   ```bash
   code
   ```

### 3. Instalación de Python 3.11

1. Acceder a la sección de descargas de Python 3.11 para Windows:
   [https://www.python.org/downloads/](https://www.python.org/downloads/)
2. Descargar el instalador de la rama **3.11.x** (por ejemplo, *Windows installer (64-bit)*).
3. Ejecutar el instalador y, antes de continuar, marcar la casilla **“Add Python 3.11 to PATH”**.
4. Completar el asistente de instalación con las opciones recomendadas.
5. Verificar la instalación abriendo **cmd** y ejecutando:

   ```bash
   python --version
   ```

---

## 💻 Parte 2: Entorno de Desarrollo (Windows usando VS Code)

Esta sección describe, paso a paso, cómo configurar el entorno de simulación en un equipo con Windows usando **Visual Studio Code**.

### 1. Crear carpeta de trabajo y abrirla en VS Code

1. Crear una carpeta en el escritorio (por ejemplo, `SRobot`).
2. Abrir **Visual Studio Code**.
3. En el menú superior, seleccionar:
   **File → Open Folder...** (Archivo → Abrir carpeta...).
4. Seleccionar la carpeta creada en el escritorio (`SRobot`) y confirmar.

   * A partir de este momento, esa carpeta será la raíz de trabajo en VS Code.

### 2. Abrir una terminal integrada en la carpeta

1. En VS Code, ir al menú:
   **Terminal → New Terminal** (Terminal → Nueva terminal).
2. Se abrirá una terminal integrada en la parte inferior de la ventana.

   * El directorio actual debería ser la carpeta `SRobot` del escritorio.
   * Si no fuera así, navegar manualmente con:

   ```bash
   cd ruta/a/la/carpeta/SRobot
   ```

### 3. Clonar el repositorio dentro de la carpeta

En la terminal integrada de VS Code (ubicada en la carpeta `SRobot`), ejecutar:

```bash
git clone https://github.com/JeanAxon/srobot.git
cd srobot
```

Al finalizar, la estructura en el explorador de VS Code mostrará la carpeta `srobot` dentro de `SRobot` con todos los archivos del proyecto.

### 4. Crear entorno virtual e instalar dependencias (Windows)

1. En la misma terminal integrada (ya dentro de `srobot`), ejecutar:

   ```bash
   python -m venv venv
   ```

2. Activar el entorno virtual:

   ```bash
   .\venv\Scripts\activate
   ```

3. Instalar dependencias específicas para Windows:

   ```bash
   pip install -r requirements_windows.txt
   ```

### 5. Ejecutar el simulador (Windows)

Con el entorno virtual activado y ubicándose en la carpeta `srobot`:

```bash
python ServidorMPS.py
```

Al ejecutar este comando, se abrirá el **panel de control** de la aplicación. Desde allí es posible:

* Probar la lógica del sistema.
* Simular trayectorias.
* Generar archivos de movimiento para el brazo robótico.

---

## 🔌 Parte 1: Conexión Inicial (Uso de Ethernet)

> ⚠️ Para la primera configuración, o cuando se cambia la red de trabajo, se recomienda utilizar siempre conexión por cable Ethernet.

### 1. Preparación del PC (Windows)

Para conectar la Raspberry Pi a través de la PC, se utiliza **Internet Connection Sharing (ICS)** de Windows. Esto permite asignar una dirección IP adecuada a la Raspberry Pi.

Pasos generales:

1. Conectar el PC a la red Wi-Fi.
2. Abrir el cuadro **Ejecutar** con `Win + R`, escribir `ncpa.cpl` y pulsar **Enter**.
3. Hacer clic derecho sobre el adaptador **Wi-Fi** y seleccionar **Propiedades**.
4. Ir a la pestaña **Uso compartido**.
5. Activar la opción
   **“Permitir que los usuarios de otras redes se conecten a través de la conexión a Internet de este equipo”**.
6. En **“Conexión de red doméstica”**, seleccionar el adaptador **Ethernet**.
7. Confirmar los cambios.

#### Reinicio del servicio de compartición (en caso de fallo tras reiniciar)

En algunos casos, después de reiniciar el PC, el servicio de compartición de internet puede quedar inestable.

Para restablecerlo:

1. Volver a abrir `ncpa.cpl`.
2. Abrir **Propiedades** del adaptador **Wi-Fi** y acceder a la pestaña **Uso compartido**.
3. Desmarcar la casilla de uso compartido y aceptar.
4. Esperar unos segundos.
5. Volver a marcar la casilla y aceptar.

Con esto se reinicia el servicio DHCP que asigna la dirección IP a la Raspberry Pi.

---

### 2. Verificación de Conectividad

1. Conectar el cable Ethernet entre el PC y la Raspberry Pi.
2. Abrir una terminal de comandos (**cmd**) en Windows.
3. Ejecutar:

```bash
ping 192.168.137.50
```

Si no se obtiene respuesta, se puede intentar:

```bash
ping mps.local
```

---

### 3. Diagnóstico con PuTTY

Para comprobar el estado interno del sistema y obtener información de red, se puede utilizar **PuTTY**.

Parámetros de conexión:

* **Host:** `192.168.137.50`
* **Puerto:** `22`
* **Tipo:** `SSH`
* **Usuario:** `mps`
* **Contraseña:** `mps123`

Comandos útiles:

```bash
ip -c a
```

Muestra las direcciones IP de las interfaces de red. La IP de `wlan0` puede utilizarse para conexiones posteriores por Wi-Fi.

```bash
sudo systemctl status srobot.service
```

Verifica el estado del servicio principal del robot.

```bash
ping -c 2 8.8.8.8
```

Comprueba la conectividad a internet desde la Raspberry Pi.

---

## 🚀 Parte 3: Trabajo sobre la Raspberry Pi (VS Code Remoto)

Esta sección describe el procedimiento para editar y probar el código directamente en la Raspberry Pi utilizando **VS Code Remote - SSH**, manteniendo la configuración del sistema bajo control.

> En la imagen estándar del sistema, el entorno virtual y las dependencias de la Raspberry Pi ya se encuentran instalados.
> Solo es necesario reinstalar dependencias en caso de trabajar con una Raspberry Pi completamente nueva o tras borrar el entorno anterior.

### 1. Configuración de SSH en VS Code

1. Instalar la extensión **Remote - SSH** en VS Code.
2. En VS Code, ir al icono verde de la esquina inferior izquierda (`><`) y seleccionar **“Open SSH Configuration File…”**.
3. Añadir las siguientes entradas al archivo de configuración:

```ssh
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
```

La IP correspondiente a `Robot-Wifi` debe consultarse mediante el comando `ip -c a` en la Raspberry Pi (interfaz `wlan0`).

### 2. Edición y Transferencia de Archivos

Una vez configurada la conexión:

* Es posible conectarse a `Robot-Cable` desde VS Code introduciendo la contraseña `mps123`.
* Los archivos del proyecto ubicados en `/home/mps/srobot` pueden:

  * Editarse directamente desde VS Code, o
  * Sustituirse arrastrando archivos desde Windows a dicha carpeta.

---

### ⚠️ Protocolo de Pruebas en la Raspberry Pi

El servicio principal del sistema utiliza la cámara y el puerto serie. Para realizar pruebas manuales sin conflicto de recursos, se recomienda seguir el siguiente orden:

#### 1. Detener el servicio

```bash
sudo systemctl stop srobot.service
```

#### 2. Ejecutar la aplicación de forma manual

```bash
cd ~/srobot
source venv/bin/activate
python app.py
```

De esta forma es posible observar en la consola los errores o mensajes de depuración en tiempo real. La ejecución puede detenerse con `Ctrl + C`.

#### 3. Reactivar el servicio al finalizar

```bash
sudo systemctl start srobot.service
```

Con esto, el sistema queda nuevamente en modo automático para uso normal en el laboratorio.

---

## 🔧 Parte 3.1: Instalación de Dependencias en una Raspberry Pi Nueva (Opcional)

Esta sección solo aplica cuando se trabaja con una **Raspberry Pi limpia**, en la que aún no se ha creado el entorno virtual ni instalado las dependencias.

1. Clonar el repositorio (si no se ha hecho):

   ```bash
   cd ~
   git clone https://github.com/JeanAxon/srobot.git
   cd srobot
   ```

2. Crear entorno virtual e instalar dependencias específicas de Raspberry Pi:

   ```bash
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements_rpi.txt
   ```

Tras esta configuración inicial, el flujo de trabajo normal corresponde al descrito en el **Protocolo de Pruebas** y en la **Gestión del Repositorio**.

---

## 🔌 Parte 3.2: Carga del Firmware del Arduino desde la Raspberry Pi

El directorio `Servo_Motor/` contiene el archivo `Servo_Motor.ino`, que corresponde al firmware de referencia para el microcontrolador (Arduino).
Este firmware puede cargarse en el Arduino directamente desde la Raspberry Pi utilizando la línea de comandos.

A continuación se muestra un procedimiento genérico utilizando **arduino-cli**:

### 1. Instalación de arduino-cli en la Raspberry Pi

```bash
# Descargar arduino-cli
curl -fsSL https://raw.githubusercontent.com/arduino/arduino-cli/master/install.sh | sh

# Moverlo a una ruta accesible globalmente
sudo mv bin/arduino-cli /usr/local/bin/arduino-cli

# Inicializar configuración
arduino-cli config init
```

### 2. Instalación del paquete de placas correspondiente

Ejemplo para una placa tipo **Arduino UNO** (ajustar según el hardware real):

```bash
arduino-cli core update-index
arduino-cli core install arduino:avr
```

### 3. Compilación del Sketch

Desde el directorio del proyecto:

```bash
cd ~/srobot/Servo_Motor
arduino-cli compile --fqbn arduino:avr:uno Servo_Motor.ino
```

### 4. Carga del Firmware en el Arduino

1. Conectar el Arduino a la Raspberry Pi por USB.

2. Identificar el puerto serie (por ejemplo, `/dev/ttyACM0` o `/dev/ttyUSB0`):

   ```bash
   ls /dev/ttyACM* /dev/ttyUSB* 2>/dev/null
   ```

3. Cargar el firmware:

   ```bash
   arduino-cli upload -p /dev/ttyACM0 --fqbn arduino:avr:uno Servo_Motor.ino
   ```

* Sustituir `arduino:avr:uno` por la placa utilizada realmente, si es distinta.
* Sustituir `/dev/ttyACM0` por el puerto correspondiente si difiere.

Este procedimiento permite restaurar o actualizar el firmware del Arduino usando el código de referencia incluido en el repositorio.

---

## 👨‍🏫 Parte 4: Gestión del Repositorio (Uso del Profesor)

Esta sección está orientada a la administración del código en la Raspberry Pi y su sincronización con el repositorio remoto.

### 🔽 Actualización de la Raspberry Pi desde el Repositorio Remoto

Cuando se hayan realizado cambios en GitHub desde otro equipo (por ejemplo, el PC del profesor) y se desee actualizar la Raspberry Pi:

1. Conectarse a la Raspberry Pi mediante SSH (VS Code o PuTTY).
2. Acceder a la carpeta del proyecto:

```bash
cd ~/srobot
```

3. Descargar los cambios:

```bash
git pull
```

En caso de existir conflictos locales, `git` lo indicará. Si se desea forzar la restauración completa, se puede utilizar el procedimiento de restauración descrito en la sección **Botón de Pánico** (Parte 5).

4. Actualizar dependencias en caso de ser necesario (solo si se modificó `requirements_rpi.txt`):

```bash
source venv/bin/activate
pip install -r requirements_rpi.txt
```

5. Reiniciar el servicio para aplicar los cambios:

```bash
sudo systemctl restart srobot.service
```

---

### 🔼 Envío de Cambios desde la Raspberry Pi al Repositorio Remoto

Si se realizan modificaciones directamente en la Raspberry Pi y se desea conservarlas en GitHub:

1. Verificar los archivos modificados:

```bash
git status
```

2. Añadir los cambios al índice:

```bash
git add .
```

3. Crear un commit con un mensaje descriptivo:

```bash
git commit -m "Descripción de los cambios realizados en la Raspberry Pi"
```

4. Enviar los cambios al repositorio remoto:

```bash
git push
```

Si no se han configurado credenciales, Git solicitará usuario y contraseña o un token de acceso.

---

## 🔁 Parte 5: Botón de Pánico (Restauración del Estado Original)

El repositorio remoto actúa como **imagen maestra** del proyecto.
En caso de que las modificaciones locales en la Raspberry Pi provoquen fallos y se desee volver al estado original, se recomienda realizar una restauración completa desde el repositorio remoto.

Procedimiento:

```bash
cd ~/srobot
git fetch origin
git reset --hard origin/main
```

Con estos comandos, se descartan los cambios locales y se restablece el proyecto exactamente a la versión almacenada en la rama `main` del repositorio remoto.

---

## 📜 Licencia

Este proyecto se distribuye bajo la licencia MIT. Puede ser usado y modificado por cualquier persona, pero siempre dando credito al autor.

---

## 📫 Contacto

Para consultas técnicas, comentarios o propuestas de mejora se puede contactar por estos medios. 
correo: jeanruizespinoza@gmail.com
whastapp: wa.me/593990969814
