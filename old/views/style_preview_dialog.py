# views/style_preview_dialog.py

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QDialogButtonBox, QWidget)
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import Qt
import utils


class StylePreviewDialog(QDialog):
    def __init__(self, before_pixmap: QPixmap, after_pixmap: QPixmap, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Предпросмотр стиля")
        self.setMinimumSize(1000, 500)

        main_layout = QVBoxLayout(self)
        images_layout = QHBoxLayout()

        # --- Область "До" ---
        before_widget = QWidget()
        before_layout = QVBoxLayout(before_widget)
        before_label = QLabel("До")
        before_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.before_image_label = QLabel()
        self.before_image_label.setPixmap(before_pixmap.scaled(
            450, 450, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
        ))
        before_layout.addWidget(before_label)
        before_layout.addWidget(self.before_image_label)

        # --- Область "После" ---
        after_widget = QWidget()
        after_layout = QVBoxLayout(after_widget)
        after_label = QLabel("После")
        after_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.after_image_label = QLabel()
        self.after_image_label.setPixmap(after_pixmap.scaled(
            450, 450, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
        ))
        after_layout.addWidget(after_label)
        after_layout.addWidget(self.after_image_label)

        # --- Кнопки ---
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        button_box.button(QDialogButtonBox.StandardButton.Save).setText("Сохранить как новый файл")

        images_layout.addWidget(before_widget)
        images_layout.addWidget(after_widget)
        main_layout.addLayout(images_layout)
        main_layout.addWidget(button_box)