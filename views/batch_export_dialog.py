# views/batch_export_dialog.py

import os
import logging
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
                             QComboBox, QSpinBox, QPushButton, QGroupBox, QFormLayout,
                             QDialogButtonBox, QCheckBox, QSlider, QFileDialog,
                             QProgressBar, QTextEdit)
from PyQt6.QtCore import Qt, QThread, QObject, pyqtSignal
from PIL import Image, ImageDraw, ImageFont


class ExportWorker(QObject):
    progress = pyqtSignal(int, int, str)  # current, total, filename
    finished = pyqtSignal(int, int)  # success_count, error_count
    error = pyqtSignal(str)

    def __init__(self, image_infos, settings):
        super().__init__()
        self.image_infos = image_infos
        self.settings = settings
        self.should_stop = False

    def run(self):
        s = self.settings
        success = 0
        errors = 0
        total = len(self.image_infos)

        for i, info in enumerate(self.image_infos):
            if self.should_stop:
                break

            filename = os.path.basename(info.path)
            self.progress.emit(i + 1, total, filename)

            try:
                img = Image.open(info.path)
                if img.mode not in ('RGB', 'RGBA'):
                    img = img.convert('RGB')

                # Resize
                if s['resize_mode'] != 'original':
                    w, h = img.size
                    if s['resize_mode'] == 'fit':
                        max_w, max_h = s['max_width'], s['max_height']
                        ratio = min(max_w / w, max_h / h)
                        if ratio < 1:
                            img = img.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)
                    elif s['resize_mode'] == 'long_edge':
                        long_edge = s['long_edge']
                        if max(w, h) > long_edge:
                            if w >= h:
                                ratio = long_edge / w
                            else:
                                ratio = long_edge / h
                            img = img.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)

                # Watermark
                if s.get('watermark_text'):
                    img = self._apply_watermark(img, s['watermark_text'], s.get('watermark_opacity', 128))

                # Output path
                name, _ = os.path.splitext(filename)
                ext_map = {'JPEG': '.jpg', 'PNG': '.png', 'WebP': '.webp'}
                new_ext = ext_map.get(s['format'], '.jpg')
                out_path = os.path.join(s['output_dir'], f"{name}{new_ext}")

                # Handle conflicts
                if os.path.exists(out_path):
                    counter = 1
                    while os.path.exists(out_path):
                        out_path = os.path.join(s['output_dir'], f"{name}_{counter}{new_ext}")
                        counter += 1

                # Save
                save_kwargs = {}
                if s['format'] == 'JPEG':
                    if img.mode == 'RGBA':
                        img = img.convert('RGB')
                    save_kwargs = {'quality': s['quality'], 'optimize': True}
                elif s['format'] == 'PNG':
                    save_kwargs = {'optimize': True}
                elif s['format'] == 'WebP':
                    save_kwargs = {'quality': s['quality']}

                img.save(out_path, s['format'], **save_kwargs)
                success += 1

            except Exception as e:
                logging.error(f"Export error {filename}: {e}")
                errors += 1

        self.finished.emit(success, errors)

    def _apply_watermark(self, img, text, opacity=128):
        """Add text watermark to image"""
        overlay = Image.new('RGBA', img.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        # Try to use a reasonable font size
        font_size = max(16, min(img.width, img.height) // 30)
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", font_size)
        except Exception:
            font = ImageFont.load_default()

        bbox = draw.textbbox((0, 0), text, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        x = img.width - tw - 20
        y = img.height - th - 20

        draw.text((x, y), text, font=font, fill=(255, 255, 255, opacity))

        if img.mode != 'RGBA':
            img = img.convert('RGBA')
        result = Image.alpha_composite(img, overlay)
        return result.convert('RGB')

    def stop(self):
        self.should_stop = True


class BatchExportDialog(QDialog):
    """Professional batch export dialog with presets"""

    PRESETS = {
        "Instagram (1080x1080)": {"resize_mode": "fit", "max_width": 1080, "max_height": 1080, "format": "JPEG", "quality": 90},
        "Full HD (1920x1080)": {"resize_mode": "fit", "max_width": 1920, "max_height": 1080, "format": "JPEG", "quality": 92},
        "4K (3840x2160)": {"resize_mode": "fit", "max_width": 3840, "max_height": 2160, "format": "JPEG", "quality": 95},
        "Web (1200px)": {"resize_mode": "long_edge", "long_edge": 1200, "format": "JPEG", "quality": 85},
        "Thumbnail (300px)": {"resize_mode": "long_edge", "long_edge": 300, "format": "JPEG", "quality": 80},
        "PNG (оригинал)": {"resize_mode": "original", "format": "PNG", "quality": 100},
        "WebP (оригинал)": {"resize_mode": "original", "format": "WebP", "quality": 90},
        "Без изменений": {"resize_mode": "original", "format": "JPEG", "quality": 95},
    }

    def __init__(self, image_infos: list, parent=None):
        super().__init__(parent)
        self.image_infos = image_infos
        self.setWindowTitle(f"Экспорт ({len(image_infos)} файлов)")
        self.setMinimumSize(550, 600)
        self._worker = None
        self._thread = None
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # Preset
        preset_group = QGroupBox("Пресет")
        preset_layout = QFormLayout(preset_group)
        self.preset_combo = QComboBox()
        self.preset_combo.addItems(list(self.PRESETS.keys()))
        self.preset_combo.currentTextChanged.connect(self._apply_preset)
        preset_layout.addRow("Пресет:", self.preset_combo)
        layout.addWidget(preset_group)

        # Size settings
        size_group = QGroupBox("Размер")
        size_layout = QFormLayout(size_group)

        self.resize_combo = QComboBox()
        self.resize_combo.addItems(["Оригинал", "Вписать в размер", "По длинной стороне"])
        self.resize_combo.currentIndexChanged.connect(self._on_resize_mode_changed)
        size_layout.addRow("Режим:", self.resize_combo)

        size_row = QHBoxLayout()
        self.max_width_spin = QSpinBox()
        self.max_width_spin.setRange(100, 10000)
        self.max_width_spin.setValue(1920)
        size_row.addWidget(QLabel("Ш:"))
        size_row.addWidget(self.max_width_spin)
        self.max_height_spin = QSpinBox()
        self.max_height_spin.setRange(100, 10000)
        self.max_height_spin.setValue(1080)
        size_row.addWidget(QLabel("В:"))
        size_row.addWidget(self.max_height_spin)
        self.size_widget = QWidget()
        self.size_widget.setLayout(size_row)
        size_layout.addRow("Размер:", self.size_widget)

        self.long_edge_spin = QSpinBox()
        self.long_edge_spin.setRange(100, 10000)
        self.long_edge_spin.setValue(1200)
        self.long_edge_spin.setVisible(False)
        size_layout.addRow("Длинная сторона:", self.long_edge_spin)

        layout.addWidget(size_group)

        # Format & Quality
        format_group = QGroupBox("Формат и качество")
        format_layout = QFormLayout(format_group)

        self.format_combo = QComboBox()
        self.format_combo.addItems(["JPEG", "PNG", "WebP"])
        format_layout.addRow("Формат:", self.format_combo)

        quality_row = QHBoxLayout()
        self.quality_slider = QSlider(Qt.Orientation.Horizontal)
        self.quality_slider.setRange(10, 100)
        self.quality_slider.setValue(92)
        self.quality_label = QLabel("92%")
        self.quality_slider.valueChanged.connect(lambda v: self.quality_label.setText(f"{v}%"))
        quality_row.addWidget(self.quality_slider)
        quality_row.addWidget(self.quality_label)
        format_layout.addRow("Качество:", quality_row)

        layout.addWidget(format_group)

        # Watermark
        wm_group = QGroupBox("Водяной знак")
        wm_layout = QFormLayout(wm_group)

        self.watermark_check = QCheckBox("Добавить текстовый водяной знак")
        wm_layout.addRow(self.watermark_check)

        self.watermark_text = QLineEdit()
        self.watermark_text.setPlaceholderText("\u00a9 WiPhoto 2026")
        self.watermark_text.setEnabled(False)
        self.watermark_check.toggled.connect(self.watermark_text.setEnabled)
        wm_layout.addRow("Текст:", self.watermark_text)

        self.watermark_opacity = QSlider(Qt.Orientation.Horizontal)
        self.watermark_opacity.setRange(30, 255)
        self.watermark_opacity.setValue(128)
        self.watermark_opacity.setEnabled(False)
        self.watermark_check.toggled.connect(self.watermark_opacity.setEnabled)
        wm_layout.addRow("Прозрачность:", self.watermark_opacity)

        layout.addWidget(wm_group)

        # Output directory
        output_row = QHBoxLayout()
        self.output_edit = QLineEdit()
        self.output_edit.setPlaceholderText("Выберите папку...")
        output_row.addWidget(self.output_edit)
        browse_btn = QPushButton("Обзор...")
        browse_btn.clicked.connect(self._browse_output)
        output_row.addWidget(browse_btn)
        layout.addLayout(output_row)

        # Progress
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #808080; font-size: 12px;")
        layout.addWidget(self.status_label)

        # Buttons
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box.accepted.connect(self._start_export)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

        # Apply first preset
        self._apply_preset(self.preset_combo.currentText())

    def _apply_preset(self, name):
        preset = self.PRESETS.get(name, {})
        if not preset:
            return

        mode = preset.get('resize_mode', 'original')
        if mode == 'original':
            self.resize_combo.setCurrentIndex(0)
        elif mode == 'fit':
            self.resize_combo.setCurrentIndex(1)
            self.max_width_spin.setValue(preset.get('max_width', 1920))
            self.max_height_spin.setValue(preset.get('max_height', 1080))
        elif mode == 'long_edge':
            self.resize_combo.setCurrentIndex(2)
            self.long_edge_spin.setValue(preset.get('long_edge', 1200))

        fmt = preset.get('format', 'JPEG')
        idx = self.format_combo.findText(fmt)
        if idx >= 0:
            self.format_combo.setCurrentIndex(idx)

        self.quality_slider.setValue(preset.get('quality', 92))

    def _on_resize_mode_changed(self, index):
        self.size_widget.setVisible(index == 1)
        self.long_edge_spin.setVisible(index == 2)

    def _browse_output(self):
        d = QFileDialog.getExistingDirectory(self, "Папка для экспорта")
        if d:
            self.output_edit.setText(d)

    def _get_settings(self) -> dict:
        mode_map = {0: 'original', 1: 'fit', 2: 'long_edge'}
        s = {
            'resize_mode': mode_map.get(self.resize_combo.currentIndex(), 'original'),
            'max_width': self.max_width_spin.value(),
            'max_height': self.max_height_spin.value(),
            'long_edge': self.long_edge_spin.value(),
            'format': self.format_combo.currentText(),
            'quality': self.quality_slider.value(),
            'output_dir': self.output_edit.text(),
            'watermark_text': self.watermark_text.text() if self.watermark_check.isChecked() else '',
            'watermark_opacity': self.watermark_opacity.value(),
        }
        return s

    def _start_export(self):
        settings = self._get_settings()
        if not settings['output_dir']:
            self.status_label.setText("Выберите папку для экспорта!")
            return
        if not os.path.isdir(settings['output_dir']):
            os.makedirs(settings['output_dir'], exist_ok=True)

        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, len(self.image_infos))
        self.button_box.setEnabled(False)

        self._thread = QThread()
        self._worker = ExportWorker(self.image_infos, settings)
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)

        self._thread.start()

    def _on_progress(self, current, total, filename):
        self.progress_bar.setValue(current)
        self.status_label.setText(f"Экспорт: {current}/{total} — {filename}")

    def _on_finished(self, success, errors):
        self._thread.quit()
        self.button_box.setEnabled(True)
        self.status_label.setText(f"Готово! Успешно: {success}, ошибок: {errors}")
        if errors == 0:
            self.status_label.setStyleSheet("color: #2ecc71; font-size: 12px;")
        else:
            self.status_label.setStyleSheet("color: #e74c3c; font-size: 12px;")

    def closeEvent(self, event):
        if self._worker:
            self._worker.stop()
        if self._thread and self._thread.isRunning():
            self._thread.quit()
            self._thread.wait(2000)
        super().closeEvent(event)
