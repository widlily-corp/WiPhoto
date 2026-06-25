# views/about_dialog.py

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QLabel, QDialogButtonBox,
                             QHBoxLayout, QFrame)
from PyQt6.QtGui import QPixmap, QIcon
from PyQt6.QtCore import Qt, pyqtSignal
from utils import resource_path
from _meta import __version__, __author__, __email__, __copyright__, __description__


class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("О программе WiPhoto")
        self.setWindowIcon(QIcon(resource_path("assets/icon.ico")))
        self.setMinimumWidth(450)
        self.setObjectName("AboutDialog")  # Для применения стилей из QSS

        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(15)

        # --- Верхняя часть с иконкой и названием ---
        header_layout = QHBoxLayout()
        icon_label = QLabel()
        icon_pixmap = QPixmap(resource_path("assets/icon.ico"))
        icon_label.setPixmap(
            icon_pixmap.scaled(64, 64, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        header_layout.addWidget(icon_label)

        title_layout = QVBoxLayout()
        title_layout.setSpacing(2)
        title_label = QLabel("WiPhoto")
        title_label.setObjectName("AboutTitle")  # Для особого стиля, если нужно
        title_label.setStyleSheet("font-size: 22px; font-weight: bold;")
        version_label = QLabel(f"Версия {__version__}")
        title_layout.addWidget(title_label)
        title_layout.addWidget(version_label)
        header_layout.addLayout(title_layout)
        header_layout.addStretch()

        main_layout.addLayout(header_layout)

        # --- Описание ---
        description_label = QLabel(__description__)
        description_label.setWordWrap(True)
        main_layout.addWidget(description_label)

        # --- Разделитель ---
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        separator.setStyleSheet("background-color: rgba(255, 255, 255, 0.1);")
        main_layout.addWidget(separator)

        # --- Информация об авторе ---
        author_label = QLabel(f"Разработчик: <b>{__author__}</b>")
        copyright_label = QLabel(__copyright__)

        # Делаем email кликабельной ссылкой
        email_label = QLabel(f'Обратная связь: <a href="mailto:{__email__}" style="color: #55aaff;">{__email__}</a>')
        email_label.setOpenExternalLinks(True)

        main_layout.addWidget(author_label)
        main_layout.addWidget(copyright_label)
        main_layout.addWidget(email_label)

        # --- Кнопки ---
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        button_box.accepted.connect(self.accept)
        main_layout.addWidget(button_box, alignment=Qt.AlignmentFlag.AlignRight)