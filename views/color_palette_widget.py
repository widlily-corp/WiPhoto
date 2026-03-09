# views/color_palette_widget.py

import numpy as np
from PyQt6.QtWidgets import QWidget, QToolTip
from PyQt6.QtCore import Qt, QRectF, QPointF
from PyQt6.QtGui import QPainter, QColor, QPen, QFont, QFontMetrics, QMouseEvent
from PIL import Image


class ColorPaletteWidget(QWidget):
    """Displays dominant colors extracted from an image using k-means clustering"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(50)
        self.setMaximumHeight(60)
        self._colors = []  # list of (r, g, b, percentage)
        self.setMouseTracking(True)

    def set_image_path(self, path: str, n_colors: int = 6):
        """Extract dominant colors from image"""
        try:
            with Image.open(path) as img:
                img.thumbnail((150, 150))
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                arr = np.array(img).reshape(-1, 3).astype(np.float64)

            # Simple k-means
            colors = self._kmeans(arr, n_colors)
            self._colors = colors
            self.update()
        except Exception:
            self._colors = []
            self.update()

    def _kmeans(self, pixels, k, max_iter=10):
        """Lightweight k-means for color extraction"""
        n = len(pixels)
        if n == 0:
            return []

        # Init centroids by sampling
        indices = np.linspace(0, n - 1, k, dtype=int)
        centroids = pixels[indices].copy()

        labels = np.zeros(n, dtype=int)

        for _ in range(max_iter):
            # Assign
            for i in range(k):
                if i == 0:
                    dists = np.sum((pixels - centroids[0]) ** 2, axis=1)
                    labels[:] = 0
                    min_dists = dists.copy()
                else:
                    dists = np.sum((pixels - centroids[i]) ** 2, axis=1)
                    mask = dists < min_dists
                    labels[mask] = i
                    min_dists[mask] = dists[mask]

            # Update
            for i in range(k):
                cluster = pixels[labels == i]
                if len(cluster) > 0:
                    centroids[i] = cluster.mean(axis=0)

        # Calculate percentages
        result = []
        for i in range(k):
            count = np.sum(labels == i)
            pct = count / n * 100
            r, g, b = int(centroids[i][0]), int(centroids[i][1]), int(centroids[i][2])
            result.append((r, g, b, pct))

        # Sort by percentage descending
        result.sort(key=lambda x: x[3], reverse=True)
        return result

    def clear(self):
        self._colors = []
        self.update()

    def paintEvent(self, event):
        if not self._colors:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self.rect().adjusted(1, 1, -1, -1)
        w = rect.width()
        h = rect.height()
        x0 = rect.x()
        y0 = rect.y()

        # Draw color bars proportional to percentage
        total_pct = sum(c[3] for c in self._colors)
        if total_pct <= 0:
            return

        current_x = float(x0)
        swatch_h = h - 16  # Leave room for hex text

        for i, (r, g, b, pct) in enumerate(self._colors):
            bar_w = (pct / total_pct) * w
            if bar_w < 2:
                continue

            color = QColor(r, g, b)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(color)

            bar_rect = QRectF(current_x, y0, bar_w, swatch_h)
            if i == 0:
                path_r = 3.0
            else:
                path_r = 0.0
            painter.drawRoundedRect(bar_rect, path_r, path_r)

            # Hex label below
            hex_str = f"#{r:02x}{g:02x}{b:02x}"
            font = QFont("Segoe UI", 7)
            painter.setFont(font)
            fm = QFontMetrics(font)
            text_w = fm.horizontalAdvance(hex_str)

            if bar_w > text_w + 4:
                text_color = QColor(200, 200, 200) if (r * 0.299 + g * 0.587 + b * 0.114) < 128 else QColor(60, 60, 60)
                painter.setPen(text_color)
                text_rect = QRectF(current_x, y0 + swatch_h, bar_w, 16)
                painter.setPen(QColor("#999999"))
                painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, hex_str)

            current_x += bar_w

        # Border
        painter.setPen(QPen(QColor("#3c3c3c"), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(QRectF(x0, y0, w, swatch_h), 3, 3)

    def mouseMoveEvent(self, event: QMouseEvent):
        """Show color info on hover"""
        if not self._colors:
            return

        rect = self.rect().adjusted(1, 1, -1, -1)
        total_pct = sum(c[3] for c in self._colors)
        if total_pct <= 0:
            return

        mx = event.position().x() - rect.x()
        current_x = 0.0
        w = rect.width()

        for r, g, b, pct in self._colors:
            bar_w = (pct / total_pct) * w
            if current_x <= mx < current_x + bar_w:
                hex_str = f"#{r:02x}{g:02x}{b:02x}"
                QToolTip.showText(event.globalPosition().toPoint(),
                                  f"{hex_str}\nRGB({r}, {g}, {b})\n{pct:.1f}%")
                return
            current_x += bar_w
