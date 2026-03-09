# views/batch_rename_dialog.py

import os
from datetime import datetime
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
                             QComboBox, QSpinBox, QPushButton, QTableWidget,
                             QTableWidgetItem, QAbstractItemView, QHeaderView,
                             QGroupBox, QFormLayout, QDialogButtonBox, QCheckBox)
from PyQt6.QtCore import Qt
from models.image_model import ImageInfo


class BatchRenameDialog(QDialog):
    """Dialog for batch renaming files with pattern support"""

    def __init__(self, image_infos: list, parent=None):
        super().__init__(parent)
        self.image_infos = image_infos
        self.rename_map = {}  # old_path -> new_path
        self.setWindowTitle("Пакетное переименование")
        self.setMinimumSize(700, 500)
        self._init_ui()
        self._update_preview()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # Pattern group
        pattern_group = QGroupBox("Шаблон имени")
        pattern_layout = QFormLayout(pattern_group)

        self.prefix_edit = QLineEdit()
        self.prefix_edit.setPlaceholderText("Например: Photo_")
        self.prefix_edit.textChanged.connect(self._update_preview)
        pattern_layout.addRow("Префикс:", self.prefix_edit)

        self.suffix_edit = QLineEdit()
        self.suffix_edit.setPlaceholderText("Например: _edited")
        self.suffix_edit.textChanged.connect(self._update_preview)
        pattern_layout.addRow("Суффикс:", self.suffix_edit)

        # Counter settings
        counter_row = QHBoxLayout()
        self.counter_start = QSpinBox()
        self.counter_start.setRange(0, 99999)
        self.counter_start.setValue(1)
        self.counter_start.valueChanged.connect(self._update_preview)
        counter_row.addWidget(QLabel("Начало:"))
        counter_row.addWidget(self.counter_start)

        self.counter_digits = QSpinBox()
        self.counter_digits.setRange(1, 6)
        self.counter_digits.setValue(3)
        self.counter_digits.valueChanged.connect(self._update_preview)
        counter_row.addWidget(QLabel("Цифр:"))
        counter_row.addWidget(self.counter_digits)

        self.counter_step = QSpinBox()
        self.counter_step.setRange(1, 100)
        self.counter_step.setValue(1)
        self.counter_step.valueChanged.connect(self._update_preview)
        counter_row.addWidget(QLabel("Шаг:"))
        counter_row.addWidget(self.counter_step)
        pattern_layout.addRow("Счетчик:", counter_row)

        # Pattern type
        self.pattern_combo = QComboBox()
        self.pattern_combo.addItems([
            "Префикс + Счетчик",
            "Префикс + Дата + Счетчик",
            "Дата + Счетчик",
            "Камера + Счетчик",
            "Оригинал + Суффикс",
        ])
        self.pattern_combo.currentIndexChanged.connect(self._update_preview)
        pattern_layout.addRow("Формат:", self.pattern_combo)

        # Lowercase extension
        self.lowercase_ext = QCheckBox("Расширение в нижнем регистре")
        self.lowercase_ext.setChecked(True)
        self.lowercase_ext.stateChanged.connect(self._update_preview)
        pattern_layout.addRow("", self.lowercase_ext)

        layout.addWidget(pattern_group)

        # Preview table
        preview_label = QLabel("Предпросмотр:")
        preview_label.setStyleSheet("font-weight: bold; margin-top: 8px;")
        layout.addWidget(preview_label)

        self.preview_table = QTableWidget()
        self.preview_table.setColumnCount(2)
        self.preview_table.setHorizontalHeaderLabels(["Текущее имя", "Новое имя"])
        self.preview_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.preview_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.preview_table.verticalHeader().setVisible(False)
        layout.addWidget(self.preview_table)

        # Buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def _generate_new_name(self, info: ImageInfo, index: int) -> str:
        """Generate new filename based on pattern"""
        original = os.path.basename(info.path)
        name, ext = os.path.splitext(original)

        if self.lowercase_ext.isChecked():
            ext = ext.lower()

        prefix = self.prefix_edit.text()
        suffix = self.suffix_edit.text()
        counter = self.counter_start.value() + index * self.counter_step.value()
        digits = self.counter_digits.value()
        counter_str = str(counter).zfill(digits)

        # Date from EXIF or file modification time
        date_str = ""
        if info.date_taken:
            try:
                dt = datetime.strptime(info.date_taken, "%Y:%m:%d %H:%M:%S")
                date_str = dt.strftime("%Y%m%d")
            except ValueError:
                pass
        if not date_str:
            try:
                mtime = os.path.getmtime(info.path)
                date_str = datetime.fromtimestamp(mtime).strftime("%Y%m%d")
            except Exception:
                date_str = "00000000"

        camera = info.camera_model.replace(" ", "_") if info.camera_model else "Unknown"

        pattern_idx = self.pattern_combo.currentIndex()

        if pattern_idx == 0:  # Prefix + Counter
            new_name = f"{prefix}{counter_str}{ext}"
        elif pattern_idx == 1:  # Prefix + Date + Counter
            new_name = f"{prefix}{date_str}_{counter_str}{ext}"
        elif pattern_idx == 2:  # Date + Counter
            new_name = f"{date_str}_{counter_str}{ext}"
        elif pattern_idx == 3:  # Camera + Counter
            new_name = f"{camera}_{counter_str}{ext}"
        elif pattern_idx == 4:  # Original + Suffix
            new_name = f"{name}{suffix}{ext}"
        else:
            new_name = f"{prefix}{counter_str}{ext}"

        return new_name

    def _update_preview(self):
        """Update preview table with generated names"""
        self.preview_table.setRowCount(len(self.image_infos))
        self.rename_map.clear()

        for i, info in enumerate(self.image_infos):
            old_name = os.path.basename(info.path)
            new_name = self._generate_new_name(info, i)

            old_item = QTableWidgetItem(old_name)
            new_item = QTableWidgetItem(new_name)

            # Highlight conflicts
            new_path = os.path.join(os.path.dirname(info.path), new_name)
            if new_path != info.path and os.path.exists(new_path):
                new_item.setForeground(Qt.GlobalColor.red)
            elif new_name != old_name:
                new_item.setForeground(Qt.GlobalColor.green)

            self.preview_table.setItem(i, 0, old_item)
            self.preview_table.setItem(i, 1, new_item)
            self.rename_map[info.path] = new_path

    def get_rename_map(self) -> dict:
        """Returns {old_path: new_path} mapping"""
        return dict(self.rename_map)
