/* =========================================================
   static/js/robot_main.js
   ---------------------------------------------------------
   Controlador Principal de la UI (Configurar Movimientos).
   Conecta:
   1. Interfaz de Usuario (HTML)
   2. Lógica de Comunicación (RobotAPI)
   3. Visualización 3D (RobotSimulation)
   ========================================================= */

// --- Estado Global de la Página ---
let simulation = null;     // Instancia de Three.js
let socket = null;         // Conexión Socket.IO

let estadoRobot = {
    servos: [90, 90, 90, 90, 90, 90], // [Base, Hombro, Codo, MuñecaV, MuñecaR, Gripper]
    velocidad: 50
};

let pasosSecuencia = [];   // Buffer temporal para crear nuevos movimientos
let interaccionUsuario = false; // Flag para evitar conflictos con actualizaciones automáticas

// --- Configuración de Debounce (Evitar saturar la red) ---
let timeoutMovimiento = null;
const enviarMovimientoDebounced = () => {
    clearTimeout(timeoutMovimiento);
    timeoutMovimiento = setTimeout(() => {
        RobotAPI.moverServos(estadoRobot.servos, estadoRobot.velocidad);
        actualizarCinematica(); // Actualizamos coordenadas al detenerse
    }, 100); // Espera 100ms de inactividad antes de enviar
};

// Utilidad para pausar ejecución en JS (Promesa)
const sleep = (ms) => new Promise(r => setTimeout(r, ms));

// ==========================================
// 1. INICIALIZACIÓN (Al cargar la página)
// ==========================================
document.addEventListener('DOMContentLoaded', async () => {
    console.log("Iniciando Controlador del Robot...");

    // 1. Iniciar Simulación 3D
    simulation = new RobotSimulation('robot-simulation');

    // 2. Cargar Estado Inicial desde Hardware
    const estadoInicial = await RobotAPI.obtenerEstadoGlobal();
    if (estadoInicial && estadoInicial.servos) {
        estadoRobot = estadoInicial;
        actualizarUI(true); // true = forzar actualización visual
    }

    // 3. Configurar Listeners (Botones y Sliders)
    configurarControles();
    
    // 4. Cargar Listas (Puntos y Movimientos guardados)
    cargarListaPuntos();
    cargarBibliotecaMovimientos();

    // 5. Configurar Socket.IO (Feedback en tiempo real, si existe)
    try {
        if(window.io) {
            socket = io();
            socket.on('connect', () => console.log("Socket Conectado"));
            socket.on('state_updated', (data) => {
                // Solo actualizamos si el usuario NO está tocando los controles
                if (!interaccionUsuario && data.servos) {
                    estadoRobot.servos = data.servos;
                    if(data.velocidad) estadoRobot.velocidad = data.velocidad;
                    actualizarUI();
                }
            });
        }
    } catch (e) { console.warn("Socket.IO no disponible"); }
});

// ==========================================
// 2. GESTIÓN DE LA UI (Sliders y Botones)
// ==========================================

function configurarControles() {
    
    // A. Sliders de Servos (1 al 5)
    for (let i = 1; i <= 5; i++) {
        const slider = document.getElementById(`servo${i}`);
        if (!slider) continue;

        // Al iniciar arrastre
        slider.addEventListener('mousedown', () => { interaccionUsuario = true; });
        slider.addEventListener('touchstart', () => { interaccionUsuario = true; }, {passive: true});

        // Al mover
        slider.addEventListener('input', (e) => {
            const val = parseInt(e.target.value);
            estadoRobot.servos[i-1] = val;
            
            // Actualizar texto
            document.getElementById(`servo${i}-val`).textContent = val;
            
            // Actualizar Simulación (Inmediato)
            if(simulation) simulation.updateAngles(estadoRobot.servos);
            
            // Enviar a Robot (Debounce)
            enviarMovimientoDebounced();
        });

        // Al soltar
        slider.addEventListener('change', () => {
            interaccionUsuario = false;
        });
        slider.addEventListener('mouseup', () => { interaccionUsuario = false; });
        slider.addEventListener('touchend', () => { interaccionUsuario = false; });
    }

    // B. Slider de Velocidad
    const speedSlider = document.getElementById('velocidad');
    if(speedSlider) {
        speedSlider.addEventListener('input', (e) => {
            estadoRobot.velocidad = parseInt(e.target.value);
            document.getElementById('speed-display').textContent = `Vel: ${estadoRobot.velocidad}`;
            enviarMovimientoDebounced();
        });
    }

    // C. Control Gripper (Pinza)
    const btnOpen = document.getElementById('gripper-open');
    const btnClose = document.getElementById('gripper-close');
    
    if(btnOpen) btnOpen.addEventListener('click', () => setGripper(true));
    if(btnClose) btnClose.addEventListener('click', () => setGripper(false));

    // D. Botones Globales
    const btnHome = document.getElementById('btn-home');
    if(btnHome) btnHome.addEventListener('click', irAHome);
    
    const btnSavePos = document.getElementById('save-position');
    if(btnSavePos) btnSavePos.addEventListener('click', agregarPasoSecuencia);
    
    // E. Botones de Guardado (Puntos y Archivos)
    const btnSavePoint = document.getElementById('save-point-btn');
    if(btnSavePoint) btnSavePoint.addEventListener('click', guardarPuntoCoordenada);
    
    const btnSaveMov = document.getElementById('save-movement');
    if(btnSaveMov) btnSaveMov.addEventListener('click', guardarSecuenciaEnArchivo);

    // F. Botón Área de Trabajo
    const btnArea = document.getElementById('btn-area-trabajo');
    if(btnArea) btnArea.addEventListener('click', toggleAreaTrabajo);
}

