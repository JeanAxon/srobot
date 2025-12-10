/* =========================================================
   static/js/kinematics.js
   ---------------------------------------------------------
   Motor de Cinemática Inversa (IK) local.
   Permite cálculos en tiempo real (0ms latencia) para Ghosting.
   ========================================================= */

const ROBOT_GEOMETRY = {
    // Ajusta estas medidas (en mm) según tu robot físico:
    d1: 100,  // Altura Base hasta eje Hombro
    a2: 105,  // Longitud Hombro a Codo
    a3: 100,  // Longitud Codo a Muñeca Vertical
    d5: 150   // Longitud desde Muñeca Vertical hasta TCP (Punta de pinza)
};

/**
 * Calcula los ángulos para un brazo de 5 GDL.
 * @param {number} x - Coordenada X (mm)
 * @param {number} y - Coordenada Y (mm)
 * @param {number} z - Coordenada Z (mm)
 * @param {number} pitch - Ángulo de la muñeca respecto al horizonte (grados)
 * @param {number} roll - Rotación de la muñeca (grados)
 * @returns {Object} { angles: [s1, s2, s3, s4, s5], isValid: boolean }
 */
function solveIK_5DOF(x, y, z, pitch, roll) {
    const { d1, a2, a3, d5 } = ROBOT_GEOMETRY;
    const toRad = Math.PI / 180;
    const toDeg = 180 / Math.PI;

    // 1. ÁNGULO BASE (Theta 1)
    // Atan2 nos da el ángulo en el plano XY
    let theta1 = Math.atan2(y, x);

    // 2. CALCULAR EL "CENTRO DE LA MUÑECA" (Wrist Center)
    // El TCP está a una distancia d5 con un ángulo 'pitch'.
    // Retrocedemos desde el TCP para encontrar dónde debe estar la articulación de la muñeca.
    const pitchRad = pitch * toRad;
    
    // Proyección radial (distancia horizontal desde el centro)
    const r_tcp = Math.sqrt(x*x + y*y); 
    
    // Coordenadas del centro de la muñeca (r_wc, z_wc)
    const r_wc = r_tcp - d5 * Math.cos(pitchRad);
    const z_wc = z - d5 * Math.sin(pitchRad) - d1; // Restamos altura base

    // 3. RESOLUCIÓN DEL TRIÁNGULO (Hombro - Codo - Muñeca)
    // Hipotenusa desde el hombro hasta el centro de la muñeca
    const h = Math.sqrt(r_wc*r_wc + z_wc*z_wc);

    // Validar alcance (si h > brazo estirado, no llega)
    if (h > (a2 + a3)) {
        return { angles: [0,0,0,0,0], isValid: false }; // Inalcanzable
    }

    // Ley de Cosenos para encontrar ángulos internos del triángulo
    // Cosines of alpha (ángulo en hombro interno) and beta (ángulo en codo)
    // a3^2 = a2^2 + h^2 - 2*a2*h * cos(alpha)
    const cos_alpha = (a2*a2 + h*h - a3*a3) / (2 * a2 * h);
    const cos_beta  = (a2*a2 + a3*a3 - h*h) / (2 * a2 * a3);
    
    // Evitar errores numéricos si cos es > 1 o < -1
    if (Math.abs(cos_alpha) > 1 || Math.abs(cos_beta) > 1) return { angles: [], isValid: false };

    const alpha = Math.acos(cos_alpha); // Ángulo interno hombro
    const beta  = Math.acos(cos_beta);  // Ángulo interno codo

    // Ángulo de elevación de la hipotenusa
    const gamma = Math.atan2(z_wc, r_wc);

    // --- CÁLCULO FINAL DE ÁNGULOS (Theta 2 y Theta 3) ---
    // Theta 2 (Hombro): Gamma + Alpha (o Gamma - Alpha dependiendo de la config "codo arriba/abajo")
    let theta2 = gamma + alpha; 
    
    // Theta 3 (Codo): El ángulo externo. Beta es el interno.
    // Dependiendo de cómo definas tus servos, suele ser (PI - beta) o similar.
    // Aquí asumimos cero geométrico alineado:
    let theta3 = -1 * (Math.PI - beta); 

    // --- CÁLCULO DE MUÑECA (Theta 4) ---
    // La suma de ángulos debe dar el pitch global deseado.
    // Pitch = Theta2 + Theta3 + Theta4
    // Theta4 = Pitch - Theta2 - Theta3
    let theta4 = pitchRad - theta2 - theta3;

    // --- CONVERSIÓN A GRADOS Y MAPEO DE SERVOS ---
    // Ajusta estos offsets según tu calibración física (ej. si 90° es recto)
    const s1 = theta1 * toDeg;       // Base: 0 suele ser frente
    const s2 = theta2 * toDeg;       // Hombro: 90 suele ser vertical
    const s3 = theta3 * toDeg;       // Codo: 0 suele ser alineado con hombro
    const s4 = theta4 * toDeg;       // Muñeca V
    const s5 = roll;                 // Muñeca R (Passthrough)

    // Ajuste de "Coordenadas Matemáticas" a "Coordenadas Servo (0-180)"
    // ESTO DEPENDE TOTALMENTE DE CÓMO MONTASTE LOS SERVOS. EJEMPLO COMÚN:
    const finalAngles = [
        Math.round(90 + s1), // Base centrada en 90
        Math.round(90 - s2), // Hombro: invertir o ajustar offset
        Math.round(90 + s3), // Codo
        Math.round(90 + s4), // Muñeca compensada
        Math.round(s5)       // Roll directo
    ];

    // Validar límites físicos (0 a 180)
    const inRange = finalAngles.every(a => a >= 0 && a <= 180);

    return {
        angles: finalAngles,
        isValid: inRange
    };
}