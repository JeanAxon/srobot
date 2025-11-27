import tensorflow as tf
import numpy as np
import cv2

def cargar_modelo(model_path):
    """Carga el modelo TensorFlow Lite."""
    interpreter = tf.lite.Interpreter(model_path=model_path)
    interpreter.allocate_tensors()
    return interpreter

def preprocesar_imagen(frame):
    """Preprocesa la imagen para el modelo (ajustar tamaño y normalizar)."""
    input_data = cv2.resize(frame, (224, 224))  # Ajustar tamaño según el modelo
    input_data = np.expand_dims(input_data, axis=0)  # Añadir batch dimension
    input_data = np.float32(input_data)  # Convertir a float32 para TensorFlow Lite
    input_data = input_data / 255.0  # Normalización
    return input_data

def obtener_prediccion(interpreter, input_data):
    """Obtiene la predicción del modelo."""
    input_details = interpreter.get_input_details()
    output_details = interpreter.get_output_details()

    interpreter.set_tensor(input_details[0]['index'], input_data)
    interpreter.invoke()

    output_data = interpreter.get_tensor(output_details[0]['index'])
    predicted_class = np.argmax(output_data)  # Clase predicha
    return predicted_class, output_data

def reconocimiento_de_objetos(frame, interpreter, labels):
    """
    Realiza el reconocimiento de objetos en un frame utilizando un intérprete cargado.
    """
    input_data = preprocesar_imagen(frame)
    predicted_class, _ = obtener_prediccion(interpreter, input_data)

    # Obtener la etiqueta correspondiente a la clase predicha
    label = labels[predicted_class]
    return label
