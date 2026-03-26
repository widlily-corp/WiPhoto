# views/document_scan_dialog.py

import os
import cv2
import numpy as np
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                             QComboBox, QFileDialog, QSplitter, QWidget)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap, QImage

from core.document_scanner import DocumentScanner


class DocumentScanDialog(QDialog):
    """Диалог сканирования документа с превью"""

    def __init__(self, image_path: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Сканер документов")
        self.setMinimumSize(900, 600)
        self.image_path = image_path
        self.scanner = DocumentScanner()
        self._original = cv2.imread(image_path)
        self._result = None

        self._init_ui()
        self._update_preview()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # Mode selector
        top_bar = QHBoxLayout()
        top_bar.addWidget(QLabel("Режим:"))
        self.mode_combo = QComboBox()
        self.mode_combo.addItems([
            "Авто", "Чистый документ", "Чёрно-белый", "Цветной", "Без обработки"
        ])
        self.mode_combo.currentIndexChanged.connect(self._update_preview)
        top_bar.addWidget(self.mode_combo)
        top_bar.addStretch()

        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #888; font-size: 12px;")
        top_bar.addWidget(self.status_label)
        layout.addLayout(top_bar)

        # Preview area: original | result
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: original with detected corners
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_label = QLabel("Оригинал")
        left_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        left_label.setStyleSheet("color: #999; font-size: 11px; font-weight: bold;")
        left_layout.addWidget(left_label)
        self.original_preview = QLabel()
        self.original_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.original_preview.setStyleSheet("background: #1e1e1e; border: 1px solid #3c3c3c;")
        left_layout.addWidget(self.original_preview)
        splitter.addWidget(left)

        # Right: scanned result
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_label = QLabel("Результат")
        right_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        right_label.setStyleSheet("color: #999; font-size: 11px; font-weight: bold;")
        right_layout.addWidget(right_label)
        self.result_preview = QLabel()
        self.result_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.result_preview.setStyleSheet("background: #1e1e1e; border: 1px solid #3c3c3c;")
        right_layout.addWidget(self.result_preview)
        splitter.addWidget(right)

        layout.addWidget(splitter, stretch=1)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        save_btn = QPushButton("Сохранить как...")
        save_btn.setStyleSheet("padding: 8px 20px; background: #0078d4; color: white; border: none; border-radius: 4px;")
        save_btn.clicked.connect(self._save_result)
        btn_layout.addWidget(save_btn)

        replace_btn = QPushButton("Заменить оригинал")
        replace_btn.setStyleSheet("padding: 8px 20px; background: #d4380d; color: white; border: none; border-radius: 4px;")
        replace_btn.clicked.connect(self._replace_original)
        btn_layout.addWidget(replace_btn)

        cancel_btn = QPushButton("Закрыть")
        cancel_btn.setStyleSheet("padding: 8px 20px;")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        layout.addLayout(btn_layout)

    def _get_mode(self) -> str:
        mode_map = {0: "auto", 1: "clean", 2: "bw", 3: "color", 4: "none"}
        return mode_map.get(self.mode_combo.currentIndex(), "auto")

    def _update_preview(self):
        if self._original is None:
            return

        # Show original with detected corners
        preview_with_corners, corners = self.scanner.get_preview_with_corners(self._original)
        self._show_cv_image(self.original_preview, preview_with_corners)

        if corners:
            self.status_label.setText("Документ обнаружен ✓")
            self.status_label.setStyleSheet("color: #2ecc71; font-size: 12px;")
        else:
            self.status_label.setText("Границы не найдены — используется всё изображение")
            self.status_label.setStyleSheet("color: #f39c12; font-size: 12px;")

        # Generate result
        mode = self._get_mode()
        self._result = self.scanner.scan_to_numpy(self._original, enhance_mode=mode)
        self._show_cv_image(self.result_preview, self._result)

    def _show_cv_image(self, label: QLabel, cv_img: np.ndarray):
        """Display OpenCV image in QLabel"""
        if cv_img is None:
            return
        rgb = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        q_img = QImage(rgb.data, w, h, w * ch, QImage.Format.Format_RGB888)
        pixmap = QPixmap.fromImage(q_img)
        scaled = pixmap.scaled(label.size(), Qt.AspectRatioMode.KeepAspectRatio,
                               Qt.TransformationMode.SmoothTransformation)
        label.setPixmap(scaled)

    def _save_result(self):
        if self._result is None:
            return
        base, ext = os.path.splitext(self.image_path)
        default_path = f"{base}_scan{ext}"
        path, _ = QFileDialog.getSaveFileName(
            self, "Сохранить сканированный документ", default_path,
            "Images (*.jpg *.png *.tiff *.bmp)"
        )
        if path:
            cv2.imwrite(path, self._result)
            self.accept()

    def _replace_original(self):
        if self._result is None:
            return
        cv2.imwrite(self.image_path, self._result)
        self.accept()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Re-render previews on resize
        if self._original is not None:
            self._update_preview()
