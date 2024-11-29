import serial
import sys
import sqlite3
import os
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QPushButton, QHBoxLayout, QComboBox, QTabWidget, QTableWidget, QTableWidgetItem
import threading
from datetime import datetime

humidity_data = []
temperature_data = []
ec_data = []
timestamps = []

# ЧТЕНИЕ КОМ-ПОРТА И ПАРСИНГ
def read_com_port():
    ser = serial.Serial('/dev/ttyUSB0', baudrate=115200, timeout=1)
    try:
        while True:
            if ser.in_waiting > 0:
                pre_data = ser.readline().decode('utf-8').strip()
                data = parse_data_from(pre_data)
                add_inf_db(data)
                get_last_15_from_db(current_dev_id)  # Обновляем для текущего dev_id
    except KeyboardInterrupt:
        print("Программа завершена")
    finally:
        ser.close()


def parse_data_from(data):
    pre_parts = data.split(': ')
    if len(pre_parts) > 1:
        parts = pre_parts[1].split(' ')
        if len(parts) >= 4:
            return parts
    return []


# БАЗА ДАННЫХ
def create_data_base():
    connection = sqlite3.connect("sensor_data")
    cursor = connection.cursor()
    cursor.execute(''' 
        CREATE TABLE IF NOT EXISTS sensor_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dev_id INTEGER,
            humidity REAL,
            temperature REAL,
            ec REAL,
            timestamp TEXT
        )
    ''')
    connection.commit()
    connection.close()


def add_inf_db(data):
    if len(data) < 4:
        print("Недостаточно данных для записи в базу:", data)
        return

    connection = sqlite3.connect("sensor_data")
    cursor = connection.cursor()
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute(
            "INSERT INTO sensor_data(dev_id, humidity, temperature, ec, timestamp) VALUES (?, ?, ?, ?, ?)",
            (int(data[0]), float(data[1]), float(data[2]), float(data[3]), timestamp)
        )
        connection.commit()
    except ValueError as e:
        print("Ошибка в данных:", e, data)
    finally:
        connection.close()


def get_last_15_from_db(dev_id):
    global humidity_data, temperature_data, ec_data, timestamps
    connection = sqlite3.connect("sensor_data")
    cursor = connection.cursor()
    cursor.execute("""
        SELECT humidity, temperature, ec, timestamp
        FROM sensor_data
        WHERE dev_id = ?
        ORDER BY id DESC
        LIMIT 15
    """, (dev_id,))
    rows = cursor.fetchall()
    connection.close()
    humidity_data.clear()
    temperature_data.clear()
    ec_data.clear()
    timestamps.clear()
    for row in reversed(rows):
        humidity_data.append(row[0])
        temperature_data.append(row[1])
        ec_data.append(row[2])
        timestamps.append(row[3])


def get_all_device_ids():
    connection = sqlite3.connect("sensor_data")
    cursor = connection.cursor()
    cursor.execute("SELECT DISTINCT dev_id FROM sensor_data")
    device_ids = [row[0] for row in cursor.fetchall()]
    connection.close()
    return device_ids


def get_all_data_from_db():
    connection = sqlite3.connect("sensor_data")
    cursor = connection.cursor()

    # Получаем имена всех столбцов
    cursor.execute("PRAGMA table_info(sensor_data)")
    columns = cursor.fetchall()

    # Столбцы, которые нам не нужны (ID — первый столбец)
    column_names = [column[1] for column in columns[1:]]  # Пропускаем первый столбец (ID)

    # Формируем запрос для всех столбцов, кроме ID
    query = f"SELECT {', '.join(column_names)} FROM sensor_data"
    cursor.execute(query)

    rows = cursor.fetchall()
    connection.close()
    return rows


# Глобальная переменная для текущего device_id
current_dev_id = 18