// --- Funciones Auxiliares de UI ---

function actualizarUI(forceUpdate = false) {
    // Sincroniza los sliders con la variable estadoRobot
    
    // Velocidad
    const speedSlider = document.getElementById('velocidad');
    if(speedSlider) {
        speedSlider.value = estadoRobot.velocidad;
        document.getElementById('speed-display').textContent = `Vel: ${estadoRobot.velocidad}`;
    }

    // Servos 1-5
    for (let i = 1; i <= 5; i++) {
        const slider = document.getElementById(`servo${i}`);
        const label = document.getElementById(`servo${i}-val`);
        if(slider && label) {
            slider.value = estadoRobot.servos[i-1];
            label.textContent = estadoRobot.servos[i-1];
        }
    }

    // Gripper (Servo 6)
    const valGripper = estadoRobot.servos[5];
    const labelS6 = document.getElementById('servo6-val');
    if(labelS6) labelS6.textContent = valGripper;
    
    // Actualizar botones activo/inactivo
    // Asumimos: 90 = Abierto, 120 = Cerrado
    const isOpen = (valGripper <= 95); 
    const btnOpen = document.getElementById('gripper-open');
    const btnClose = document.getElementById('gripper-close');
    
    if (btnOpen && btnClose) {
        if (isOpen) {
            btnOpen.classList.add('active');
            btnClose.classList.remove('active');
        } else {
            btnClose.classList.add('active');
            btnOpen.classList.remove('active');
        }
    }

    // Actualizar Simulación
    if(simulation) simulation.updateAngles(estadoRobot.servos);
    
    // Actualizar Cinemática (Texto)
    if(forceUpdate) actualizarCinematica();
}

function setGripper(abrir) {
    const val = abrir ? 90 : 120; // Ajusta según tu hardware
    estadoRobot.servos[5] = val;
    
    // Actualización inmediata visual
    actualizarUI();
    
    // Envio inmediato
    RobotAPI.moverServos(estadoRobot.servos, estadoRobot.velocidad);
}

function irAHome() {
    estadoRobot.servos = [90, 90, 90, 90, 90, 90];
    estadoRobot.velocidad = 50;
    actualizarUI(true);
    RobotAPI.moverServos(estadoRobot.servos, estadoRobot.velocidad);
}

async function actualizarCinematica() {
    // Solo si existen los elementos de coordenadas
    if(!document.getElementById("gripper-x")) return;

    const coords = await RobotAPI.calcularPosicionGripper(estadoRobot.servos);
    if (!coords || coords.error) return;

    document.getElementById("gripper-x").textContent = coords.x;
    document.getElementById("gripper-y").textContent = coords.y;
    document.getElementById("gripper-z").textContent = coords.z;
    document.getElementById("gripper-roll").textContent = coords.roll;
    document.getElementById("gripper-pitch").textContent = coords.pitch;
    document.getElementById("gripper-yaw").textContent = coords.yaw;
}

async function toggleAreaTrabajo() {
    const data = await RobotAPI.obtenerAreaTrabajo();
    if(simulation) simulation.toggleWorkspace(data.points);
}

// ==========================================
// 3. LÓGICA DE SECUENCIAS (Crear movimientos)
// ==========================================

