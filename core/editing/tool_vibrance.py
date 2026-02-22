from PyQt6.QtWidgets import QWidget, QFormLayout, QSlider
from PyQt6.QtCore import Qt
import numpy as np
from PIL import Image
from .base_tool import EditingTool


class VibranceTool(EditingTool):
    def __init__(self):
        super().__init__(); self.value = 0

    @property
    def name(self) -> str:
        return "vibrance"

    @property
    def label(self) -> str:
        return "Красочность"

    def _create_ui(self, parent=None) -> QWidget:
        widget = QWidget(parent)
        layout = QFormLayout(widget);
        layout.setContentsMargins(0, 5, 0, 5)
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(-100, 100);
        self.slider.setValue(self.value)
        self.slider.valueChanged.connect(lambda val: self.valueChanged.emit(self.name, "value", val, True))
        self.slider.sliderReleased.connect(
            lambda: self.valueChanged.emit(self.name, "value", self.slider.value(), False))
        layout.addRow(self.label, self.slider)
        return widget

    def apply(self, image: Image) -> Image:
        if self.value == 0: return image
        img_hsv = np.array(image.convert('HSV'), dtype=np.float32)
        s_channel = img_hsv[:, :, 1]

        factor = self.value / 100.0
        if factor > 0:
            # Увеличиваем насыщенность, сильнее для менее насыщенных цветов
            s_channel += factor * (255 - s_channel)
        else:
            # Уменьшаем насыщенность
            s_channel += factor * s_channel

        img_hsv[:, :, 1] = np.clip(s_channel, 0, 255)
        return Image.fromarray(img_hsv.astype(np.uint8), 'HSV').convert('RGB')

    def get_params(self) -> dict:
        return {"value": self.value}

    def set_params(self, params: dict):
        self.value = params.get("value", 0)
        if hasattr(self, 'slider'): self.slider.setValue(self.value)

    def reset(self):
        self.set_params({"value": 0})
# --- END OF FILE core/editing/tool_vibrance.py ---