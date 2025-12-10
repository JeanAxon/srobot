/* =========================================================
   static/js/robot_api.js
   ---------------------------------------------------------
   Cliente API unificado.
   Mapea las funciones JavaScript a las rutas de Flask definidas 
   en routes_api.py.
   ========================================================= */

const RobotAPI = {

    // ==========================================
    // 1. CONEXIÓN Y ESTADO (Serial / Modbus)
    // ==========================================

    listarPuertos: async () => {
        try {
            const res = await fetch("/listar_puertos");
            return await res.json();
        } catch (e) { console.error("Error listarPuertos:", e); return []; }
    },

    conectarSerial: async (puerto) => {
        // Nota: El backend espera el puerto en la URL, codificado por si tiene barras (Linux)
        const puertoEncoded = encodeURIComponent(puerto);
        try {
            const res = await fetch(`/conectar_serial/${puertoEncoded}`, { method: "POST" });
            return await res.text();
        } catch (e) { console.error("Error conectarSerial:", e); return "Error de red"; }
    },

    verificarConexion: async () => {
        try {
            const res = await fetch("/status_connection");
            return await res.json(); // { connected: bool, port: string }
        } catch (e) { return { connected: false }; }
    },

    obtenerEstadoModbus: async () => {
        try {
            const res = await fetch("/modbus/estado");
            return await res.json();
        } catch (e) { return { status: "Error red" }; }
    },

    obtenerDatosPLC: async () => {
        try {
            const res = await fetch("/modbus/datos_plc");
            return await res.json();
        } catch (e) { return { datos: [], status: "error" }; }
    },

    // ==========================================
    // 2. CONTROL DE HARDWARE (Brazo y Banda)
    // ==========================================

    /**
     * @param {string} accion - 'activar', 'desactivar', 'derecha', 'izquierda'
     */
    controlBanda: async (accion) => {
        try {
            const res = await fetch(`/control_banda/${accion}`, { method: "POST" });
            return await res.text();
        } catch (e) { console.error("Error controlBanda:", e); }
    },

    /**
     * @param {Array} servos - [Base, Hombro, Codo, M.Vertical, M.Rotacion, Gripper]
     * @param {Number} velocidad - 0 a 100
     */
    moverServos: async (servos, velocidad) => {
        try {
            const res = await fetch("/control_brazo/mover_servos_global", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ servos, velocidad })
            });
            return await res.text();
        } catch (e) { console.error("Error moverServos:", e); }
    },

    // ==========================================
    // 3. CINEMÁTICA Y PUNTOS
    // ==========================================

    calcularPosicionGripper: async (servos) => {
        // Cinemática Directa (Ángulos -> Coordenadas XYZ)
        try {
            const res = await fetch("/calcular_posicion_gripper", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ servos })
            });
            return await res.json();
        } catch (e) { return { error: true }; }
    },

    calcularAngulos: async (coords) => {
        // Cinemática Inversa (Coordenadas XYZ -> Ángulos)
        // coords: { x, y, z, roll, pitch, yaw }
        try {
            const res = await fetch("/calcular_angulos", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(coords)
            });
            return await res.json();
        } catch (e) { return { error: true }; }
    },

    guardarPunto: async (datosPunto) => {
        // datosPunto: { name, x, y, z, roll, pitch, yaw }
        try {
            const res = await fetch("/guardar_punto", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(datosPunto)
            });
            return await res.text();
        } catch (e) { console.error("Error guardarPunto:", e); }
    },

    listarPuntos: async () => {
        try {
            const res = await fetch("/listar_puntos");
            return await res.json();
        } catch (e) { return []; }
    },

    borrarPunto: async (nombre) => {
        try {
            const res = await fetch(`/borrar_punto/${nombre}`, { method: "DELETE" });
            return await res.text();
        } catch (e) { console.error("Error borrarPunto:", e); }
    },

    verPunto: async (nombre) => {
        try {
            const res = await fetch(`/ver_punto/${nombre}`);
            return await res.text();
        } catch (e) { return ""; }
    },

    obtenerAreaTrabajo: async () => {
        try {
            const res = await fetch("/obtener_area_trabajo");
            return await res.json();
        } catch (e) { return { points: [] }; }
    },

    // ==========================================
    // 4. MOVIMIENTOS (Archivos .txt)
    // ==========================================

    guardarMovimiento: async (nombre, pasos) => {
        try {
            const res = await fetch("/guardar_movimiento", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ movementName: nombre, posiciones: pasos })
            });
            return await res.text();
        } catch (e) { console.error("Error guardarMovimiento:", e); }
    },

    obtenerMovimientos: async () => {
        try {
            const res = await fetch("/obtener_movimientos");
            return await res.json();
        } catch (e) { return []; }
    },

    cargarMovimiento: async (nombre) => {
        try {
            const res = await fetch(`/cargar_movimiento/${nombre}`, { method: "POST" });
            if (!res.ok) throw new Error("No encontrado");
            return await res.json();
        } catch (e) { return null; }
    },

    ejecutarMovimiento: async (nombre) => {
        try {
            const res = await fetch(`/ejecutar_movimiento/${nombre}`, { method: "POST" });
            return await res.json();
        } catch (e) { console.error("Error ejecutarMovimiento:", e); }
    },

    borrarMovimiento: async (nombre) => {
        try {
            const res = await fetch(`/borrar_movimiento/${nombre}`, { method: "DELETE" });
            return await res.text();
        } catch (e) { console.error("Error borrarMovimiento:", e); }
    },

    // ==========================================
    // 5. LÓGICA Y EJECUCIÓN
    // ==========================================

    iniciarEjecucion: async () => {
        try {
            await fetch("/iniciar_ejecucion", { method: "POST" });
        } catch (e) { console.error("Error iniciar:", e); }
    },

    detenerEjecucion: async () => {
        try {
            await fetch("/detener_ejecucion", { method: "POST" });
        } catch (e) { console.error("Error detener:", e); }
    },

    guardarLogica: async (reglas) => {
        try {
            const res = await fetch("/guardar_logica", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(reglas)
            });
            return await res.text();
        } catch (e) { console.error("Error guardarLogica:", e); }
    },

    cargarLogica: async () => {
        try {
            const res = await fetch("/cargar_logica");
            return await res.json();
        } catch (e) { return []; }
    },

    obtenerEstadoGlobal: async () => {
        // Lee el archivo estado.json (persistencia del backend)
        try {
            const res = await fetch("/obtener_estado");
            return await res.json();
        } catch (e) { return null; }
    }
};