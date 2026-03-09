# views/slideshow_widget.py

import os
from PyQt6.QtWidgets import QWidget, QLabel, QVBoxLayout, QHBoxLayout
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QPixmap, QPainter, QColor, QFont, QKeyEvent, QImage
from PIL import Image

from models.image_model import ImageInfo, RAW_EXTENSIONS, VIDEO_EXTENSIONS

RAW_FORMATS = RAW_EXTENSIONS
VIDEO_FORMATS = VIDEO_EXTENSIONS


class SlideshowWindow(QWidget):
    """Fullscreen slideshow with transitions, timer, and navigation"""

    def __init__(self, image_infos: list, interval_sec: int = 4, parent=None):
        super().__init__(parent)
        self.image_infos = [i for i in image_infos if not i.is_video()]
        self.current_index = 0
        self.interval = interval_sec * 1000
        self.is_paused = False

        self.setWindowTitle("WiPhoto — Слайдшоу")
        self.setStyleSheet("background-color: black;")
        self.setCursor(Qt.CursorShape.BlankCursor)

        self._current_pixmap = None
        self._opacity = 1.0

        # Timer
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._next)

        # Info overlay timer (auto-hide)
        self.info_visible = True
        self.info_timer = QTimer(self)
        self.info_timer.setSingleShot(True)
        self.info_timer.timeout.connect(self._hide_info)

        if self.image_infos:
            self._load_image(0)
            self.timer.start(self.interval)
            self.info_timer.start(3000)

    def _load_image(self, index: int):
        if not self.image_infos:
            return

        self.current_index = index % len(self.image_infos)
        info = self.image_infos[self.current_index]

        try:
            path = info.path
            if path.lower().endswith(RAW_FORMATS):
                import rawpy
                with rawpy.imread(path) as raw:
                    rgb = raw.postprocess(use_camera_wb=True, output_bps=8)
                pil_img = Image.fromarray(rgb)
            else:
                pil_img = Image.open(path)

            try:
                if pil_img.mode != 'RGB':
                    pil_img = pil_img.convert('RGB')

                q_img = QImage(
                    pil_img.tobytes(),
                    pil_img.width, pil_img.height,
                    pil_img.width * 3,
                    QImage.Format.Format_RGB888
                )
                self._current_pixmap = QPixmap.fromImage(q_img)
            finally:
                pil_img.close()
        except Exception:
            self._current_pixmap = None

        self.update()

    def _next(self):
        if not self.is_paused and self.image_infos:
            self._load_image(self.current_index + 1)

    def _prev(self):
        if self.image_infos:
            self._load_image(self.current_index - 1)

    def _toggle_pause(self):
        self.is_paused = not self.is_paused
        if self.is_paused:
            self.timer.stop()
        else:
            self.timer.start(self.interval)
        self.info_visible = True
        self.info_timer.start(3000)
        self.update()

    def _hide_info(self):
        self.info_visible = False
        self.update()

    def _show_info_briefly(self):
        self.info_visible = True
        self.info_timer.start(3000)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        # Black background
        painter.fillRect(self.rect(), QColor(0, 0, 0))

        # Image
        if self._current_pixmap and not self._current_pixmap.isNull():
            scaled = self._current_pixmap.scaled(
                self.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            x = (self.width() - scaled.width()) // 2
            y = (self.height() - scaled.height()) // 2
            painter.drawPixmap(x, y, scaled)

        # Info overlay
        if self.info_visible and self.image_infos:
            info = self.image_infos[self.current_index]
            self._draw_overlay(painter, info)

    def _draw_overlay(self, painter: QPainter, info: ImageInfo):
        # Bottom bar
        bar_h = 50
        bar_rect = self.rect().adjusted(0, self.height() - bar_h, 0, 0)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(0, 0, 0, 160))
        painter.drawRect(bar_rect)

        # Filename
        font = QFont("Segoe UI", 14)
        painter.setFont(font)
        painter.setPen(QColor(220, 220, 220))
        filename = os.path.basename(info.path)
        painter.drawText(bar_rect.adjusted(20, 0, 0, 0),
                         Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                         filename)

        # Counter
        counter = f"{self.current_index + 1} / {len(self.image_infos)}"
        painter.drawText(bar_rect.adjusted(0, 0, -20, 0),
                         Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                         counter)

        # Pause indicator
        if self.is_paused:
            font2 = QFont("Segoe UI", 12)
            painter.setFont(font2)
            painter.setPen(QColor("#f1c40f"))
            painter.drawText(bar_rect, Qt.AlignmentFlag.AlignCenter, "\u23F8 ПАУЗА")

        # Rating
        if info.rating > 0:
            star_text = "\u2605" * info.rating
            painter.setPen(QColor("#f1c40f"))
            painter.drawText(bar_rect.adjusted(0, 0, -150, 0),
                             Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                             star_text)

    def keyPressEvent(self, event: QKeyEvent):
        key = event.key()
        if key == Qt.Key.Key_Escape:
            self.timer.stop()
            self.close()
        elif key == Qt.Key.Key_Space:
            self._toggle_pause()
        elif key in (Qt.Key.Key_Right, Qt.Key.Key_Down):
            self._load_image(self.current_index + 1)
            self._show_info_briefly()
        elif key in (Qt.Key.Key_Left, Qt.Key.Key_Up):
            self._prev()
            self._show_info_briefly()
        elif key == Qt.Key.Key_Home:
            self._load_image(0)
            self._show_info_briefly()
        elif key == Qt.Key.Key_End:
            self._load_image(len(self.image_infos) - 1)
            self._show_info_briefly()
        # Rating during slideshow
        elif Qt.Key.Key_0 <= key <= Qt.Key.Key_5:
            if self.image_infos:
                info = self.image_infos[self.current_index]
                info.rating = key - Qt.Key.Key_0
                self._show_info_briefly()
        else:
            super().keyPressEvent(event)

    def mousePressEvent(self, event):
        self._show_info_briefly()
        if event.button() == Qt.MouseButton.LeftButton:
            self._toggle_pause()
        elif event.button() == Qt.MouseButton.RightButton:
            self.timer.stop()
            self.close()

    def closeEvent(self, event):
        self.timer.stop()
        self.setCursor(Qt.CursorShape.ArrowCursor)
        super().closeEvent(event)
