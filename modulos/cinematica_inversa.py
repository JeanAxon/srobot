import math

# ==========================================
# CONFIGURACIÓN FÍSICA DEL ROBOT (Medidas en cm o mm)
# ==========================================
# Basado en tu archivo config.js y Brazo_Robotico.html
# Asegúrate de que estas unidades coincidan con lo que envías (mm recomendado)

L_BASE = 5.0      # Altura de la base (d1)
L_HOMBRO = 10.0   # Longitud del brazo (a2)
L_ANTEBRAZO = 8.0 # Longitud del antebrazo (a3)
L_MUNECA = 3.0    # Longitud de la mano/gripper hasta el TCP (d_wrist_tcp)

def calcular_angulos(x, y, z, roll, pitch, yaw):
    """
    Calcula la Cinemática Inversa para un brazo de 5GDL (sin Yaw de muñeca).
    
    Args:
        x, y, z: Coordenadas del efector final.
        pitch: Inclinación deseada de la muñeca (grados).
               0 = Horizontal, -90 = Mirando abajo.
        roll, yaw: Se ignoran para el cálculo geométrico (el Roll es passthrough).
    
    Returns:
        list: [Angulo1, Angulo2, Angulo3, Angulo4] o None si es inalcanzable.
    """
    try:
        # 1. Ángulo de la BASE (S1)
        # ------------------------------------------------
        # Es simplemente la rotación hacia el punto (x,y)
        theta1 = math.atan2(y, x)
        
        # 2. Calcular el CENTRO DE LA MUÑECA (Wrist Center)
        # ------------------------------------------------
        # Retrocedemos desde el punto objetivo (TCP) una distancia L_MUNECA
        # en la dirección del Pitch deseado.
        pitch_rad = math.radians(pitch)
        
        # Proyección del retroceso en el plano horizontal y vertical
        # Asumimos que el pitch es relativo al horizonte
        dx = L_MUNECA * math.cos(pitch_rad) * math.cos(theta1)
        dy = L_MUNECA * math.cos(pitch_rad) * math.sin(theta1)
        dz = L_MUNECA * math.sin(pitch_rad)
        
        # Coordenadas del centro de la muñeca
        wx = x - dx
        wy = y - dy
        wz = z - dz
        
        # 3. Problema Plano (Triángulo Hombro-Codo-Muñeca)
        # ------------------------------------------------
        # Distancia horizontal desde el eje del hombro hasta el centro de la muñeca
        # r es la proyección radial en el suelo
        r = math.sqrt(wx**2 + wy**2)
        
        # Altura de la muñeca respecto al hombro
        # Restamos la altura de la base
        h = wz - L_BASE
        
        # Distancia directa desde el hombro hasta la muñeca (hipotenusa)
        c = math.sqrt(r**2 + h**2)
        
        # VALIDACIÓN: ¿Alcanza el brazo?
        if c > (L_HOMBRO + L_ANTEBRAZO):
            return None # El punto está demasiado lejos
            
        # 4. Ley de Cosenos para Hombro (S2) y Codo (S3)
        # ------------------------------------------------
        # Ángulo alfa (elevación del vector hombro-muñeca)
        alpha = math.atan2(h, r)
        
        # Ángulo beta (triángulo interior por ley de cosenos)
        cos_beta = (L_HOMBRO**2 + c**2 - L_ANTEBRAZO**2) / (2 * L_HOMBRO * c)
        
        # Protección matemática por errores de redondeo
        cos_beta = max(-1, min(1, cos_beta))
        beta = math.acos(cos_beta)
        
        # Theta2: Ángulo del Hombro
        theta2 = alpha + beta 
        
        # Ángulo gamma (ángulo del codo interior)
        cos_gamma = (L_HOMBRO**2 + L_ANTEBRAZO**2 - c**2) / (2 * L_HOMBRO * L_ANTEBRAZO)
        cos_gamma = max(-1, min(1, cos_gamma))
        gamma = math.acos(cos_gamma)
        
        # Theta3: Ángulo del Codo (relativo al brazo anterior)
        # Nota: Depende de cómo estén montados tus servos (0 grados = recto o doblado?)
        # Asumiremos configuración estándar: 0 es brazo estirado.
        theta3 = gamma - math.pi 
        
        # 5. Ángulo de la Muñeca Vertical (S4)
        # ------------------------------------------------
        # La suma de los ángulos (Hombro + Codo + Muñeca) debe dar el Pitch global
        # Pitch_Global = Theta2 + Theta3 + Theta4
        theta4 = pitch_rad - (theta2 + theta3)
        
        # 6. Conversión a Grados y Mapeo a Servos (0-180)
        # ------------------------------------------------
        # Esto depende de tu hardware. Asumiremos:
        # 90 grados es la posición "neutra" o "Home".
        
        ang_base = math.degrees(theta1)
        ang_hombro = math.degrees(theta2)
        ang_codo = math.degrees(theta3)
        ang_muneca = math.degrees(theta4)

        # AJUSTES DE HARDWARE (Mapeo Final)
        # Ajusta estos offsets según cómo pusiste los horns de tus servos
        
        # Base: atan2 da -180 a 180. Mapeamos 0 -> 90.
        s1 = 90 + ang_base 
        
        # Hombro: 90 es vertical.
        s2 = 90 - ang_hombro # O + dependiendo del sentido de giro
        
        # Codo: 
        s3 = 90 + ang_codo 
        
        # Muñeca: 
        s4 = 90 + ang_muneca

        # Retornamos los 4 ángulos calculados
        # El Roll (s5) y Gripper (s6) se añaden en el JS o se pasan directo
        return [s1, s2, s3, s4]
        
    except Exception as e:
        print(f"Error en cinemática: {e}")
        return None