function agregarPasoSecuencia() {
    const paso = {
        servos: [...estadoRobot.servos],
        velocidad: estadoRobot.velocidad
    };
    pasosSecuencia.push(paso);
    renderizarListaPasos();
}

function renderizarListaPasos() {
    const lista = document.getElementById('positions-list');
    if(!lista) return;
    lista.innerHTML = '';

    if (pasosSecuencia.length === 0) {
        lista.innerHTML = '<li class="movement-item" style="color:#94a3b8; justify-content:center;">Sin pasos guardados</li>';
        return;
    }

    pasosSecuencia.forEach((paso, index) => {
        const li = document.createElement('li');
        li.className = 'movement-item';
        li.innerHTML = `
            <span><b>Paso ${index + 1}:</b> [${paso.servos.slice(0,5).join(', ')}]</span>
            <button class="btn-icon text-red" onclick="borrarPaso(${index})">
                <i class="fas fa-trash"></i>
            </button>
        `;
        lista.appendChild(li);
    });
}

window.borrarPaso = (index) => {
    pasosSecuencia.splice(index, 1);
    renderizarListaPasos();
};

async function guardarSecuenciaEnArchivo() {
    const nombre = document.getElementById('movement-name').value.trim();
    if (!nombre) return alert("Escribe un nombre para la secuencia.");
    if (pasosSecuencia.length === 0) return alert("No hay pasos para guardar.");

    const msg = await RobotAPI.guardarMovimiento(nombre, pasosSecuencia);
    alert(msg);
    
    pasosSecuencia = [];
    renderizarListaPasos();
    document.getElementById('movement-name').value = '';
    cargarBibliotecaMovimientos(); 
}

// ==========================================
// 4. LÓGICA DE BIBLIOTECA (Cargar/Ejecutar)
// ==========================================

async function cargarBibliotecaMovimientos() {
    const archivos = await RobotAPI.obtenerMovimientos();
    const lista = document.getElementById('movements-list');
    if(!lista) return;
    lista.innerHTML = '';

    if (!archivos || archivos.length === 0) {
        lista.innerHTML = '<li class="movement-item" style="color:#94a3b8; justify-content:center;">Biblioteca vacía</li>';
        return;
    }

    archivos.forEach(archivo => {
        const nombreDisplay = archivo.replace('.txt', '');
        const li = document.createElement('li');
        li.className = 'movement-item';
        li.innerHTML = `
            <span title="${archivo}"><i class="fas fa-file-code"></i> ${nombreDisplay}</span>
            <div class="item-actions">
                <button class="btn-icon text-blue" title="Inspector" onclick="inspeccionarMov('${archivo}')"><i class="fas fa-search"></i></button>
                <button class="btn-icon text-green" title="Ejecutar" onclick="ejecutarMov('${archivo}')"><i class="fas fa-play"></i></button>
                <button class="btn-icon text-red" title="Borrar" onclick="borrarMov('${archivo}')"><i class="fas fa-trash"></i></button>
            </div>
        `;
        lista.appendChild(li);
    });
}

// --- FUNCIÓN DE EJECUCIÓN SINCRONIZADA ---
window.ejecutarMov = async (nombre) => {
    // 1. Cargar pasos para saber cuánto durará y qué mostrar
    const pasos = await RobotAPI.cargarMovimiento(nombre);
    
    if (!pasos || pasos.length === 0) {
        alert("El movimiento está vacío o no se pudo cargar.");
        return;
    }

    // 2. CUENTA REGRESIVA (3, 2, 1)
    const overlay = document.getElementById('countdown-overlay');
    const texto = document.getElementById('countdown-text');
    
    if(overlay && texto) {
        overlay.classList.add('active');
        
        texto.textContent = "3";
        await sleep(1000);
        texto.textContent = "2";
        await sleep(1000);
        texto.textContent = "1";
        await sleep(1000);
        texto.textContent = "GO!";
        await sleep(500);
        
        overlay.classList.remove('active');
    }

    // 3. INICIAR EJECUCIÓN EN BACKEND (Fuego y olvido)
    console.log(`Enviando orden física: ${nombre}`);
    RobotAPI.ejecutarMovimiento(nombre); // Esto lanza el hilo en Python

    // 4. INICIAR EJECUCIÓN VISUAL (Sincronizada manualmente)
    interaccionUsuario = true; // Bloquear sliders manuales

    for (const paso of pasos) {
        // Actualizar estado local
        estadoRobot.servos = paso.servos;
        if (paso.velocidad) estadoRobot.velocidad = paso.velocidad;

        // Actualizar UI y Simulación 3D
        actualizarUI(true);

        // Esperar tiempo de movimiento (550ms para cubrir latencia + mov físico)
        // Ajusta este valor si tu robot físico es más lento o rápido
        await sleep(550); 
    }
    
    interaccionUsuario = false; // Desbloquear sliders
    console.log("Ejecución visual finalizada.");
};

