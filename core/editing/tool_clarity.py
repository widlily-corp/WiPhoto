from PyQt6.QtWidgets import QWidget, QFormLayout, QSlider
from PyQt6.QtCore import Qt
import numpy as np
from PIL import Image, ImageFilter
from .base_tool import EditingTool


class ClarityTool(EditingTool):
    def __init__(self):
        super().__init__(); self.value = 0

    @property
    def name(self) -> str:
        return "clarity"

    @property
    def label(self) -> str:
        return "Четкость"

    def _create_ui(self, parent=None) -> QWidget:
        widget = QWidget(parent)
        layout = QFormLayout(widget);
        layout.setContentsMargins(0, 5, 0, 5)
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 100);
        self.slider.setValue(self.value)
        self.slider.valueChanged.connect(lambda val: self.valueChanged.emit(self.name, "value", val, True))
        self.slider.sliderReleased.connect(
            lambda: self.valueChanged.emit(self.name, "value", self.slider.value(), False))
        layout.addRow(self.label, self.slider)
        return widget

    def apply(self, image: Image) -> Image:
        if self.value == 0: return image

        # Конвертируем в LAB и работаем с каналом L
        img_lab = image.convert('LAB')
        l_channel, a_channel, b_channel = img_lab.split()

        # Создаем маску локального контраста через Unsharp Mask с большим радиусом
        unsharp_mask = l_channel.filter(ImageFilter.UnsharpMask(radius=20, percent=200, threshold=3))

        # Смешиваем оригинал с маской
        l_channel_blended = Image.blend(l_channel, unsharp_mask, alpha=self.value / 100.0)

        # Собираем изображение обратно
        return Image.merge('LAB', (l_channel_blended, a_channel, b_channel)).convert('RGB')

    def get_params(self) -> dict:
        return {"value": self.value}

    def set_params(self, params: dict):
        self.value = params.get("value", 0)
        if hasattr(self, 'slider'): self.slider.setValue(self.value)

    def reset(self):
        self.set_params({"value": 0})
# --- END OF FILE core/editing/tool_clarity.py ---