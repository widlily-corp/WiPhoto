
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QPushButton, QSlider,
                             QLabel, QHBoxLayout, QMessageBox, QProgressBar)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QImage
from PIL import Image

from .base_tool import EditingTool
from core.editing.items.mask_drawing_item import MaskDrawingItem
from core.api.local_inpainting import LocalInpaintingWorker


class SmartRetouchTool(EditingTool):
    applied = pyqtSignal()
    cancelled = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.mask_item = None
        self.worker = None
        self.brush_size = 40
        self.is_processing = False
        self._ui_widget = None

    @property
    def name(self) -> str:
        return "smart_retouch"

    @property
    def label(self) -> str:
        return "✨ Умное ретуширование"

    def _create_ui(self, parent=None) -> QWidget:
        widget = QWidget(parent)
        layout = QVBoxLayout(widget)
        layout.setSpacing(10)

        info = QLabel("Закрасьте объект:")
        info.setStyleSheet("color: #aaa; font-size: 11px;")
        layout.addWidget(info)

        brush_layout = QHBoxLayout()
        brush_layout.addWidget(QLabel("Кисть:"))
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(10, 200)
        self.slider.setValue(self.brush_size)
        self.slider.valueChanged.connect(self._on_brush_size_change)
        brush_layout.addWidget(self.slider)
        layout.addLayout(brush_layout)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setTextVisible(False)
        self.progress.setVisible(False)
        self.progress.setStyleSheet("QProgressBar { height: 4px; }")
        layout.addWidget(self.progress)

        self.apply_btn = QPushButton("✨ Удалить")
        self.apply_btn.setStyleSheet(
            "QPushButton { background-color: #00a152; color: white; font-weight: bold; padding: 8px; } QPushButton:hover { background-color: #00c853; }")

        self.cancel_btn = QPushButton("Отмена")
        self.cancel_btn.clicked.connect(self.cancelled.emit)

        layout.addWidget(self.apply_btn)
        layout.addWidget(self.cancel_btn)
        layout.addStretch()

        return widget

    def _on_brush_size_change(self, value):
        self.brush_size = value
        if self.mask_item:
            self.mask_item.setBrushSize(value)

    def activate(self, scene, image_rect):
        # image_rect - это координаты картинки на сцене. Обычно (0,0, W, H).
        if not self.mask_item:
            self.mask_item = MaskDrawingItem(image_rect)
            self.mask_item.setBrushSize(self.brush_size)
            self.mask_item.setZValue(100)
            scene.addItem(self.mask_item)

    def deactivate(self, scene):
        if self.mask_item:
            scene.removeItem(self.mask_item)
            self.mask_item = None
        self._set_loading(False)

    def _set_loading(self, active: bool):
        self.is_processing = active
        if self._ui_widget:
            self.progress.setVisible(active)
            self.apply_btn.setEnabled(not active)
            self.cancel_btn.setEnabled(not active)
            self.slider.setEnabled(not active)
            if active:
                self.apply_btn.setText("Идет обработка...")
            else:
                self.apply_btn.setText("✨ Удалить")

    def process_with_image(self, current_pil_image):
        if not self.mask_item: return
        self._set_loading(True)

        # Получаем размеры ИМЕННО КАРТИНКИ
        img_w, img_h = current_pil_image.size

        # Генерируем маску строго под размер картинки
        q_mask = self.mask_item.get_mask_image(img_w, img_h)

        # Конвертация QImage -> bytes -> PIL Image
        q_mask = q_mask.convertToFormat(QImage.Format.Format_RGBA8888)
        width = q_mask.width()
        height = q_mask.height()
        ptr = q_mask.bits()
        ptr.setsize(height * width * 4)
        data = bytes(ptr)
        mask_pil = Image.frombytes('RGBA', (width, height), data)

        self.worker = LocalInpaintingWorker(current_pil_image, mask_pil)
        self.worker.finished.connect(self._on_success)
        self.worker.error.connect(self._on_error)
        self.worker.start()

    def _on_success(self, result_image):
        self._set_loading(False)
        self.result_image = result_image
        self.applied.emit()

    def _on_error(self, error_msg):
        self._set_loading(False)
        QMessageBox.critical(None, "Ошибка", f"Сбой: {error_msg}")

    def apply(self, image: Image) -> Image:
        if hasattr(self, 'result_image') and self.result_image:
            return self.result_image
        return image

    def get_params(self) -> dict:
        return {}

    def set_params(self, params: dict):
        pass

    def reset(self):
        self.result_image = None