def animate(i, axes):
    get_last_15_from_db(current_dev_id)
    if len(humidity_data) > 0:
        for ax in axes.flatten():
            ax.clear()
        axes[0, 0].plot(timestamps, humidity_data, label="Humidity", marker='o')  # Используем timestamps для оси X
        axes[0, 0].set_title("Humidity")
        axes[0, 0].set_ylabel("Humidity (%)")
        axes[0, 0].grid(True)
        axes[0, 0].legend()
        axes[0, 0].set_xticks(range(len(timestamps)))
        axes[0, 0].set_xticklabels(timestamps, rotation=45, fontsize = 4)

        axes[0, 1].plot(timestamps, temperature_data, label="Temperature", marker='x')  # Используем timestamps для оси X
        axes[0, 1].set_title("Temperature")
        axes[0, 1].set_ylabel("Temperature (°C)")
        axes[0, 1].grid(True)
        axes[0, 1].legend()
        axes[0, 1].set_xticks(range(len(timestamps)))
        axes[0, 1].set_xticklabels(timestamps, rotation=45, fontsize = 4)

        axes[1, 0].plot(timestamps, ec_data, label="EC", marker='s')  # Используем timestamps для оси X
        axes[1, 0].set_title("EC")
        axes[1, 0].set_ylabel("EC (µS/cm)")
        axes[1, 0].grid(True)
        axes[1, 0].legend()
        axes[1, 0].set_xticks(range(len(timestamps)))
        axes[1, 0].set_xticklabels(timestamps, rotation=45, fontsize = 4)

        axes[1, 1].axis('off')
        plt.tight_layout()

class MyApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("App")
        self.setGeometry(0, 0, 1900, 1000)

        # Создаем вкладки
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        # Вкладка с графиками
        self.graphs_tab = QWidget()
        self.setup_graphs_tab()
        self.tabs.addTab(self.graphs_tab, "Graphs")

        # Вкладка с таблицей
        self.database_tab = QWidget()
        self.setup_database_tab()
        self.tabs.addTab(self.database_tab, "Database")

        # Пустая вкладка
        self.tab_by_device = QWidget()
        self.setup_tab_by_device()
        self.tabs.addTab(self.tab_by_device, "Tabs by device")


    def setup_graphs_tab(self):
        layout = QVBoxLayout(self.graphs_tab)

        # Создаем графики
        self.figure, self.axes = plt.subplots(2, 2, figsize=(10, 6))
        self.canvas = FigureCanvas(self.figure)
        layout.addWidget(self.canvas)

        # Комбо-бокс для выбора dev_id
        device_ids = get_all_device_ids()
        self.device_combo = QComboBox()
        self.device_combo.addItems(map(str, device_ids))
        self.device_combo.currentIndexChanged.connect(self.update_graphs)
        layout.addWidget(self.device_combo)

        # Анимация
        self.ani = FuncAnimation(self.figure, animate, fargs=(self.axes,), interval=1000)

    def setup_database_tab(self):
        layout = QVBoxLayout(self.database_tab)
        self.table = QTableWidget()
        layout.addWidget(self.table)

        # Кнопка для очистки базы данных
        self.clear_button = QPushButton("Очистить базу данных")
        self.clear_button.clicked.connect(self.clear_database)
        layout.addWidget(self.clear_button)

        # Кнопка для обновления данных
        self.update_button = QPushButton("Обновить данные")
        self.update_button.clicked.connect(self.load_database)
        layout.addWidget(self.update_button)

        self.load_database()

    def load_database(self):

        data = get_all_data_from_db()

        self.table.clearContents()
        self.table.setRowCount(len(data))

        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Device ID", "Humidity", "Temperature", "EC", "Timestamp"])

        data = list(reversed(data))

        for row_idx, row_data in enumerate(data):
            for col_idx, col_data in enumerate(row_data):
                self.table.setItem(row_idx, col_idx, QTableWidgetItem(str(col_data)))

    def update_graphs(self):
        global current_dev_id
        current_dev_id = int(self.device_combo.currentText())
        get_last_15_from_db(current_dev_id)
        self.canvas.draw()

    def clear_database(self):
        """
        Очищает базу данных, сбрасывает ID и обновляет таблицы во всех вкладках.
        """
        connection = sqlite3.connect("sensor_data")
        cursor = connection.cursor()

        # Очищаем таблицу
        cursor.execute("DELETE FROM sensor_data")
        connection.commit()

        # Сбрасываем автоинкрементное значение для ID
        cursor.execute("DELETE FROM sqlite_sequence WHERE name='sensor_data';")
        connection.commit()

        connection.close()

        # Обновляем таблицы в обоих вкладках
        self.load_database()  # Обновление таблицы во вкладке Database
        self.update_table()  # Обновление таблицы во вкладке Tabs by device

    def setup_tab_by_device(self):
        layout = QVBoxLayout(self.tab_by_device)

        # Получаем список устройств
        device_ids = get_all_device_ids()

        # Создаём ComboBox для выбора устройства
        self.device_combo = QComboBox()
        self.device_combo.addItems(map(str, device_ids))
        self.device_combo.currentIndexChanged.connect(self.update_table)
        layout.addWidget(self.device_combo)

        # Создаём таблицу
        self.table2 = QTableWidget()
        self.table2.setRowCount(15)
        self.table2.setColumnCount(4)
        self.table2.setHorizontalHeaderLabels(["Humidity", "Temperature", "EC", "Timestamp"])
        self.table2.setColumnWidth(0, 100)  # Ширина столбца для "Humidity"
        self.table2.setColumnWidth(1, 100)  # Ширина столбца для "Temperature"
        self.table2.setColumnWidth(2, 100)  # Ширина столбца для "EC"
        self.table2.setColumnWidth(3, 200)  # Ширина столбца для "Timestamp"

        layout.addWidget(self.table2)

        # # Кнопка для очистки данных на вкладке "Tabs by device"
        # self.clear_button_device = QPushButton("Очистить данные для устройства")
        # self.clear_button_device.clicked.connect(self.clear_device_data)
        # layout.addWidget(self.clear_button_device)

        # Кнопка для обновления данных
        self.update_button_device = QPushButton("Обновить данные для устройства")
        self.update_button_device.clicked.connect(self.update_table)
        layout.addWidget(self.update_button_device)

        # Инициализируем таблицу данными первого устройства
        if device_ids:
            self.update_table()

    # def clear_device_data(self):
    #     """
    #     Очищает данные на вкладке "Tabs by device".
    #     """
    #     self.table2.clearContents()  # Очищаем таблицу
    #     print("Данные для устройства очищены!")

    def update_table(self):
        """
        Обновляет таблицу данными для выбранного устройства на вкладке Tabs by device.
        """
        current_dev_id = int(self.device_combo.currentText())  # Получаем выбранный dev_id
        get_last_15_from_db(current_dev_id)  # Получаем последние 15 данных для выбранного устройства

        # Очищаем таблицу перед обновлением
        self.table2.clearContents()

        # Заполняем таблицу новыми данными
        for row_idx in range(len(humidity_data)):  # Предполагается, что данные хранятся в глобальных переменных
            self.table2.setItem(row_idx, 0, QTableWidgetItem(str(humidity_data[row_idx])))
            self.table2.setItem(row_idx, 1, QTableWidgetItem(str(temperature_data[row_idx])))
            self.table2.setItem(row_idx, 2, QTableWidgetItem(str(ec_data[row_idx])))
            self.table2.setItem(row_idx, 3, QTableWidgetItem(str(timestamps[row_idx])))


    def clear_database(self):

        connection = sqlite3.connect("sensor_data")
        cursor = connection.cursor()
        cursor.execute("DELETE FROM sensor_data")  # Очищаем всю таблицу
        connection.commit()
        connection.close()

        # Очищаем таблицу на вкладке "Database"
        self.table.clearContents()

        # Обновляем таблицы в обоих вкладках
        self.load_database()  # Обновление таблицы во вкладке Database
        self.update_table()  # Обновление таблицы во вкладке Tabs by device
        print("База данных очищена!")


if __name__ == "__main__":
    create_data_base()
    app = QApplication(sys.argv)
    window = MyApp()
    window.show()

    # Запуск потока для чтения данных с COM-порта
    thread = threading.Thread(target=read_com_port, daemon=True)
    thread.start()

    sys.exit(app.exec_())
