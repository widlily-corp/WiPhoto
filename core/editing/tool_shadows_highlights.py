# core/editing/tool_shadows_highlights.py

from PyQt6.QtWidgets import QWidget, QFormLayout, QLabel, QSlider
from PyQt6.QtCore import Qt, pyqtSignal
from PIL import Image, ImageOps
import numpy as np
from .base_tool import EditingTool


class ShadowsHighlightsTool(EditingTool):
    valueChanged = pyqtSignal(str, int, bool)

    def __init__(self):
        super().__init__()
        self.shadows = 0  # 0 to 100
        self.highlights = 0  # 0 to 100 (будем инвертировать для применения)

    @property
    def name(self) -> str:
        return "shadows_highlights"

    @property
    def label(self) -> str:
        return "Тени и Света"

    def _create_ui(self, parent=None) -> QWidget:
        widget = QWidget(parent)
        layout = QFormLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)

        self.shadows_slider = QSlider(Qt.Orientation.Horizontal)
        self.shadows_slider.setRange(0, 100)
        self.shadows_slider.setValue(self.shadows)
        self.shadows_slider.valueChanged.connect(lambda val: self.valueChanged.emit("shadows", val, True))
        self.shadows_slider.sliderReleased.connect(
            lambda: self.valueChanged.emit("shadows", self.shadows_slider.value(), False))

        self.highlights_slider = QSlider(Qt.Orientation.Horizontal)
        self.highlights_slider.setRange(0, 100)
        self.highlights_slider.setValue(self.highlights)
        self.highlights_slider.valueChanged.connect(lambda val: self.valueChanged.emit("highlights", val, True))
        self.highlights_slider.sliderReleased.connect(
            lambda: self.valueChanged.emit("highlights", self.highlights_slider.value(), False))

        layout.addRow("Тени", self.shadows_slider)
        layout.addRow("Света", self.highlights_slider)
        return widget

    def apply(self, image: Image) -> Image:
        if self.shadows == 0 and self.highlights == 0:
            return image

        img_np = np.array(image, dtype=np.float32) / 255.0

        # Конвертируем в LAB, чтобы работать только с яркостью (L канал)
        img_lab = Image.fromarray((img_np * 255).astype(np.uint8)).convert('LAB')
        l, a, b = img_lab.split()
        l_np = np.array(l, dtype=np.float32) / 255.0

        # Обработка теней (осветление темных участков)
        if self.shadows != 0:
            shadow_mask = 1.0 - l_np
            # Гамма-коррекция для темных участков
            l_np = 1.0 - (1.0 - l_np) ** (1 + self.shadows / 100.0)
            l_np = l_np * shadow_mask + np.array(l, dtype=np.float32) / 255.0 * (1 - shadow_mask)

        # Обработка светов (затемнение светлых участков)
        if self.highlights != 0:
            highlight_mask = l_np
            l_np = l_np ** (1 + self.highlights / 100.0)
            l_np = l_np * highlight_mask + np.array(l, dtype=np.float32) / 255.0 * (1 - highlight_mask)

        l_np = np.clip(l_np * 255, 0, 255).astype(np.uint8)

        merged_lab = Image.merge('LAB', [Image.fromarray(l_np), a, b])
        return merged_lab.convert('RGB')

    def get_params(self) -> dict:
        return {"shadows": self.shadows, "highlights": self.highlights}

    def set_params(self, params: dict):
        self.shadows = params.get("shadows", 0)
        self.highlights = params.get("highlights", 0)
        if self._ui_widget:
            self.shadows_slider.setValue(self.shadows)
            self.highlights_slider.setValue(self.highlights)

    def reset(self):
        self.set_params({"shadows": 0, "highlights": 0})