import numpy as np
from cinematica_directa import forward_kinematics

# ========================== FUNCIÓN CINEMÁTICA INVERSA CCD ULTRA PRECISA ========================== #
def cinematica_inversa_CCD(target_pos, max_iter=1200, tol_pos=0.2, tol_orient=0.3):
    """
    Resuelve la cinemática inversa usando CCD con refinamiento avanzado para orientación.

    target_pos: Diccionario {'x':X, 'y':Y, 'z':Z, 'roll':R, 'pitch':P, 'yaw':Y}
    max_iter: Número máximo de iteraciones.
    tol_pos: Tolerancia para la convergencia en posición (mm).
    tol_orient: Tolerancia para la convergencia en orientación (grados).
    """
    q_actual = np.radians([90, 90, 90, 90, 90])  # Iniciamos en Home
    sin_mejora = 0  # Contador de iteraciones sin mejora
    fase_orientacion = False  # Fase de ajuste fino de orientación

    for iteracion in range(max_iter):
        estado_actual = forward_kinematics(np.degrees(q_actual))

        # 🔹 Extraemos solo X, Y, Z y orientación
        pos_actual = np.array([estado_actual['x'], estado_actual['y'], estado_actual['z']])
        orient_actual = np.array([estado_actual['roll'], estado_actual['pitch'], estado_actual['yaw']])
        
        pos_objetivo = np.array([target_pos['x'], target_pos['y'], target_pos['z']])
        orient_objetivo = np.array([target_pos['roll'], target_pos['pitch'], target_pos['yaw']])

        error_pos = np.linalg.norm(pos_objetivo - pos_actual)  # Error en posición (mm)
        error_orient = np.linalg.norm(orient_objetivo - orient_actual)  # Error en orientación (grados)

        # 🔹 Si la posición es precisa pero la orientación no, pasamos a la fase de ajuste fino
        if error_pos < tol_pos and not fase_orientacion:
            print(f"🔄 Cambio de estrategia: Posición óptima alcanzada, refinando orientación.")
            fase_orientacion = True  # Cambiamos a modo de ajuste de orientación

        # 🔹 Si el error en posición y orientación está dentro de la tolerancia, devolvemos la solución
        if error_pos < tol_pos and error_orient < tol_orient:
            print(f"✅ Solución encontrada en {iteracion} iteraciones con error de {error_pos:.2f} mm y orientación {error_orient:.2f}°")
            return np.degrees(q_actual)  # Devolver en grados

        # 🔹 Ajustamos dinámicamente el paso
        paso = np.radians(2) if error_pos > 10 else np.radians(0.8) if error_pos > 3 else np.radians(0.2)

        mejor_error = error_pos + error_orient

        # 🔹 CCD ahora se enfoca primero en posición, luego en orientación si es necesario
        articulaciones = range(len(q_actual)) if fase_orientacion else reversed(range(len(q_actual)))

        # 🔹 Ajustamos cada articulación
        for i in articulaciones:
            q_temp = q_actual.copy()
            q_temp[i] += paso  # Mover la articulación en una dirección
            estado_mas = forward_kinematics(np.degrees(q_temp))
            pos_mas = np.array([estado_mas['x'], estado_mas['y'], estado_mas['z']])
            orient_mas = np.array([estado_mas['roll'], estado_mas['pitch'], estado_mas['yaw']])
            error_mas = np.linalg.norm(pos_mas - pos_objetivo) + np.linalg.norm(orient_mas - orient_objetivo)

            q_temp[i] -= 2 * paso  # Mover en la otra dirección
            estado_menos = forward_kinematics(np.degrees(q_temp))
            pos_menos = np.array([estado_menos['x'], estado_menos['y'], estado_menos['z']])
            orient_menos = np.array([estado_menos['roll'], estado_menos['pitch'], estado_menos['yaw']])
            error_menos = np.linalg.norm(pos_menos - pos_objetivo) + np.linalg.norm(orient_menos - orient_objetivo)

            # 🔹 Aplicamos la mejor modificación
            if error_mas < mejor_error:
                q_actual[i] += paso
                mejor_error = error_mas
                sin_mejora = 0
            elif error_menos < mejor_error:
                q_actual[i] -= paso
                mejor_error = error_menos
                sin_mejora = 0
            else:
                sin_mejora += 1

        # 🔹 Si no mejora en 50 iteraciones, cambiamos la estrategia
        if sin_mejora > 50:
            print("🔄 Cambio de estrategia: aumentando paso momentáneamente.")
            paso *= 1.5
            sin_mejora = 0

    print(f"⚠️ No se encontró solución exacta dentro de {max_iter} iteraciones, error final: {error_pos:.2f} mm y orientación {error_orient:.2f}°")
    return np.degrees(q_actual)  # Devolver la mejor solución encontrada

def calcular_angulos(x, y, z, roll, pitch, yaw):
    """Wrapper para manejar tipos de datos"""
    try:
        target_pos = {
            'x': float(x),
            'y': float(y),
            'z': float(z),
            'roll': float(roll),
            'pitch': float(pitch),
            'yaw': float(yaw)
        }
        angulos = cinematica_inversa_CCD(target_pos)
        return angulos.tolist() if isinstance(angulos, np.ndarray) else angulos
    except Exception as e:
        print(f"Error en cálculo de ángulos: {str(e)}")
        return [90.0, 90.0, 90.0, 90.0, 90.0]