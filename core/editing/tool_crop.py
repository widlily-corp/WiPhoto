# Этот инструмент модальный и остается почти без изменений
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QPushButton
from PyQt6.QtCore import pyqtSignal, QRectF
from PIL import Image
from .base_tool import EditingTool
# Убедитесь, что .items.crop_box_item существует и корректен
# from .items.crop_box_item import CropBoxItem

class CropTool(EditingTool):
    applied = pyqtSignal()
    cancelled = pyqtSignal()
    def __init__(self): super().__init__(); self.crop_box_item = None
    @property
    def name(self) -> str: return "crop"
    @property
    def label(self) -> str: return "Кадрирование"

    def _create_ui(self, parent=None) -> QWidget:
        widget = QWidget(parent)
        layout = QVBoxLayout(widget)
        apply_button = QPushButton("Применить"); apply_button.clicked.connect(self.applied.emit)
        cancel_button = QPushButton("Отмена"); cancel_button.clicked.connect(self.cancelled.emit)
        layout.addWidget(apply_button); layout.addWidget(cancel_button); layout.addStretch()
        return widget

    def apply(self, image: Image) -> Image:
        if not self.crop_box_item: return image
        crop_rect = self.crop_box_item.rect()
        box = (int(crop_rect.left()), int(crop_rect.top()), int(crop_rect.right()), int(crop_rect.bottom()))
        return image.crop(box)

    def activate(self, scene, image_rect):
        from .items.crop_box_item import CropBoxItem
        if not self.crop_box_item:
            self.crop_box_item = CropBoxItem(QRectF(image_rect))
            scene.addItem(self.crop_box_item)

    def deactivate(self, scene):
        if self.crop_box_item:
            scene.removeItem(self.crop_box_item)
            self.crop_box_item = None

    def get_params(self) -> dict: return {}
    def set_params(self, params: dict): pass
    def reset(self): pass
# --- END OF FILE core/editing/tool_crop.py ---