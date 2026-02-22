# views/welcome_window.py

from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QPushButton,
                             QCheckBox, QProgressBar)
from PyQt6.QtCore import Qt
from utils import resource_path


class WelcomeWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Добро пожаловать в WiPhoto")

        # Устанавливаем иконку с обработкой ошибок
        try:
            self.setWindowIcon(QIcon(resource_path("assets/icon.ico")))
        except Exception as e:
            print(f"Не удалось загрузить иконку окна: {e}")

        self.setGeometry(300,300, 500, 250)

        # Устанавливаем ObjectName для корректной работы со стилями
        self.setObjectName("WelcomeWindow")

        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(50)

        # --- Виджеты ---
        title_label = QLabel("WiPhoto - Ваш умный менеджер фотографий")
        title_label.setObjectName("WelcomeTitle")
        title_label.setStyleSheet("font-size: 20px; font-weight: bold;")

        info_label = QLabel(
            "Выберите папку с вашими фотографиями<br>для начала работы."
        )
        info_label.setWordWrap(True)
        info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)



        self.select_folder_button = QPushButton("Выбрать папку...")
        self.select_folder_button.setFixedSize(200, 40)

        self.recursive_checkbox = QCheckBox("Сканировать вложенные папки")
        self.recursive_checkbox.setChecked(True)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)

        # --- Добавление в компоновку ---
        layout.addWidget(title_label, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(info_label, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.recursive_checkbox, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.select_folder_button, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.progress_bar)

        self.setLayout(layout)

    def closeEvent(self, event):
        """Обработка закрытия окна"""
        try:
            event.accept()
        except Exception as e:
            event.accept()