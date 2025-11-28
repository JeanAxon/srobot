# Se eliminó la línea "import tflite_runtime.interpreter as tflite" porque no es necesaria aquí.
import numpy as np
import cv2
import os

COLOR_RANGES = {
    "rojo": [
        (0, 80, 70),   (10, 255, 255),   # Rango rojo 1
        (170, 80, 70), (180, 255, 255)
    ],
    "verde": [
        (35, 30, 30), (85, 255, 255)
    ],
    "azul": [
        (90, 30, 30), (130, 255, 255)
    ],
    "vacio": []
}

def corregir_iluminacion(frame):
    lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    l_corr = clahe.apply(l)
    lab_corr = cv2.merge((l_corr, a, b))
    return cv2.cvtColor(lab_corr, cv2.COLOR_LAB2BGR)

def preprocesar_imagen(frame):
    if frame is None:
        return None
    frame_corr = corregir_iluminacion(frame)
    frame_rgb = cv2.cvtColor(frame_corr, cv2.COLOR_BGR2RGB)
    input_data = cv2.resize(frame_rgb, (224, 224))
    input_data = np.expand_dims(input_data, axis=0)
    return np.float32(input_data) / 255.0

def obtener_prediccion(interpreter, input_data, threshold=0.6):
    try:
        input_details = interpreter.get_input_details()
        output_details = interpreter.get_output_details()
        interpreter.set_tensor(input_details[0]['index'], input_data)
        interpreter.invoke()
        output_data = interpreter.get_tensor(output_details[0]['index'])[0]

        class_idx = np.argmax(output_data)
        max_prob = output_data[class_idx]
        if max_prob < threshold:
            return None, output_data
        return class_idx, output_data
    except Exception as e:
        print(f"❌ Error en predicción: {e}")
        return None, None

def detectar_color_hsv(frame, area_threshold_ratio=0.01):
    hsv = cv2.cvtColor(corregir_iluminacion(frame), cv2.COLOR_BGR2HSV)
    h, w = hsv.shape[:2]
    total_area = h * w

    kernel = np.ones((3,3), np.uint8)
    detecciones = {}

    for color, ranges in COLOR_RANGES.items():
        if color == "vacio":
            continue
        mask = None
        for i in range(0, len(ranges), 2):
            lower = np.array(ranges[i])
            upper = np.array(ranges[i+1])
            temp = cv2.inRange(hsv, lower, upper)
            # Limpieza
            temp = cv2.erode(temp, kernel, iterations=1)
            temp = cv2.dilate(temp, kernel, iterations=2)
            mask = temp if mask is None else cv2.bitwise_or(mask, temp)
        if mask is not None:
            count_pixels = cv2.countNonZero(mask)
            detecciones[color] = count_pixels
        else:
            detecciones[color] = 0

    if not detecciones:
        return "vacio"
    max_color = max(detecciones, key=detecciones.get)
    max_count = detecciones[max_color]
    ratio = max_count / float(total_area)
    if ratio < area_threshold_ratio:
        return "vacio"
    return max_color

def reconocimiento_de_objetos(frame,
                              interpreter_shape, shape_labels,
                              interpreter_color, color_labels,
                              shape_threshold=0.6, color_threshold=0.6):
    if frame is None:
        return "vacio_vacio"
    input_data = preprocesar_imagen(frame)
    if input_data is None:
        return "vacio_vacio"

    # Forma
    shape_class, _ = obtener_prediccion(interpreter_shape, input_data, threshold=shape_threshold)
    if shape_class is None:
        return "vacio_vacio"
    shape_label = shape_labels[shape_class]

    # Color
    color_class, _ = obtener_prediccion(interpreter_color, input_data, threshold=color_threshold)
    if color_class is None:
        return "vacio_vacio"
    color_label = color_labels[color_class]

    # Si literal es "vacio"
    if "vacio" in shape_label.lower() or "vacio" in color_label.lower():
        return "vacio_vacio"

    # HSV (opcional, si sigues usando rangos)
    color_hsv = detectar_color_hsv(frame, area_threshold_ratio=0.01)

    # Parsear etiquetas
    parts_shape = shape_label.split(' ', 1)
    if len(parts_shape) == 2:
        shape_id, shape_name = parts_shape
    else:
        shape_id = parts_shape[0]
        shape_name = "desconocido"

    color_prefix = None
    if color_hsv != "vacio":
        for clabel in color_labels:
            if '_' in clabel:
                cparts = clabel.split('_', 1)
            else:
                cparts = clabel.split(' ', 1)
            if len(cparts) == 2:
                cprefix, cname = cparts
                if cname.lower() == color_hsv.lower():
                    color_prefix = cprefix
                    break

    # Construir salida
    if color_prefix is not None and color_hsv != "vacio":
        return f"{shape_id} {shape_name}_{color_prefix} {color_hsv}"
    else:
        if '_' in color_label:
            cparts = color_label.split('_', 1)
        else:
            cparts = color_label.split(' ', 1)
        if len(cparts) == 2:
            cprefix, cname = cparts
            return f"{shape_id} {shape_name}_{cprefix} {cname}"
        else:
            return f"{shape_id} {shape_name}_0 desconocido"