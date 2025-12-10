/* =========================================================
   static/js/robot_main_ci.js
   ---------------------------------------------------------
   Controlador PROFESIONAL de Cinemática Inversa (5GDL).
   
   Versión: 2.0 (Híbrida)
   - Cálculo Matemático: Local (kinematics.js) -> Instantáneo
   - Ejecución Física: Remota (Flask API) -> Asíncrona
   ========================================================= */

// --- Estado Interno ---
let simulation = null;       // Instancia del motor 3D
// Nota: Ya no necesitamos calculationTimeout para debounce gracias al cálculo local

// Coordenadas Objetivo (Lo que el usuario quiere)
let target = {
    x: 0,
    y: 150, // mm
    z: 150, // mm
    pitch: -90, // Grados (Muñeca mirando abajo por defecto)
    roll: 0,    // Grados (Giro de muñeca manual)
    gripper: 90 // Grados (Apertura pinza)
};

// Solución Calculada (Lo que el robot hará)
let pendingSolution = null; // Array [s1, s2, s3, s4, s5, s6] o null si es inválido

// ==========================================
// 1. INICIALIZACIÓN
// ==========================================
document.addEventListener('DOMContentLoaded', async () => {
    console.log("Iniciando Modo CI con Ghosting Local...");

    // 1. Iniciar Simulación (Con soporte para Fantasma)
    simulation = new RobotSimulation('robot-simulation');

    // 2. Sincronizar UI con el Robot Real al inicio
    const estado = await RobotAPI.obtenerEstadoGlobal();
    if (estado && estado.servos) {
        // Actualizar robot real (opaco)
        simulation.updateAngles(estado.servos, false);
        
        // Inicializar el Fantasma en la misma posición (oculto por ahora)
        simulation.updateAngles(estado.servos, true);
        simulation.setGhostVisible(false);

        // Intentar deducir coordenadas iniciales
        // Nota: Si el backend no devuelve coords, usamos los defaults
        const coords = await RobotAPI.calcularPosicionGripper(estado.servos);
        if (coords && !coords.error) {
            actualizarInputsUI(coords);
            target.gripper = estado.servos[5]; // Sincronizar gripper
        }
    }

    // 3. Configurar Listeners
    setupControls();
    
    // 4. Configurar Botón Principal
    const btnMover = document.getElementById('btn-calcular-mover');
    btnMover.addEventListener('click', ejecutarMovimiento);
    btnMover.disabled = true; // Deshabilitado hasta que haya solución válida

    // 5. Cargar utilidades
    cargarListaPuntos();
});

// ==========================================
// 2. CONTROL DE INPUTS (JOGGING)
// ==========================================

function setupControls() {
    // A. Inputs Numéricos Directos
    ['x', 'y', 'z', 'pitch', 'roll'].forEach(key => {
        const input = document.getElementById(`val-${key}`);
        if (!input) return;

        input.addEventListener('input', (e) => {
            target[key] = parseFloat(e.target.value) || 0;
            requestGhostCalculation(); // Recalcular en tiempo real local
        });
    });

    // B. Control de Gripper (Independiente de la CI)
    document.getElementById('gripper-open').addEventListener('click', () => updateGripperTarget(90));
    document.getElementById('gripper-close').addEventListener('click', () => updateGripperTarget(120));
}

// Función global para los botones del HTML (+ / -)
window.ajustarValor = (axis, delta) => {
    const input = document.getElementById(`val-${axis}`);
    if (!input) return;

    let newVal = parseFloat(input.value) + delta;
    
    // Validaciones básicas de UI para evitar números absurdos
    if (axis === 'z' && newVal < -50) newVal = -50; 

    input.value = newVal;
    target[axis] = newVal;
    
    requestGhostCalculation(); // Cálculo instantáneo
};

function updateGripperTarget(val) {
    target.gripper = val;
    
    // Actualizar visualmente los botones
    const btnOpen = document.getElementById('gripper-open');
    const btnClose = document.getElementById('gripper-close');
    if(val <= 95) {
        btnOpen.classList.add('active');
        btnClose.classList.remove('active');
    } else {
        btnClose.classList.add('active');
        btnOpen.classList.remove('active');
    }

    // Si hay una solución fantasma visible, actualizamos su gripper visualmente al instante
    if (pendingSolution) {
        pendingSolution[5] = val;
        simulation.updateAngles(pendingSolution, true);
    }
}

function actualizarInputsUI(coords) {
    // Actualiza los campos de texto sin disparar eventos recursivos
    if (coords.x !== undefined) { document.getElementById('val-x').value = Math.round(coords.x); target.x = coords.x; }
    if (coords.y !== undefined) { document.getElementById('val-y').value = Math.round(coords.y); target.y = coords.y; }
    if (coords.z !== undefined) { document.getElementById('val-z').value = Math.round(coords.z); target.z = coords.z; }
    if (coords.pitch !== undefined) { document.getElementById('val-pitch').value = Math.round(coords.pitch); target.pitch = coords.pitch; }
    // Roll se mantiene manual o a 0 si no viene definido
}

