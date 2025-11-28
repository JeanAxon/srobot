import numpy as np
from cinematica_inversa import cinematica_inversa_ultrarrapida

# ========================== FUNCIÓN GENERADORA DE TRAYECTORIAS ========================== #
def generar_trayectoria(tipo, puntos, num_pasos=50):
    """
    Genera una trayectoria para el robot según el tipo especificado.

    tipo: 'lineal', 'circular', 'spline', 'ptp'
    puntos: Lista de diccionarios {'x':X, 'y':Y, 'z':Z, 'roll':R, 'pitch':P, 'yaw':Y}
    num_pasos: Número de puntos intermedios a generar en la trayectoria.
    
    Retorna:
    - Lista de ángulos articulares para cada paso de la trayectoria.
    """
    trayectoria_angulos = []

    if tipo == 'lineal':
        trayectoria = interpolacion_lineal(puntos[0], puntos[1], num_pasos)
    elif tipo == 'circular':
        trayectoria = interpolacion_circular(puntos[0], puntos[1], puntos[2], num_pasos)
    elif tipo == 'spline':
        trayectoria = interpolacion_spline(puntos, num_pasos)
    elif tipo == 'ptp':
        trayectoria = puntos  # No se interpolan puntos en PTP
    else:
        raise ValueError("❌ Tipo de trayectoria no válido. Usa 'lineal', 'circular', 'spline' o 'ptp'.")

    # 🔹 Calcular la cinemática inversa para cada punto de la trayectoria
    for punto in trayectoria:
        angulos = cinematica_inversa_ultrarrapida(punto)
        if angulos is not None:
            trayectoria_angulos.append(angulos)
        else:
            print(f"⚠️ No se pudo calcular cinemática inversa para {punto}")

    return trayectoria_angulos

# ========================== INTERPOLACIÓN LINEAL ========================== #
def interpolacion_lineal(p1, p2, num_pasos):
    """
    Genera una trayectoria lineal entre dos puntos.
    """
    return [
        {
            'x': np.linspace(p1['x'], p2['x'], num_pasos)[i],
            'y': np.linspace(p1['y'], p2['y'], num_pasos)[i],
            'z': np.linspace(p1['z'], p2['z'], num_pasos)[i],
            'roll': np.linspace(p1['roll'], p2['roll'], num_pasos)[i],
            'pitch': np.linspace(p1['pitch'], p2['pitch'], num_pasos)[i],
            'yaw': np.linspace(p1['yaw'], p2['yaw'], num_pasos)[i],
        }
        for i in range(num_pasos)
    ]

# ========================== INTERPOLACIÓN CIRCULAR ========================== #
def interpolacion_circular(p1, p2, p3, num_pasos):
    """
    Genera una trayectoria circular pasando por tres puntos clave.
    """
    p1_arr, p2_arr, p3_arr = np.array([p1['x'], p1['y'], p1['z']]), np.array([p2['x'], p2['y'], p2['z']]), np.array([p3['x'], p3['y'], p3['z']])
    
    # Centro del círculo
    A = np.linalg.norm(p1_arr - p2_arr)
    B = np.linalg.norm(p2_arr - p3_arr)
    C = np.linalg.norm(p3_arr - p1_arr)
    s = (A + B + C) / 2
    R = (A * B * C) / (4 * np.sqrt(s * (s - A) * (s - B) * (s - C)))
    
    centro = (p1_arr + p2_arr + p3_arr) / 3

    # Generar puntos en el arco
    angulos = np.linspace(0, np.pi, num_pasos)
    trayectoria = []
    
    for angulo in angulos:
        x = centro[0] + R * np.cos(angulo)
        y = centro[1] + R * np.sin(angulo)
        z = centro[2]
        trayectoria.append({'x': x, 'y': y, 'z': z, 'roll': p1['roll'], 'pitch': p1['pitch'], 'yaw': p1['yaw']})
    
    return trayectoria

# ========================== INTERPOLACIÓN SPLINE ========================== #
def interpolacion_spline(puntos, num_pasos):
    """
    Genera una trayectoria suave interpolando varios puntos con una curva spline.
    """
    from scipy.interpolate import CubicSpline

    t = np.linspace(0, 1, len(puntos))
    t_fino = np.linspace(0, 1, num_pasos)

    # Interpolar cada coordenada con un spline cúbico
    x_spline = CubicSpline(t, [p['x'] for p in puntos])
    y_spline = CubicSpline(t, [p['y'] for p in puntos])
    z_spline = CubicSpline(t, [p['z'] for p in puntos])
    roll_spline = CubicSpline(t, [p['roll'] for p in puntos])
    pitch_spline = CubicSpline(t, [p['pitch'] for p in puntos])
    yaw_spline = CubicSpline(t, [p['yaw'] for p in puntos])

    return [
        {'x': x_spline(ti), 'y': y_spline(ti), 'z': z_spline(ti), 'roll': roll_spline(ti), 'pitch': pitch_spline(ti), 'yaw': yaw_spline(ti)}
        for ti in t_fino
    ]


