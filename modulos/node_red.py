import requests
import time
import os
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import threading

# Rutas de los archivos y directorios
color_labels_path = '/home/mps/Desktop/servidorW/web/uploads/model_color/labels.txt'
form_labels_path = '/home/mps/Desktop/servidorW/web/uploads/model_form/labels.txt'
movimientos_dir = '/home/mps/Desktop/servidorW/web/movimientos'

# URLs de Node-RED
node_red_urls = {
    'colores': 'http://localhost:1880/colores_cargados',
    'formas': 'http://localhost:1880/formas_cargados',
    'movimientos': 'http://localhost:1880/movimientos_cargados'
}

def read_labels(file_path):
    """Lee un archivo de etiquetas y devuelve un diccionario."""
    labels = {}
    try:
        with open(file_path, 'r') as file:
            for line in file:
                parts = line.strip().split(' ', 1)
                if len(parts) == 2:
                    key = int(parts[0])
                    value = parts[1]
                    labels[key] = value
        print(f'Leídos labels de {file_path}: {labels}')
        return labels
    except FileNotFoundError:
        print(f'Error: No se encontró el archivo {file_path}')
        return {}
    except Exception as e:
        print(f'Error al leer {file_path}: {e}')
        return {}

def get_movimientos_files():
    """Obtiene la lista de nombres de archivos en el directorio de movimientos."""
    try:
        files = [f for f in os.listdir(movimientos_dir) if os.path.isfile(os.path.join(movimientos_dir, f))]
        print(f'Archivos en {movimientos_dir}: {files}')
        return files
    except Exception as e:
        print(f'Error al leer el directorio {movimientos_dir}: {e}')
        return []

def send_to_nodered(tipo, data):
    """Envía los datos a Node-RED mediante una solicitud POST."""
    url = node_red_urls.get(tipo)
    payload = {'data': data}
    try:
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            print(f'Datos de {tipo} enviados correctamente a {url}')
        else:
            print(f'Error al enviar datos de {tipo} a {url}: {response.status_code}')
    except requests.exceptions.RequestException as e:
        print(f'Error de conexión con Node-RED para {tipo}: {e}')

def send_initial_data():
    """Envía los datos iniciales a Node-RED en hilos separados para simultaneidad."""
    def send_in_thread(tipo, data):
        if data:
            send_to_nodered(tipo, data)
        else:
            print(f'No hay datos de {tipo} para enviar')

    # Leer datos
    color_labels = read_labels(color_labels_path)
    form_labels = read_labels(form_labels_path)
    movimientos_files = get_movimientos_files()

    # Enviar en paralelo
    threads = [
        threading.Thread(target=send_in_thread, args=('colores', color_labels)),
        threading.Thread(target=send_in_thread, args=('formas', form_labels)),
        threading.Thread(target=send_in_thread, args=('movimientos', movimientos_files))
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()  # Espera a que todos terminen
        
# Monitoreo de cambios
class FileChangeHandler(FileSystemEventHandler):
    def on_modified(self, event):
        if event.src_path == color_labels_path:
            print(f'Detectado cambio en {color_labels_path}')
            color_labels = read_labels(color_labels_path)
            if color_labels:
                send_to_nodered('colores', color_labels)
        elif event.src_path == form_labels_path:
            print(f'Detectado cambio en {form_labels_path}')
            form_labels = read_labels(form_labels_path)
            if form_labels:
                send_to_nodered('formas', form_labels)

    def on_any_event(self, event):
        if event.src_path.startswith(movimientos_dir) and not event.is_directory:
            print(f'Detectado cambio en el directorio {movimientos_dir}')
            movimientos_files = get_movimientos_files()
            if movimientos_files:
                send_to_nodered('movimientos', movimientos_files)

if __name__ == '__main__':
    send_initial_data()
    event_handler = FileChangeHandler()
    observer = Observer()
    observer.schedule(event_handler, path=color_labels_path, recursive=False)
    observer.schedule(event_handler, path=form_labels_path, recursive=False)
    observer.schedule(event_handler, path=movimientos_dir, recursive=True)
    observer.start()
    print('Monitoreando cambios...')
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()