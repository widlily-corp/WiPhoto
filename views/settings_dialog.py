# views/settings_dialog.py

import multiprocessing
import shutil
import os
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QTabWidget, QWidget, QFormLayout,
                             QLabel, QSpinBox, QComboBox, QDialogButtonBox, QCheckBox,
                             QPushButton, QMessageBox, QLineEdit, QGroupBox, QSlider,
                             QHBoxLayout, QTableWidget, QTableWidgetItem, QAbstractItemView,
                             QHeaderView)
from PyQt6.QtCore import Qt
from core.settings_manager import settings, KEY_WORKER_COUNT, KEY_RAW_QUALITY, \
    KEY_CALC_SHARPNESS, KEY_HAMMING_THRESHOLD, KEY_THUMBNAIL_CACHE_PATH


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Настройки")
        self.setMinimumSize(600, 500)
        self.setObjectName("SettingsDialog")

        main_layout = QVBoxLayout(self)
        tab_widget = QTabWidget()
        main_layout.addWidget(tab_widget)

        tab_widget.addTab(self._create_general_tab(), "Общие")
        tab_widget.addTab(self._create_performance_tab(), "Производительность")
        tab_widget.addTab(self._create_workflow_tab(), "Рабочий процесс")
        tab_widget.addTab(self._create_export_tab(), "Экспорт")
        tab_widget.addTab(self._create_cache_tab(), "Кэш")
        tab_widget.addTab(self._create_shortcuts_tab(), "Горячие клавиши")

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        main_layout.addWidget(button_box)

        self._load_settings()

    def _create_general_tab(self):
        widget = QWidget()
        layout = QFormLayout(widget)

        self.hamming_threshold_spinbox = QSpinBox()
        self.hamming_threshold_spinbox.setRange(1, 20)
        self.hamming_threshold_spinbox.setToolTip(
            "Чем ниже значение, тем более похожими должны быть изображения,\n"
            "чтобы попасть в одну группу дубликатов."
        )
        layout.addRow("Порог схожести:", self.hamming_threshold_spinbox)

        self.default_view_combo = QComboBox()
        self.default_view_combo.addItems(["Галерея", "Таймлайн", "Карта"])
        layout.addRow("Вид по умолчанию:", self.default_view_combo)

        self.sidebar_left_check = QCheckBox("Показывать левую панель")
        self.sidebar_left_check.setChecked(True)
        layout.addRow(self.sidebar_left_check)

        self.sidebar_right_check = QCheckBox("Показывать правую панель")
        self.sidebar_right_check.setChecked(True)
        layout.addRow(self.sidebar_right_check)

        # Info section
        layout.addRow("", QLabel(""))
        info_group = QGroupBox("О программе")
        info_layout = QVBoxLayout(info_group)
        info_layout.addWidget(QLabel("WiPhoto v2.1.0"))
        info_layout.addWidget(QLabel("Профессиональный фотоменеджер"))
        info_layout.addWidget(QLabel("\u00a9 2026 Widlily Corporation"))
        layout.addRow(info_group)

        return widget

    def _create_performance_tab(self):
        widget = QWidget()
        layout = QFormLayout(widget)

        self.worker_count_spinbox = QSpinBox()
        self.worker_count_spinbox.setRange(1, multiprocessing.cpu_count())
        layout.addRow("Потоков для анализа:", self.worker_count_spinbox)

        self.raw_quality_combo = QComboBox()
        self.raw_quality_combo.addItems(["Половинное (быстро)", "Полное (качественно)"])
        layout.addRow("Качество обработки RAW:", self.raw_quality_combo)

        self.calc_sharpness_checkbox = QCheckBox("Вычислять резкость (медленнее)")
        self.calc_sharpness_checkbox.setToolTip(
            "Отключение этой опции значительно ускорит сканирование,\n"
            "но функция 'Оставить лучшее' будет работать менее точно."
        )
        layout.addRow(self.calc_sharpness_checkbox)

        self.thumbnail_size_spin = QSpinBox()
        self.thumbnail_size_spin.setRange(100, 600)
        self.thumbnail_size_spin.setValue(300)
        self.thumbnail_size_spin.setSuffix(" px")
        layout.addRow("Размер миниатюр кэша:", self.thumbnail_size_spin)

        self.pixmap_cache_spin = QSpinBox()
        self.pixmap_cache_spin.setRange(100, 2000)
        self.pixmap_cache_spin.setValue(500)
        layout.addRow("Размер кэша отрисовки:", self.pixmap_cache_spin)

        return widget

    def _create_workflow_tab(self):
        widget = QWidget()
        layout = QFormLayout(widget)

        # Flag workflow
        flag_group = QGroupBox("Флаги (Pick/Reject)")
        flag_layout = QFormLayout(flag_group)

        self.auto_advance_check = QCheckBox("Авто-переход после флага")
        self.auto_advance_check.setChecked(True)
        self.auto_advance_check.setToolTip("Автоматически переходить к следующему фото после P/X/U")
        flag_layout.addRow(self.auto_advance_check)

        self.reject_opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.reject_opacity_slider.setRange(30, 200)
        self.reject_opacity_slider.setValue(140)
        flag_layout.addRow("Прозрачность отклонённых:", self.reject_opacity_slider)

        layout.addRow(flag_group)

        # Rating workflow
        rating_group = QGroupBox("Рейтинг")
        rating_layout = QFormLayout(rating_group)

        self.rating_advance_check = QCheckBox("Авто-переход после рейтинга")
        self.rating_advance_check.setChecked(False)
        rating_layout.addRow(self.rating_advance_check)

        layout.addRow(rating_group)

        # Slideshow
        slide_group = QGroupBox("Слайдшоу")
        slide_layout = QFormLayout(slide_group)

        self.slideshow_interval_spin = QSpinBox()
        self.slideshow_interval_spin.setRange(1, 60)
        self.slideshow_interval_spin.setValue(4)
        self.slideshow_interval_spin.setSuffix(" сек")
        slide_layout.addRow("Интервал:", self.slideshow_interval_spin)

        layout.addRow(slide_group)

        return widget

    def _create_export_tab(self):
        widget = QWidget()
        layout = QFormLayout(widget)

        self.default_export_format = QComboBox()
        self.default_export_format.addItems(["JPEG", "PNG", "WebP"])
        layout.addRow("Формат по умолчанию:", self.default_export_format)

        self.default_quality_spin = QSpinBox()
        self.default_quality_spin.setRange(10, 100)
        self.default_quality_spin.setValue(92)
        self.default_quality_spin.setSuffix("%")
        layout.addRow("Качество по умолчанию:", self.default_quality_spin)

        self.default_watermark = QLineEdit()
        self.default_watermark.setPlaceholderText("\u00a9 WiPhoto 2026")
        layout.addRow("Водяной знак:", self.default_watermark)

        self.export_subfolder_check = QCheckBox("Создавать подпапку 'export'")
        self.export_subfolder_check.setChecked(True)
        layout.addRow(self.export_subfolder_check)

        return widget

    def _create_cache_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)

        cache_path = settings.get_thumbnail_cache_path()
        layout.addWidget(QLabel(f"Расположение кэша миниатюр:\n{cache_path}"))

        # Cache size info
        try:
            total_size = 0
            file_count = 0
            if os.path.isdir(cache_path):
                for dirpath, _, filenames in os.walk(cache_path):
                    for f in filenames:
                        fp = os.path.join(dirpath, f)
                        total_size += os.path.getsize(fp)
                        file_count += 1
            size_mb = total_size / (1024 * 1024)
            layout.addWidget(QLabel(f"Файлов в кэше: {file_count} ({size_mb:.1f} МБ)"))
        except Exception:
            pass

        # Trash info
        trash_path = os.path.join(os.path.expanduser("~"), ".wiphoto", "trash")
        try:
            trash_count = len(os.listdir(trash_path)) if os.path.isdir(trash_path) else 0
            layout.addWidget(QLabel(f"\nКорзина: {trash_count} файлов"))
        except Exception:
            pass

        btn_row = QHBoxLayout()

        clear_cache_button = QPushButton("Очистить кэш миниатюр")
        clear_cache_button.clicked.connect(self._clear_cache)
        btn_row.addWidget(clear_cache_button)

        clear_trash_button = QPushButton("Очистить корзину")
        clear_trash_button.clicked.connect(self._clear_trash)
        btn_row.addWidget(clear_trash_button)

        layout.addLayout(btn_row)
        layout.addStretch()

        return widget

    def _create_shortcuts_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)

        layout.addWidget(QLabel("Горячие клавиши WiPhoto:"))

        shortcuts = QTableWidget()
        shortcuts.setColumnCount(2)
        shortcuts.setHorizontalHeaderLabels(["Действие", "Клавиша"])
        shortcuts.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        shortcuts.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        shortcuts.verticalHeader().setVisible(False)

        keys = [
            ("Рейтинг 0-5", "0-5"),
            ("Цветная метка", "6-9"),
            ("Выбрать (Pick)", "P"),
            ("Отклонить (Reject)", "X"),
            ("Снять флаг", "U"),
            ("Удалить", "Delete"),
            ("Копировать", "Ctrl+C"),
            ("Переместить", "Ctrl+X"),
            ("Сравнить", "Ctrl+D"),
            ("Выбрать все", "Ctrl+A"),
            ("Снять выделение", "Ctrl+Shift+A"),
            ("Быстрый просмотр", "Space"),
            ("Полный экран", "F11"),
            ("Переименование", "F2"),
            ("Экспорт", "Ctrl+Shift+E"),
            ("Слайдшоу", "F8"),
            ("Обновить", "F5"),
            ("Следующее", "\u2192"),
            ("Предыдущее", "\u2190"),
            ("Настройки", "Ctrl+,"),
            ("Выход", "Ctrl+Q"),
            ("Увеличить миниатюры", "Ctrl+\u2191"),
            ("Уменьшить миниатюры", "Ctrl+\u2193"),
        ]

        shortcuts.setRowCount(len(keys))
        for i, (action, key) in enumerate(keys):
            shortcuts.setItem(i, 0, QTableWidgetItem(action))
            shortcuts.setItem(i, 1, QTableWidgetItem(key))

        layout.addWidget(shortcuts)
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

    def _clear_cache(self):
        cache_path = settings.get_thumbnail_cache_path()
        reply = QMessageBox.question(self, "Подтверждение",
                                     f"Удалить все файлы из кэша?\n{cache_path}",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            try:
                shutil.rmtree(cache_path)
                settings.settings.setValue(KEY_THUMBNAIL_CACHE_PATH, cache_path)
                QMessageBox.information(self, "Успех", "Кэш очищен.")
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось очистить кэш: {e}")

    def _clear_trash(self):
        trash_path = os.path.join(os.path.expanduser("~"), ".wiphoto", "trash")
        if not os.path.isdir(trash_path):
            QMessageBox.information(self, "Корзина", "Корзина пуста.")
            return
        reply = QMessageBox.question(self, "Подтверждение",
                                     "Удалить все файлы из корзины?\nЭто действие необратимо!",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            try:
                shutil.rmtree(trash_path)
                os.makedirs(trash_path, exist_ok=True)
                QMessageBox.information(self, "Успех", "Корзина очищена.")
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Ошибка: {e}")

    def accept(self):
        self._save_settings()
        super().accept()
