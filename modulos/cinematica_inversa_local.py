# archivo: modulos/cinematica_inversa_local.py

import numpy as np
from scipy.optimize import minimize
from .cinematica_directa import forward_kinematics

def cinematica_inversa_local(
    target_pos, 
    q_inicial,          # en grados
    tol_pos=0.01, 
    tol_orient=0.01,
    lambda_config=5.0,
    maxiter=30
):
    """
    Cálculo local de cinemática inversa partiendo de q_inicial (en grados).
    Penaliza desviarse drásticamente de q_inicial para mantener continuidad.
    
    Retorna (q_sol_deg, success):
      - q_sol_deg: array/list de 5 ángulos en grados.
      - success: bool, indica si se llegó a la tolerancia.
    """
    q0_rad = np.radians(q_inicial)

    # Ajustar bounds a [0..180] => [0..pi] en rad
    bounds_rad = [(0, np.pi)] * 5

    # Minimización local con L-BFGS-B
    res = minimize(
        fun=costo_local,
        x0=q0_rad,
        args=(target_pos, q0_rad, lambda_config),
        method='L-BFGS-B',
        bounds=bounds_rad,
        jac=gradiente_costo_local,
        options={
            'maxiter': maxiter,
            'ftol': 1e-7,
            'disp': False
        }
    )

    q_sol_deg = np.degrees(res.x)

    # Verificamos error final
    estado = forward_kinematics(q_sol_deg)
    pos_final = np.array([estado['x'], estado['y'], estado['z']])
    pos_obj = np.array([target_pos['x'], target_pos['y'], target_pos['z']])
    error_pos = np.linalg.norm(pos_obj - pos_final)

    orient_final = np.array([estado['roll'], estado['pitch'], estado['yaw']])
    orient_obj = np.array([target_pos['roll'], target_pos['pitch'], target_pos['yaw']])
    error_orient = np.linalg.norm(orient_obj - orient_final)

    success = (error_pos < tol_pos) and (error_orient < tol_orient)
    return q_sol_deg, success

def costo_local(q_rad, target_pos, q_inicial_rad, lambda_config):
    """
    Costo: error pos/orient + penalización (q - q_inicial)^2
    """
    q_deg = np.degrees(q_rad)
    estado = forward_kinematics(q_deg)

    pos = np.array([estado['x'], estado['y'], estado['z']])
    pos_obj = np.array([target_pos['x'], target_pos['y'], target_pos['z']])
    error_pos = np.linalg.norm(pos_obj - pos)

    orient = np.array([estado['roll'], estado['pitch'], estado['yaw']])
    orient_obj = np.array([target_pos['roll'], target_pos['pitch'], target_pos['yaw']])
    error_orient = np.linalg.norm(orient_obj - orient)

    # Penalización
    diff_q = q_rad - q_inicial_rad
    penalty_config = np.linalg.norm(diff_q)**2

    peso_orient = 2.0
    costo = error_pos + peso_orient * error_orient + lambda_config * penalty_config

    return costo

def gradiente_costo_local(q_rad, target_pos, q_inicial_rad, lambda_config):
    """
    Gradiente numérico central.
    """
    delta = np.radians(0.01)
    grad = np.zeros_like(q_rad)
    for i in range(len(q_rad)):
        q_up = q_rad.copy()
        q_down = q_rad.copy()
        q_up[i] += delta
        q_down[i] -= delta

        c_up = costo_local(q_up,   target_pos, q_inicial_rad, lambda_config)
        c_dn = costo_local(q_down, target_pos, q_inicial_rad, lambda_config)

        grad[i] = (c_up - c_dn) / (2 * delta)

    return grad
