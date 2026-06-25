# views/welcome_window.py

import logging
import time
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QPushButton,
                             QCheckBox, QProgressBar)
from PyQt6.QtCore import Qt, QTimer
from utils import resource_path


class WelcomeWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Добро пожаловать в WiPhoto")

        try:
            self.setWindowIcon(QIcon(resource_path("assets/icon.ico")))
        except Exception as e:
            logging.error(f"Не удалось загрузить иконку окна: {e}")

        self.setGeometry(300, 300, 550, 320)
        self.setObjectName("WelcomeWindow")

        self._start_time = None
        self._timer = QTimer()
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._update_time)

        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(15)
        layout.setContentsMargins(40, 30, 40, 30)

        title_label = QLabel("WiPhoto - Ваш умный менеджер фотографий")
        title_label.setObjectName("WelcomeTitle")
        title_label.setStyleSheet("font-size: 20px; font-weight: bold;")

        info_label = QLabel("Выберите папку с вашими фотографиями")
        info_label.setWordWrap(True)
        info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info_label.setFixedSize(200,60)

        self.recursive_checkbox = QCheckBox("Сканировать вложенные папки")
        self.recursive_checkbox.setChecked(True)

        self.select_folder_button = QPushButton("Выбрать папку...")
        self.select_folder_button.setFixedSize(200, 40)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)

        # File info label: "filename.jpg — 15 из 243"
        self.file_info_label = QLabel("")
        self.file_info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.file_info_label.setStyleSheet("color: #aaa; font-size: 12px;")
        self.file_info_label.setVisible(False)
        self.file_info_label.setWordWrap(True)

        # Time info: elapsed + ETA
        self.time_info_label = QLabel("")
        self.time_info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.time_info_label.setStyleSheet("color: #888; font-size: 11px;")
        self.time_info_label.setVisible(False)

        layout.addWidget(title_label, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(info_label, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.recursive_checkbox, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.select_folder_button, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.file_info_label)
        layout.addWidget(self.time_info_label)

        self.setLayout(layout)

        self._current = 0
        self._total = 0
        self._last_file = ""

    def start_progress(self):
        """Call when scanning starts"""
        self._start_time = time.time()
        self.file_info_label.setVisible(True)
        self.time_info_label.setVisible(True)
        self._timer.start()

    def update_scan_progress(self, current: int, total: int, file_path: str = ""):
        """Update progress with file info"""
        self._current = current
        self._total = total
        if file_path:
            self._last_file = file_path

        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)

        # File info
        import os
        filename = os.path.basename(self._last_file) if self._last_file else ""
        self.file_info_label.setText(f"{filename}  —  {current} из {total}")

        self._update_time()

    def _update_time(self):
        if self._start_time is None or self._total == 0:
            return

        elapsed = time.time() - self._start_time
        elapsed_str = self._format_time(elapsed)

        if self._current > 0:
            rate = elapsed / self._current
            remaining = rate * (self._total - self._current)
            eta_str = self._format_time(remaining)
            self.time_info_label.setText(
                f"Прошло: {elapsed_str}  |  Осталось: ~{eta_str}"
            )
        else:
            self.time_info_label.setText(f"Прошло: {elapsed_str}")

    @staticmethod
    def _format_time(seconds: float) -> str:
        seconds = int(seconds)
        if seconds < 60:
            return f"{seconds} сек"
        m, s = divmod(seconds, 60)
        if m < 60:
            return f"{m:02d}:{s:02d}"
        h, m = divmod(m, 60)
        return f"{h}:{m:02d}:{s:02d}"

    def stop_progress(self):
        self._timer.stop()

    def closeEvent(self, event):
        self._timer.stop()
        event.accept()
