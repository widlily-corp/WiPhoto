# views/histogram_widget.py

import numpy as np
from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QPainter, QColor, QPen, QLinearGradient, QImage, QPixmap, QPainterPath
from PIL import Image


class HistogramWidget(QWidget):
    """RGB histogram widget like Lightroom"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(100)
        self.setMaximumHeight(150)
        self._hist_r = None
        self._hist_g = None
        self._hist_b = None
        self._hist_l = None  # luminance

    def set_image_path(self, path: str):
        """Calculate histogram from image file"""
        try:
            with Image.open(path) as img:
                img.thumbnail((400, 400))  # downsample for speed
                if img.mode != 'RGB':
                    img = img.convert('RGB')

                arr = np.array(img)

            self._hist_r = np.histogram(arr[:, :, 0], bins=256, range=(0, 256))[0]
            self._hist_g = np.histogram(arr[:, :, 1], bins=256, range=(0, 256))[0]
            self._hist_b = np.histogram(arr[:, :, 2], bins=256, range=(0, 256))[0]

            # Luminance
            lum = 0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]
            self._hist_l = np.histogram(lum, bins=256, range=(0, 256))[0]

            self.update()
        except Exception as e:
            self._hist_r = None
            self.update()

    def clear(self):
        self._hist_r = None
        self._hist_g = None
        self._hist_b = None
        self._hist_l = None
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self.rect().adjusted(1, 1, -1, -1)

        # Background
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#1e1e1e"))
        painter.drawRoundedRect(QRectF(rect), 3, 3)

        if self._hist_r is None:
            painter.setPen(QColor("#555555"))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "Гистограмма")
            return

        # Normalize
        max_val = max(
            self._hist_r.max(), self._hist_g.max(),
            self._hist_b.max(), self._hist_l.max(), 1
        )

        w = rect.width()
        h = rect.height() - 4
        x0 = rect.x()
        y0 = rect.y() + 2

        # Draw channels with transparency
        channels = [
            (self._hist_r, QColor(220, 50, 50, 80)),
            (self._hist_g, QColor(50, 200, 50, 80)),
            (self._hist_b, QColor(50, 100, 220, 80)),
        ]

        for hist, color in channels:
            painter.setPen(QPen(color.darker(120), 1))
            painter.setBrush(color)

            path = QPainterPath()
            path.moveTo(x0, y0 + h)

            for i in range(256):
                px = x0 + (i / 255.0) * w
                py = y0 + h - (hist[i] / max_val) * h
                path.lineTo(px, py)

            path.lineTo(x0 + w, y0 + h)
            path.closeSubpath()
            painter.drawPath(path)

        # Luminance overlay (white, thin line)
        painter.setPen(QPen(QColor(200, 200, 200, 120), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        lum_path = QPainterPath()
        lum_path.moveTo(x0, y0 + h - (self._hist_l[0] / max_val) * h)
        for i in range(1, 256):
            px = x0 + (i / 255.0) * w
            py = y0 + h - (self._hist_l[i] / max_val) * h
            lum_path.lineTo(px, py)
        painter.drawPath(lum_path)

        # Border
        painter.setPen(QPen(QColor("#3c3c3c"), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(QRectF(rect), 3, 3)
