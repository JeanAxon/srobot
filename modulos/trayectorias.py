import numpy as np
from modulos.cinematica_inversa import calcular_angulos

def generar_trayectoria_lineal(inicio, fin, pasos=20):
    """
    Genera una lista de configuraciones de servos para mover el robot
    en línea recta desde el punto 'inicio' hasta 'fin'.
    
    Args:
        inicio (dict): {x, y, z, pitch, roll, gripper}
        fin (dict):    {x, y, z, pitch, roll, gripper}
        pasos (int):   Cantidad de puntos intermedios (resolución).
    
    Returns:
        list: Lista de arrays [s1, s2, s3, s4, s5, s6]
    """
    trayectoria_servos = []
    
    # Interpolación Lineal (LERP) para cada coordenada
    xs = np.linspace(inicio['x'], fin['x'], pasos)
    ys = np.linspace(inicio['y'], fin['y'], pasos)
    zs = np.linspace(inicio['z'], fin['z'], pasos)
    
    # Interpolamos también el Pitch y Roll por si cambian durante el viaje
    pitches = np.linspace(inicio['pitch'], fin['pitch'], pasos)
    rolls = np.linspace(inicio['roll'], fin['roll'], pasos)
    
    # El gripper suele mantenerse o cambiar linealmente
    grippers = np.linspace(inicio['gripper'], fin['gripper'], pasos)

    for i in range(pasos):
        # 1. Calcular ángulos para este micro-paso
        angulos = calcular_angulos(xs[i], ys[i], zs[i], rolls[i], pitches[i], 0)
        
        if angulos is None:
            # Si un punto intermedio es inalcanzable, la línea recta es imposible
            print(f"Error: Punto intermedio {i} inalcanzable")
            return None 
            
        # 2. Construir el comando completo de 6 ejes
        # angulos trae [s1, s2, s3, s4]
        paso_completo = [
            angulos[0], 
            angulos[1], 
            angulos[2], 
            angulos[3], 
            rolls[i],    # S5
            grippers[i]  # S6
        ]
        trayectoria_servos.append(paso_completo)
        
    return trayectoria_servos