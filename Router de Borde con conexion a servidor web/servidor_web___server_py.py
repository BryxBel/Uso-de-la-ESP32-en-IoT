import os
import socket
import sqlite3
from flask import Flask, render_template
from datetime import datetime
import threading

app = Flask(__name__)

# Configuración de la base de datos
db_path = os.path.join(os.path.dirname(__file__), "sensor_data.db")


def init_db():
    """Inicializa la base de datos creando las tablas necesarias."""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Crear tabla principal de datos
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS datos (
                nodo TEXT PRIMARY KEY,
                ipv6_global TEXT,
                temperatura REAL,
                humedad REAL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Crear tabla historial
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS historial (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nodo TEXT,
                temperatura REAL,
                humedad REAL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
        conn.close()
        print(f"Base de datos creada o conectada en: {db_path}")
    except sqlite3.Error as e:
        print(f"Error al inicializar la base de datos: {e}")


def update_db(nodo, ipv6_global, temperatura, humedad):
    """Actualiza la base de datos con nuevos datos de sensores."""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Actualizar o insertar en la tabla principal
        cursor.execute('''
            REPLACE INTO datos (nodo, ipv6_global, temperatura, humedad, timestamp)
            VALUES (?, ?, ?, ?, ?)
        ''', (nodo, ipv6_global, temperatura, humedad, datetime.now()))

        # Insertar en la tabla historial
        cursor.execute('''
            INSERT INTO historial (nodo, temperatura, humedad, timestamp)
            VALUES (?, ?, ?, ?)
        ''', (nodo, temperatura, humedad, datetime.now()))

        conn.commit()
        conn.close()
    except sqlite3.Error as e:
        print(f"Error al actualizar la base de datos: {e}")


@app.route("/")
def index():
    """Ruta principal para renderizar la tabla con datos y gráficos."""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Obtener datos principales
        cursor.execute("SELECT nodo, ipv6_global, temperatura, humedad, timestamp FROM datos")
        rows = cursor.fetchall()

        # Obtener datos históricos para cada nodo
        historial = {}
        for row in rows:
            nodo = row[0]
            cursor.execute(
                "SELECT temperatura, humedad, timestamp FROM historial WHERE nodo = ? ORDER BY timestamp ASC",
                (nodo,)
            )
            historial[nodo] = cursor.fetchall()

        conn.close()

        # Renderizar HTML con datos
        return render_template("index.html", rows=rows, historial=historial)
    except sqlite3.Error as e:
        return f"Error al obtener datos de la base de datos: {e}"


def start_udp_server():
    """Inicia el servidor UDP para recibir datos."""
    init_db()
    sock = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
    sock.bind(("::", 8888))
    print("Servidor UDP escuchando en [::]:8888")
    while True:
        data, addr = sock.recvfrom(1024)
        try:
            payload = data.decode("utf-8").strip()
            temp_str, hum_str = payload.split(",")
            temperatura = int(temp_str) / 10.0
            humedad = int(hum_str) / 10.0
            nodo = addr[0]
            update_db(nodo, addr[0], temperatura, humedad)
        except Exception as e:
            print(f"Error al procesar datos: {e}")


if __name__ == "__main__":
    init_db()

    # Mostrar direcciones accesibles
    hostname = socket.gethostname()
    local_ip = socket.gethostbyname(hostname)
    print(f"Servidor HTTP disponible localmente en: http://{local_ip}:5000")
    print("Servidor HTTP disponible en todas las interfaces: http://127.0.0.1:5000")

    # Iniciar servidor UDP
    udp_thread = threading.Thread(target=start_udp_server, daemon=True)
    udp_thread.start()

    # Iniciar servidor HTTP
    app.run(host="0.0.0.0", port=5000, debug=True)