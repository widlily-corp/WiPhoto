from PyQt6.QtWidgets import QWidget, QFormLayout, QSlider
from PyQt6.QtCore import Qt
import numpy as np
from PIL import Image, ImageOps
from .base_tool import EditingTool

class WhitesTool(EditingTool):
    def __init__(self): super().__init__(); self.value = 0
    @property
    def name(self) -> str: return "whites"
    @property
    def label(self) -> str: return "Белые"

    def _create_ui(self, parent=None) -> QWidget:
        widget = QWidget(parent)
        layout = QFormLayout(widget); layout.setContentsMargins(0, 5, 0, 5)
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(-100, 100); self.slider.setValue(self.value)
        self.slider.valueChanged.connect(lambda val: self.valueChanged.emit(self.name, "value", val, True))
        self.slider.sliderReleased.connect(lambda: self.valueChanged.emit(self.name, "value", self.slider.value(), False))
        layout.addRow(self.label, self.slider)
        return widget

    def apply(self, image: Image) -> Image:
        if self.value == 0: return image
        # Значение > 0 делает белые ярче, < 0 - темнее
        whitepoint = self.value * 0.2
        return ImageOps.autocontrast(image, cutoff=(0, whitepoint if whitepoint > 0 else 0))

    def get_params(self) -> dict: return {"value": self.value}
    def set_params(self, params: dict):
        self.value = params.get("value", 0)
        if hasattr(self, 'slider'): self.slider.setValue(self.value)
    def reset(self): self.set_params({"value": 0})
# --- END OF FILE core/editing/tool_whites.py ---