from PyQt6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QSlider, QFormLayout, QDoubleSpinBox, QAbstractSpinBox
from PyQt6.QtCore import Qt, pyqtSignal
from PIL import Image
from .base_tool import EditingTool


class RotationTool(EditingTool):
    live_update = pyqtSignal(float)
    applied = pyqtSignal()
    cancelled = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.angle = 0.0

    @property
    def name(self) -> str:
        return "rotation"

    @property
    def label(self) -> str:
        return "Поворот и выравнивание"

    def _create_ui(self, parent=None) -> QWidget:
        widget = QWidget(parent);
        layout = QVBoxLayout(widget);
        layout.setSpacing(15)
        form_layout = QFormLayout()
        self.spin_box = QDoubleSpinBox();
        self.spin_box.setRange(-180.0, 180.0)
        self.spin_box.setDecimals(1);
        self.spin_box.setSuffix("°");
        self.spin_box.setValue(self.angle)
        self.spin_box.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.PlusMinus)
        self.spin_box.setStyleSheet("""
            QDoubleSpinBox { background-color: white; color: #222; border: 1px solid #555; border-radius: 4px; padding: 2px 4px; }
            QDoubleSpinBox:focus { border: 1px solid #55aaff; } """)
        self.slider = QSlider(Qt.Orientation.Horizontal);
        self.slider.setRange(-1800, 1800)
        self.slider.setValue(int(self.angle * 10));
        self.slider.valueChanged.connect(self._on_slider_change)
        self.spin_box.valueChanged.connect(self._on_spinbox_change)
        form_layout.addRow("Угол:", self.spin_box);
        form_layout.addRow("Точно:", self.slider)
        apply_button = QPushButton("Применить");
        apply_button.clicked.connect(self.applied.emit)
        cancel_button = QPushButton("Отмена");
        cancel_button.clicked.connect(self.cancelled.emit)
        layout.addLayout(form_layout);
        layout.addWidget(apply_button);
        layout.addWidget(cancel_button);
        layout.addStretch()
        return widget

    def _set_angle(self, value: float):
        self.angle = round(value, 1);
        self.live_update.emit(self.angle)

    def _on_slider_change(self, value: int):
        angle = value / 10.0
        self.spin_box.blockSignals(True);
        self.spin_box.setValue(angle);
        self.spin_box.blockSignals(False)
        self._set_angle(angle)

    def _on_spinbox_change(self, value: float):
        self.slider.blockSignals(True);
        self.slider.setValue(int(value * 10));
        self.slider.blockSignals(False)
        self._set_angle(value)

    def apply(self, image: Image) -> Image:
        if self.angle == 0: return image
        return image.rotate(self.angle, resample=Image.Resampling.BICUBIC, expand=True, fillcolor=(0, 0, 0, 0))

    def activate(self, scene, image_rect):
        pass

    def deactivate(self, scene):
        pass

    def get_params(self) -> dict:
        return {"angle": self.angle}

    def set_params(self, params: dict):
        """
        Устанавливает параметры. Метод сделан "пуленепробиваемым" - он всегда
        обновит состояние, а UI - только если он существует.
        """
        self.angle = params.get("angle", 0.0) if params else 0.0

        # <<< ФИНАЛЬНОЕ ИСПРАВЛЕНИЕ:
        # Проверяем, что родительский виджет UI существует.
        # Это самая надежная проверка, что UI не был удален.
        if self._ui_widget is not None:
            # Если UI существует, то и дочерние виджеты тоже существуют.
            self.spin_box.blockSignals(True)
            self.spin_box.setValue(self.angle)
            self.spin_box.blockSignals(False)

            self.slider.blockSignals(True)
            self.slider.setValue(int(self.angle * 10))
            self.slider.blockSignals(False)

    def reset(self):
        self.set_params({"angle": 0.0})
# --- END OF FILE core/editing/tool_rotation.py ---