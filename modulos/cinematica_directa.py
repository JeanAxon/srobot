import numpy as np

# Definición de la matriz DH según los parámetros proporcionados
dh_params = [
    {'theta': 0, 'd': 86.65, 'a': 0, 'alpha': 90},
    {'theta': 0, 'd': 0, 'a': 120, 'alpha': 0},
    {'theta': -90, 'd': 0, 'a': 115.48, 'alpha': 0},
    {'theta': 0, 'd': 0, 'a': 0, 'alpha': 90},
    {'theta': -90, 'd': 161.74, 'a': 0, 'alpha': 0}
]

def deg_to_rad(deg):
    """Convierte grados a radianes."""
    return np.radians(deg)

def dh_matrix(theta, d, a, alpha):
    """Calcula la matriz de transformación homogénea usando los parámetros DH."""
    theta = deg_to_rad(theta)
    alpha = deg_to_rad(alpha)
    
    return np.array([
        [np.cos(theta), -np.sin(theta) * np.cos(alpha),  np.sin(theta) * np.sin(alpha), a * np.cos(theta)],
        [np.sin(theta),  np.cos(theta) * np.cos(alpha), -np.cos(theta) * np.sin(alpha), a * np.sin(theta)],
        [0,             np.sin(alpha),                  np.cos(alpha),                 d],
        [0,             0,                              0,                              1]
    ])

def forward_kinematics(joint_angles):
    """
    Calcula la posición (x, y, z) y la orientación (ángulos de Euler)
    del gripper en base a los ángulos de los servos.
    """
    T = np.eye(4)  # Matriz identidad 4x4 (base de referencia)

    # Multiplicación de matrices DH para obtener la transformación final
    for i in range(len(dh_params)):
        theta = dh_params[i]['theta'] + joint_angles[i]  # Suma el ángulo del servo
        d = dh_params[i]['d']
        a = dh_params[i]['a']
        alpha = dh_params[i]['alpha']
        
        T = np.dot(T, dh_matrix(theta, d, a, alpha))

    # Extraer la posición del gripper
    x, y, z = T[0:3, 3]

    # Extraer la orientación en ángulos de Euler
    roll = np.arctan2(T[2, 1], T[2, 2])  # Rotación sobre X
    pitch = np.arcsin(-T[2, 0])          # Rotación sobre Y
    yaw = np.arctan2(T[1, 0], T[0, 0])   # Rotación sobre Z

    # Convertir a grados
    roll, pitch, yaw = np.degrees([roll, pitch, yaw])

    return {
        'x': round(x, 2),
        'y': round(y, 2),
        'z': round(z, 2),
        'roll': round(roll, 2),
        'pitch': round(pitch, 2),
        'yaw': round(yaw, 2)
    }

