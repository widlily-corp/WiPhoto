# views/contact_sheet_dialog.py

import os
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, QSpinBox,
                             QLineEdit, QPushButton, QFileDialog, QLabel,
                             QDialogButtonBox, QGroupBox, QComboBox, QCheckBox)
from PyQt6.QtCore import Qt
from PIL import Image, ImageDraw, ImageFont

from models.image_model import ImageInfo


class ContactSheetDialog(QDialog):
    """Generate a contact sheet (grid of thumbnails) as PNG/JPEG"""

    def __init__(self, image_infos: list, parent=None):
        super().__init__(parent)
        self.image_infos = image_infos
        self.setWindowTitle(f"Контактный лист ({len(image_infos)} фото)")
        self.setMinimumWidth(400)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # Grid settings
        grid_group = QGroupBox("Сетка")
        grid_layout = QFormLayout(grid_group)

        self.columns_spin = QSpinBox()
        self.columns_spin.setRange(2, 12)
        self.columns_spin.setValue(4)
        grid_layout.addRow("Столбцов:", self.columns_spin)

        self.cell_size_spin = QSpinBox()
        self.cell_size_spin.setRange(100, 800)
        self.cell_size_spin.setValue(300)
        self.cell_size_spin.setSuffix(" px")
        grid_layout.addRow("Размер ячейки:", self.cell_size_spin)

        self.spacing_spin = QSpinBox()
        self.spacing_spin.setRange(2, 30)
        self.spacing_spin.setValue(10)
        self.spacing_spin.setSuffix(" px")
        grid_layout.addRow("Отступ:", self.spacing_spin)

        layout.addWidget(grid_group)

        # Info settings
        info_group = QGroupBox("Информация")
        info_layout = QFormLayout(info_group)

        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("Заголовок листа (необязательно)")
        info_layout.addRow("Заголовок:", self.title_edit)

        self.show_filename = QCheckBox("Имя файла")
        self.show_filename.setChecked(True)
        info_layout.addRow("Показывать:", self.show_filename)

        self.show_exif = QCheckBox("Разрешение и размер")
        self.show_exif.setChecked(True)
        info_layout.addRow("", self.show_exif)

        layout.addWidget(info_group)

        # Output
        output_group = QGroupBox("Вывод")
        output_layout = QFormLayout(output_group)

        self.format_combo = QComboBox()
        self.format_combo.addItems(["PNG", "JPEG"])
        output_layout.addRow("Формат:", self.format_combo)

        self.bg_combo = QComboBox()
        self.bg_combo.addItems(["Чёрный", "Белый", "Тёмно-серый"])
        output_layout.addRow("Фон:", self.bg_combo)

        layout.addWidget(output_group)

        # Preview info
        self.info_label = QLabel("")
        self.info_label.setStyleSheet("color: #808080; font-size: 11px;")
        layout.addWidget(self.info_label)
        self._update_info()
        self.columns_spin.valueChanged.connect(self._update_info)
        self.cell_size_spin.valueChanged.connect(self._update_info)

        # Buttons
        button_box = QDialogButtonBox()
        save_btn = button_box.addButton("Сохранить...", QDialogButtonBox.ButtonRole.AcceptRole)
        button_box.addButton(QDialogButtonBox.StandardButton.Cancel)
        save_btn.clicked.connect(self._save)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def _update_info(self):
        cols = self.columns_spin.value()
        cell = self.cell_size_spin.value()
        n = len(self.image_infos)
        rows = (n + cols - 1) // cols
        w = cols * (cell + self.spacing_spin.value()) + self.spacing_spin.value()
        h = rows * (cell + 30 + self.spacing_spin.value()) + self.spacing_spin.value() + 60
        self.info_label.setText(f"Итого: {cols}x{rows} = {n} фото, ~{w}x{h} px")

    def _save(self):
        fmt = self.format_combo.currentText()
        ext = ".png" if fmt == "PNG" else ".jpg"
        path, _ = QFileDialog.getSaveFileName(
            self, "Сохранить контактный лист",
            f"contact_sheet{ext}",
            f"Images (*{ext})"
        )
        if not path:
            return

        self._generate(path)
        self.accept()

    def _generate(self, output_path: str):
        cols = self.columns_spin.value()
        cell = self.cell_size_spin.value()
        spacing = self.spacing_spin.value()
        n = len(self.image_infos)
        rows = (n + cols - 1) // cols

        text_h = 30 if (self.show_filename.isChecked() or self.show_exif.isChecked()) else 0
        title_h = 50 if self.title_edit.text().strip() else 0

        total_w = cols * (cell + spacing) + spacing
        total_h = rows * (cell + text_h + spacing) + spacing + title_h

        bg_map = {"Чёрный": (20, 20, 20), "Белый": (255, 255, 255), "Тёмно-серый": (40, 40, 40)}
        bg_color = bg_map.get(self.bg_combo.currentText(), (20, 20, 20))
        text_color = (200, 200, 200) if bg_color[0] < 128 else (40, 40, 40)

        sheet = Image.new('RGB', (total_w, total_h), bg_color)
        draw = ImageDraw.Draw(sheet)

        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 12)
            title_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 18)
        except Exception:
            font = ImageFont.load_default()
            title_font = font

        # Title
        if title_h > 0:
            title = self.title_edit.text().strip()
            bbox = draw.textbbox((0, 0), title, font=title_font)
            tw = bbox[2] - bbox[0]
            draw.text(((total_w - tw) // 2, 15), title, fill=text_color, font=title_font)

        # Thumbnails
        for idx, info in enumerate(self.image_infos):
            row = idx // cols
            col = idx % cols

            x = spacing + col * (cell + spacing)
            y = title_h + spacing + row * (cell + text_h + spacing)

            try:
                thumb_path = info.thumbnail_path or info.path
                img = Image.open(thumb_path)
                img.thumbnail((cell, cell), Image.LANCZOS)

                # Center in cell
                ox = x + (cell - img.width) // 2
                oy = y + (cell - img.height) // 2
                sheet.paste(img, (ox, oy))

                # Border
                draw.rectangle([x, y, x + cell - 1, y + cell - 1], outline=(80, 80, 80))

            except Exception:
                draw.rectangle([x, y, x + cell - 1, y + cell - 1], outline=(80, 80, 80))
                draw.text((x + 4, y + 4), "Error", fill=(200, 50, 50), font=font)

            # Text below
            if text_h > 0:
                text_y = y + cell + 2
                lines = []
                if self.show_filename.isChecked():
                    fname = os.path.basename(info.path)
                    if len(fname) > 25:
                        fname = fname[:22] + "..."
                    lines.append(fname)
                if self.show_exif.isChecked() and info.width > 0:
                    lines.append(f"{info.width}x{info.height}")

                for li, line in enumerate(lines):
                    draw.text((x + 2, text_y + li * 14), line, fill=text_color, font=font)

        # Save
        fmt = self.format_combo.currentText()
        if fmt == "JPEG":
            if sheet.mode == 'RGBA':
                sheet = sheet.convert('RGB')
            sheet.save(output_path, 'JPEG', quality=95)
        else:
            sheet.save(output_path, 'PNG')