// ==========================================
// 3. CÁLCULO Y GHOSTING (VERSIÓN LOCAL)
// ==========================================

function requestGhostCalculation() {
    // Feedback visual inmediato
    const statusLabel = document.getElementById('status-ci');
    
    // 1. Mostrar Fantasma
    simulation.setGhostVisible(true);

    // 2. CÁLCULO MATEMÁTICO LOCAL (kinematics.js)
    // Esto ejecuta la función importada, sin fetch, sin delay.
    const solution = solveIK_5DOF(
        target.x, 
        target.y, 
        target.z, 
        target.pitch, 
        target.roll
    );

    const btnMover = document.getElementById('btn-calcular-mover');
    const displayResult = document.getElementById('angulos-resultado');

    if (solution && solution.isValid) {
        // --- ÉXITO: Solución Geométrica Encontrada ---
        
        // Construir vector completo de 6 servos [Base, Hombro, Codo, Pitch, Roll, Gripper]
        pendingSolution = [
            solution.angles[0], 
            solution.angles[1], 
            solution.angles[2], 
            solution.angles[3], 
            solution.angles[4], // Roll (passthrough o calculado)
            target.gripper      // Gripper manual
        ];

        // A. Actualizar Fantasma Visual (¡Instantáneo!)
        simulation.updateAngles(pendingSolution, true);

        // B. Actualizar UI
        statusLabel.innerHTML = '<i class="fas fa-check"></i> Válido';
        statusLabel.className = "status-badge status-connected"; // Verde
        statusLabel.style.background = "#dcfce7";
        statusLabel.style.color = "#16a34a";
        
        mostrarAngulosResultado(pendingSolution);
        
        btnMover.disabled = false;
        btnMover.style.opacity = "1";
        btnMover.innerHTML = '<i class="fas fa-play"></i> Mover Robot';

    } else {
        // --- ERROR: Posición Inalcanzable o Colisión ---
        pendingSolution = null;
        
        statusLabel.innerHTML = '<i class="fas fa-exclamation-triangle"></i> Inalcanzable';
        statusLabel.className = "status-badge status-disconnected"; // Rojo
        statusLabel.style.background = "#fee2e2";
        statusLabel.style.color = "#dc2626";
        
        // Opcional: Podríamos pintar el fantasma de rojo aquí si simulation tuviera ese método
        // simulation.tintGhost(0xff0000);
        
        displayResult.innerHTML = "<span style='color:#ef4444;'>Sin solución geométrica</span>";
        
        btnMover.disabled = true;
        btnMover.style.opacity = "0.5";
        btnMover.innerHTML = '<i class="fas fa-ban"></i> Bloqueado';
    }
}

function mostrarAngulosResultado(servos) {
    const contenedor = document.getElementById('angulos-resultado');
    const labels = ["Base", "Hombro", "Codo", "Pitch", "Roll"];
    let html = "";
    for(let i=0; i<5; i++) {
        html += `<span>${labels[i]}: <b>${Math.round(servos[i])}°</b></span>`;
    }
    contenedor.innerHTML = html;
}

// ==========================================
// 4. EJECUCIÓN FÍSICA
// ==========================================

async function ejecutarMovimiento() {
    if (!pendingSolution) return;

    const btn = document.getElementById('btn-calcular-mover');
    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-cog fa-spin"></i> Moviendo...';

    // 1. Mover Robot Real (Llamada al Backend)
    // Usamos el API existente. Esto es asíncrono.
    await RobotAPI.moverServos(pendingSolution, 50); // Velocidad media por defecto

    // 2. Feedback final
    // Ocultar fantasma porque el real ya llegó (o va a llegar)
    // Esperamos un poco para dar sensación de completado
    setTimeout(() => {
        simulation.setGhostVisible(false);
        // Actualizamos la posición del robot "Real" en la simulación para que coincida
        simulation.updateAngles(pendingSolution, false);
        
        btn.disabled = false;
        btn.innerHTML = '<i class="fas fa-calculator"></i> Calcular y Mover';
    }, 800);
}

// ==========================================
// 5. GESTIÓN DE PUNTOS (Guardar Coordenadas)
// ==========================================

document.getElementById('save-point-btn').addEventListener('click', async () => {
    const nombre = document.getElementById('point-name').value.trim();
    if (!nombre) return alert("Escribe un nombre.");

    // Guardamos la INTENCIÓN (Coordenadas), no los ángulos.
    const data = {
        name: nombre,
        x: target.x,
        y: target.y,
        z: target.z,
        roll: target.roll,
        pitch: target.pitch,
        yaw: 0
    };

    const msg = await RobotAPI.guardarPunto(data);
    alert(msg);
    cargarListaPuntos();
});

