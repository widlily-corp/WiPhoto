from PyQt6.QtWidgets import QWidget, QFormLayout, QSlider, QLabel
from PyQt6.QtCore import Qt
import numpy as np
from PIL import Image
from .base_tool import EditingTool


class VignetteTool(EditingTool):
    def __init__(self):
        super().__init__()
        self.amount = 0;
        self.feather = 50

    @property
    def name(self) -> str:
        return "vignette"

    @property
    def label(self) -> str:
        return "Виньетка"

    def _create_ui(self, parent=None) -> QWidget:
        widget = QWidget(parent);
        layout = QFormLayout(widget);
        layout.setContentsMargins(0, 5, 0, 5)
        self.amount_slider = QSlider(Qt.Orientation.Horizontal);
        self.amount_slider.setRange(-100, 100);
        self.amount_slider.setValue(self.amount)
        self.amount_slider.valueChanged.connect(lambda val: self.valueChanged.emit(self.name, "amount", val, True))
        self.amount_slider.sliderReleased.connect(
            lambda: self.valueChanged.emit(self.name, "amount", self.amount_slider.value(), False))

        self.feather_slider = QSlider(Qt.Orientation.Horizontal);
        self.feather_slider.setRange(1, 100);
        self.feather_slider.setValue(self.feather)
        self.feather_slider.valueChanged.connect(lambda val: self.valueChanged.emit(self.name, "feather", val, True))
        self.feather_slider.sliderReleased.connect(
            lambda: self.valueChanged.emit(self.name, "feather", self.feather_slider.value(), False))

        layout.addRow("Эффект", self.amount_slider);
        layout.addRow("Растушевка", self.feather_slider)
        return widget

    def apply(self, image: Image) -> Image:
        if self.amount == 0: return image
        img_np = np.array(image);
        height, width, _ = img_np.shape
        x = np.linspace(-1, 1, width);
        y = np.linspace(-1, 1, height)
        xx, yy = np.meshgrid(x, y)
        radius = np.sqrt(xx ** 2 + yy ** 2)
        radius /= np.sqrt(2)
        vignette_mask = 1 - radius * (2.0 - self.feather / 50.0)
        vignette_mask = np.clip(vignette_mask, 0, 1)[:, :, np.newaxis]

        if self.amount > 0:
            factor = 1.0 - self.amount / 100.0
            img_np = (img_np * (factor + (1.0 - factor) * vignette_mask)).astype(np.uint8)
        else:
            factor = -self.amount / 100.0
            white_vignette = (1.0 - vignette_mask) * factor * 255
            img_np = np.clip(img_np + white_vignette, 0, 255).astype(np.uint8)
        return Image.fromarray(img_np)

    def get_params(self) -> dict:
        return {"amount": self.amount, "feather": self.feather}

    def set_params(self, params: dict):
        self.amount = params.get("amount", 0);
        self.feather = params.get("feather", 50)
        if hasattr(self, 'amount_slider'): self.amount_slider.setValue(self.amount)
        if hasattr(self, 'feather_slider'): self.feather_slider.setValue(self.feather)

    def reset(self):
        self.set_params({"amount": 0, "feather": 50})
# --- END OF FILE core/editing/tool_vignette.py ---