window.borrarMov = async (nombre) => {
    if(!confirm(`¿Borrar ${nombre}?`)) return;
    const msg = await RobotAPI.borrarMovimiento(nombre);
    alert(msg);
    cargarBibliotecaMovimientos();
};

// --- Inspector de Movimientos ---
window.inspeccionarMov = async (nombre) => {
    const pasos = await RobotAPI.cargarMovimiento(nombre);
    if (!pasos) return alert("Error al cargar archivo");

    const lista = document.getElementById('loaded-movement-list');
    if(!lista) return;
    lista.innerHTML = '';

    pasos.forEach((paso, idx) => {
        const li = document.createElement('li');
        li.className = 'movement-item';
        li.innerHTML = `
            <span>Paso ${idx + 1} (Vel ${paso.velocidad})</span>
            <button class="btn-icon text-blue" onclick="cargarPasoEnRobot(${idx})">
                <i class="fas fa-arrow-right"></i> Ir
            </button>
        `;
        // Guardamos datos en dataset para acceso rápido
        li.dataset.servos = JSON.stringify(paso.servos);
        li.dataset.velocidad = paso.velocidad;
        lista.appendChild(li);
    });
    
    // Helper local para el botón "Ir" dentro del inspector
    window.cargarPasoEnRobot = (idx) => {
        const items = document.querySelectorAll('#loaded-movement-list li');
        if(items[idx]) {
            const s = JSON.parse(items[idx].dataset.servos);
            const v = parseInt(items[idx].dataset.velocidad);
            
            estadoRobot.servos = s;
            estadoRobot.velocidad = v;
            actualizarUI(true);
            RobotAPI.moverServos(s, v);
        }
    };
};

window.quitarMovimientoCargado = () => {
    const lista = document.getElementById('loaded-movement-list');
    if(lista) {
        lista.innerHTML = '<li class="movement-item" style="color:#94a3b8; justify-content:center;">Selecciona un movimiento</li>';
    }
};

// ==========================================
// 5. GESTIÓN DE PUNTOS (Coordenadas)
// ==========================================

async function guardarPuntoCoordenada() {
    const nombre = document.getElementById('point-name').value.trim();
    if (!nombre) return alert("Ponle un nombre al punto.");

    // Leemos del DOM los valores calculados por la API
    if(!document.getElementById("gripper-x")) return alert("No hay datos de coordenadas calculados.");

    const data = {
        name: nombre,
        x: document.getElementById("gripper-x").textContent,
        y: document.getElementById("gripper-y").textContent,
        z: document.getElementById("gripper-z").textContent,
        roll: document.getElementById("gripper-roll").textContent,
        pitch: document.getElementById("gripper-pitch").textContent,
        yaw: document.getElementById("gripper-yaw").textContent
    };

    const msg = await RobotAPI.guardarPunto(data);
    alert(msg);
    cargarListaPuntos();
}

async function cargarListaPuntos() {
    const puntos = await RobotAPI.listarPuntos();
    const lista = document.getElementById('saved-points-list');
    if(!lista) return;
    lista.innerHTML = '';

    if (!puntos || puntos.length === 0) {
        lista.innerHTML = '<li class="movement-item" style="color:#94a3b8; justify-content:center;">Sin puntos guardados</li>';
        return;
    }

    puntos.forEach(nombre => {
        const li = document.createElement('li');
        li.className = 'movement-item';
        li.innerHTML = `
            <span>${nombre}</span>
            <div class="item-actions">
                <button class="btn-icon text-blue" onclick="verPunto('${nombre}')"><i class="fas fa-eye"></i></button>
                <button class="btn-icon text-red" onclick="borrarPunto('${nombre}')"><i class="fas fa-trash"></i></button>
            </div>
        `;
        lista.appendChild(li);
    });
}

window.verPunto = async (nombre) => {
    const info = await RobotAPI.verPunto(nombre);
    alert(`📍 Punto: ${nombre}\n\n${info}`);
};

window.borrarPunto = async (nombre) => {
    if(!confirm("¿Borrar punto?")) return;
    await RobotAPI.borrarPunto(nombre);
    cargarListaPuntos();
};