async function cargarListaPuntos() {
    const puntos = await RobotAPI.listarPuntos();
    const lista = document.getElementById('saved-points-list');
    lista.innerHTML = '';

    if (!puntos || puntos.length === 0) {
        lista.innerHTML = '<li class="movement-item" style="justify-content:center; color:#94a3b8;">Sin puntos</li>';
        return;
    }

    puntos.forEach(nombre => {
        const li = document.createElement('li');
        li.className = 'movement-item';
        li.innerHTML = `
            <span>${nombre}</span>
            <div class="item-actions">
                <button class="btn-icon text-blue" onclick="cargarPunto('${nombre}')" title="Cargar"><i class="fas fa-upload"></i></button>
                <button class="btn-icon text-red" onclick="borrarPunto('${nombre}')"><i class="fas fa-trash"></i></button>
            </div>
        `;
        lista.appendChild(li);
    });
}

// Función global para cargar un punto guardado en los inputs
window.cargarPunto = async (nombre) => {
    const rawData = await RobotAPI.verPunto(nombre);
    
    // Parseo simple del archivo de texto (formato: "Posicion: X=100...")
    try {
        const x = parseFloat(rawData.match(/X=(-?[\d.]+)/)[1]);
        const y = parseFloat(rawData.match(/Y=(-?[\d.]+)/)[1]);
        const z = parseFloat(rawData.match(/Z=(-?[\d.]+)/)[1]);
        const pitch = parseFloat(rawData.match(/Pitch=(-?[\d.]+)/)[1]);
        
        let roll = 0;
        const matchRoll = rawData.match(/Roll=(-?[\d.]+)/);
        if(matchRoll) roll = parseFloat(matchRoll[1]);

        // Actualizar UI y Target
        actualizarInputsUI({x, y, z, pitch});
        document.getElementById('val-roll').value = roll;
        target.roll = roll;

        // Trigger cálculo fantasma instantáneo
        requestGhostCalculation();
        
    } catch(e) {
        alert("Error leyendo el formato del punto.");
        console.error(e);
    }
};

window.borrarPunto = async (nombre) => {
    if(confirm("¿Borrar punto permanentemente?")) {
        await RobotAPI.borrarPunto(nombre);
        cargarListaPuntos();
    }
};

// ==========================================
// 6. GESTIÓN DE SECUENCIAS (Rutas)
// ==========================================
let pasosSecuencia = [];

document.getElementById('save-position').addEventListener('click', () => {
    if (!pendingSolution) return alert("Primero obtén una posición válida (check verde).");
    
    // Añadimos el paso a la lista temporal
    pasosSecuencia.push({
        servos: [...pendingSolution],
        velocidad: 50, 
        coord_ref: {...target} // Guardamos ref de coordenadas para mostrar en lista
    });
    renderizarPasos();
});

document.getElementById('save-movement').addEventListener('click', async () => {
    const nombre = document.getElementById('movement-name').value.trim();
    if(!nombre || pasosSecuencia.length === 0) return alert("Falta nombre o pasos para guardar.");
    
    await RobotAPI.guardarMovimiento(nombre, pasosSecuencia);
    alert("Ruta guardada exitosamente.");
    pasosSecuencia = [];
    renderizarPasos();
    document.getElementById('movement-name').value = "";
    cargarBibliotecaMovimientos();
});

function renderizarPasos() {
    const ul = document.getElementById('positions-list');
    ul.innerHTML = '';
    
    if(pasosSecuencia.length === 0) {
        ul.innerHTML = '<li class="movement-item" style="justify-content:center; color:#94a3b8;">Sin pasos</li>';
        return;
    }
    
    pasosSecuencia.forEach((p, i) => {
        const li = document.createElement('li');
        li.className = 'movement-item';
        li.innerHTML = `
            <span><b>P${i+1}:</b> X:${p.coord_ref.x} Y:${p.coord_ref.y} Z:${p.coord_ref.z}</span>
            <button class="btn-icon text-red" onclick="eliminarPaso(${i})"><i class="fas fa-times"></i></button>
        `;
        ul.appendChild(li);
    });
}

window.eliminarPaso = (i) => {
    pasosSecuencia.splice(i, 1);
    renderizarPasos();
};

// Carga inicial de biblioteca (Solo lectura aquí)
async function cargarBibliotecaMovimientos() {
    const archivos = await RobotAPI.obtenerMovimientos();
    const lista = document.getElementById('movements-list');
    lista.innerHTML = '';

    if (!archivos || archivos.length === 0) {
        lista.innerHTML = '<li class="movement-item" style="justify-content:center; color:#94a3b8;">Biblioteca vacía</li>';
        return;
    }

    archivos.forEach(archivo => {
        const nombreDisplay = archivo.replace('.txt', '');
        const li = document.createElement('li');
        li.className = 'movement-item';
        li.innerHTML = `<span><i class="fas fa-file-code"></i> ${nombreDisplay}</span>`;
        lista.appendChild(li);
    });
}