# core/editing/tool_brightness.py

from PyQt6.QtWidgets import QWidget, QFormLayout, QLabel, QSlider
from PyQt6.QtCore import Qt, pyqtSignal
from PIL import Image, ImageEnhance
from .base_tool import EditingTool


class BrightnessTool(EditingTool):
    valueChanged = pyqtSignal(int, bool)

    def __init__(self):
        super().__init__()
        self.value = 1.0  # 1.0 - без изменений

    @property
    def name(self) -> str:
        return "brightness"

    @property
    def label(self) -> str:
        return "Яркость"

    def _create_ui(self, parent=None) -> QWidget:
        widget = QWidget(parent)
        layout = QFormLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)

        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 200)  # 0% - 200%
        self.slider.setValue(int(self.value * 100))
        self.slider.valueChanged.connect(lambda val: self.valueChanged.emit(val, True))
        self.slider.sliderReleased.connect(lambda: self.valueChanged.emit(self.slider.value(), False))

        layout.addRow(self.label, self.slider)
        return widget

    def apply(self, image: Image) -> Image:
        if self.value == 1.0: return image
        enhancer = ImageEnhance.Brightness(image)
        return enhancer.enhance(self.value)

    def get_params(self) -> dict:
        return {"value": self.value}

    def set_params(self, params: dict):
        self.value = params.get("value", 1.0)
        if self._ui_widget:
            self.slider.setValue(int(self.value * 100))

    def reset(self):
        self.set_params({"value": 1.0})