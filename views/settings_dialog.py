# views/settings_dialog.py

import multiprocessing
import shutil
from PyQt6.QtWidgets import QLineEdit
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QTabWidget, QWidget, QFormLayout,
                             QLabel, QSpinBox, QComboBox, QDialogButtonBox, QCheckBox,
                             QPushButton, QMessageBox)
from PyQt6.QtCore import Qt
from core.settings_manager import settings, KEY_WORKER_COUNT, KEY_RAW_QUALITY, \
    KEY_CALC_SHARPNESS, KEY_HAMMING_THRESHOLD, KEY_THUMBNAIL_CACHE_PATH


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Настройки")
        self.setMinimumWidth(500)
        self.setObjectName("SettingsDialog")
        # --- Основная структура ---
        main_layout = QVBoxLayout(self)
        tab_widget = QTabWidget()
        main_layout.addWidget(tab_widget)

        # --- Создание вкладок ---
        performance_tab = self._create_performance_tab()
        general_tab = self._create_general_tab()
        cache_tab = self._create_cache_tab()
        #api_tab = self._create_api_tab()

        tab_widget.addTab(performance_tab, "Производительность")
        tab_widget.addTab(general_tab, "Общие")
        tab_widget.addTab(cache_tab, "Кэш")
        #tab_widget.addTab(api_tab, "ИИ Сервисы")

        # --- Кнопки OK/Cancel ---
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        main_layout.addWidget(button_box)

        self._load_settings()

    def _create_api_tab(self):
        """Создает вкладку настроек API"""
        widget = QWidget()
        layout = QFormLayout(widget)

        self.clipdrop_key_edit = QLineEdit()
        self.clipdrop_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.clipdrop_key_edit.setPlaceholderText("sk-...")

        link_label = QLabel('<a href="https://clipdrop.co/apis">Получить API ключ ClipDrop</a>')
        link_label.setOpenExternalLinks(True)

        layout.addRow("ClipDrop API Key:", self.clipdrop_key_edit)
        layout.addRow("", link_label)

        return widget

    def _create_performance_tab(self):
        widget = QWidget()
        layout = QFormLayout(widget)

        self.worker_count_spinbox = QSpinBox()
        self.worker_count_spinbox.setRange(1, multiprocessing.cpu_count())
        layout.addRow("Количество потоков для анализа:", self.worker_count_spinbox)

        self.raw_quality_combo = QComboBox()
        self.raw_quality_combo.addItems(["Половинное (быстро)", "Полное (качественно)"])
        layout.addRow("Качество обработки RAW:", self.raw_quality_combo)

        self.calc_sharpness_checkbox = QCheckBox("Вычислять резкость (медленнее)")
        self.calc_sharpness_checkbox.setToolTip(
            "Отключение этой опции значительно ускорит сканирование, \n"
            "но функция 'Оставить лучшее' будет работать менее точно."
        )
        layout.addRow(self.calc_sharpness_checkbox)

        return widget

    def _create_general_tab(self):
        widget = QWidget()
        layout = QFormLayout(widget)

        self.hamming_threshold_spinbox = QSpinBox()
        self.hamming_threshold_spinbox.setRange(1, 20)
        self.hamming_threshold_spinbox.setToolTip(
            "Чем ниже значение, тем более похожими должны быть изображения, \n"
            "чтобы попасть в одну группу дубликатов."
        )
        layout.addRow("Порог схожести изображений:", self.hamming_threshold_spinbox)
        return widget

    def _create_cache_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)

        cache_path = settings.get_thumbnail_cache_path()
        layout.addWidget(QLabel(f"Расположение кэша миниатюр:\n{cache_path}"))

        clear_cache_button = QPushButton("Очистить кэш миниатюр")
        clear_cache_button.clicked.connect(self._clear_cache)
        layout.addWidget(clear_cache_button)
        layout.addStretch()

        return widget

    def _load_settings(self):
        self.worker_count_spinbox.setValue(settings.get_worker_count())
        raw_quality_map = {"half": 0, "full": 1}
        self.raw_quality_combo.setCurrentIndex(raw_quality_map.get(settings.get_raw_quality(), 0))
        self.calc_sharpness_checkbox.setChecked(settings.get_calculate_sharpness())
        self.hamming_threshold_spinbox.setValue(settings.get_hamming_threshold())

    def _save_settings(self):
        settings.set_worker_count(self.worker_count_spinbox.value())
        raw_quality_map = {0: "half", 1: "full"}
        settings.set_raw_quality(raw_quality_map[self.raw_quality_combo.currentIndex()])
        settings.set_calculate_sharpness(self.calc_sharpness_checkbox.isChecked())
        settings.set_hamming_threshold(self.hamming_threshold_spinbox.value())
        if hasattr(self, 'clipdrop_key_edit'):
            key = self.clipdrop_key_edit.text()
            # На всякий случай принтуем в консоль для проверки (потом можно убрать)
            print(f"Сохраняем API ключ: '{key}'")
            settings.set_clipdrop_key(key)
    def _clear_cache(self):
        cache_path = settings.get_thumbnail_cache_path()
        reply = QMessageBox.question(self, "Подтверждение",
                                     f"Вы уверены, что хотите удалить все файлы из кэша?\n{cache_path}\n"
                                     "Они будут созданы заново при следующем сканировании.",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            try:
                shutil.rmtree(cache_path)
                # Важно пересоздать папку после удаления
                settings.settings.setValue(KEY_THUMBNAIL_CACHE_PATH, cache_path)
                QMessageBox.information(self, "Успех", "Кэш успешно очищен.")
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось очистить кэш: {e}")

    def accept(self):
        """Переопределенный метод, вызываемый при нажатии OK."""
        self._save_settings()
        super().accept()