# views/fullscreen_viewer.py

import os
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                             QGraphicsView, QGraphicsScene, QGraphicsPixmapItem,
                             QPushButton, QApplication)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap, QImage, QWheelEvent, QKeyEvent, QPainter, QColor, QIcon
from PIL import Image

from core.analyzer import _load_image_optimized
from models.image_model import ImageInfo, RAW_EXTENSIONS
from utils import resource_path

VIDEO_EXTENSIONS = ('.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v')


class FullscreenView(QGraphicsView):
    """Зумируемый вид для полноэкранного просмотра"""
    zoom_changed = pyqtSignal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setStyleSheet("background: #000; border: none;")
        self._pixmap_item = None
        self._zoom = 1.0

    def set_pixmap(self, pixmap: QPixmap):
        self._scene.clear()
        self._pixmap_item = self._scene.addPixmap(pixmap)
        self._scene.setSceneRect(self._pixmap_item.boundingRect())
        self._zoom = 1.0
        self.resetTransform()
        self.fitInView(self._pixmap_item, Qt.AspectRatioMode.KeepAspectRatio)
        # Calculate actual zoom after fit
        if pixmap.width() > 0:
            view_w = self.viewport().width()
            scale_x = self.transform().m11()
            self._zoom = scale_x
        self.zoom_changed.emit(self._zoom)

    def wheelEvent(self, event: QWheelEvent):
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        self._zoom *= factor
        self.scale(factor, factor)
        self.zoom_changed.emit(self._zoom)

    def fit_view(self):
        if self._pixmap_item:
            self.resetTransform()
            self.fitInView(self._pixmap_item, Qt.AspectRatioMode.KeepAspectRatio)
            self._zoom = self.transform().m11()
            self.zoom_changed.emit(self._zoom)

    def zoom_100(self):
        if self._pixmap_item:
            self.resetTransform()
            self._zoom = 1.0
            self.zoom_changed.emit(self._zoom)


class FullscreenViewer(QWidget):
    """Полноэкранный просмотрщик с инфо-баром и навигацией"""

    closed = pyqtSignal()

    def __init__(self, image_list: list, start_index: int = 0, parent=None):
        super().__init__(parent)
        self._images = image_list
        self._index = start_index
        self.setWindowFlags(Qt.WindowType.Window)
        self.setStyleSheet("background: #000;")

        try:
            self.setWindowIcon(QIcon(resource_path("assets/icon.ico")))
        except Exception:
            pass

        self._init_ui()
        self._show_current()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Info bar (top)
        self.info_bar = QLabel("")
        self.info_bar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.info_bar.setStyleSheet("""
            background: rgba(0,0,0,0.7); color: #ccc; font-size: 12px;
            padding: 6px 12px; font-family: monospace;
        """)
        self.info_bar.setFixedHeight(32)
        layout.addWidget(self.info_bar)

        # Main view
        self.view = FullscreenView()
        self.view.zoom_changed.connect(self._update_info)
        layout.addWidget(self.view, stretch=1)

        # Bottom bar with nav buttons
        bottom = QHBoxLayout()
        bottom.setContentsMargins(8, 4, 8, 4)

        btn_style = "QPushButton { background: rgba(255,255,255,0.1); color: #ccc; border: none; border-radius: 4px; padding: 6px 16px; font-size: 14px; } QPushButton:hover { background: rgba(255,255,255,0.2); }"

        prev_btn = QPushButton("◀ Назад")
        prev_btn.setStyleSheet(btn_style)
        prev_btn.clicked.connect(self._prev)
        bottom.addWidget(prev_btn)

        bottom.addStretch()

        fit_btn = QPushButton("Вписать")
        fit_btn.setStyleSheet(btn_style)
        fit_btn.clicked.connect(self.view.fit_view)
        bottom.addWidget(fit_btn)

        zoom100_btn = QPushButton("100%")
        zoom100_btn.setStyleSheet(btn_style)
        zoom100_btn.clicked.connect(self.view.zoom_100)
        bottom.addWidget(zoom100_btn)

        bottom.addStretch()

        next_btn = QPushButton("Далее ▶")
        next_btn.setStyleSheet(btn_style)
        next_btn.clicked.connect(self._next)
        bottom.addWidget(next_btn)

        close_btn = QPushButton("✕")
        close_btn.setStyleSheet("QPushButton { background: rgba(255,0,0,0.3); color: white; border: none; border-radius: 4px; padding: 6px 12px; font-size: 14px; } QPushButton:hover { background: rgba(255,0,0,0.5); }")
        close_btn.clicked.connect(self.close)
        bottom.addWidget(close_btn)

        layout.addLayout(bottom)

    def _show_current(self):
        if not self._images or self._index < 0 or self._index >= len(self._images):
            return

        info = self._images[self._index]
        pixmap = self._load_pixmap(info.path)
        if pixmap and not pixmap.isNull():
            self.view.set_pixmap(pixmap)
        self._current_zoom = 1.0
        self._update_info(self.view._zoom)

    def _update_info(self, zoom: float = 1.0):
        if not self._images or self._index < 0:
            return
        info = self._images[self._index]
        name = os.path.basename(info.path)
        w, h = info.width, info.height
        mp = (w * h) / 1_000_000 if w and h else 0
        size_kb = info.file_size / 1024
        if size_kb > 1024:
            size_str = f"{size_kb / 1024:.1f} MB"
        else:
            size_str = f"{size_kb:.0f} KB"
        idx = self._index + 1
        total = len(self._images)
        zoom_pct = int(zoom * 100)

        self.info_bar.setText(
            f"{name}  ( {w} x {h} = {mp:.2f} MP ,  {size_str} )  "
            f"[ {idx} / {total} ]  {zoom_pct}%"
        )
        self.setWindowTitle(f"WiPhoto — {name}")

    def _load_pixmap(self, path: str) -> QPixmap:
        """Загружает изображение с точным управлением цветом для полноэкранного режима"""
        try:
            pil_img = _load_image_optimized(path, for_thumbnail=False)
            if pil_img is None:
                return None

            from utils import pil_to_color_managed_pixmap
            pixmap = pil_to_color_managed_pixmap(pil_img)
            pil_img.close()
            return pixmap
        except Exception:
            return None

    def _next(self):
        if self._index < len(self._images) - 1:
            self._index += 1
            self._show_current()

    def _prev(self):
        if self._index > 0:
            self._index -= 1
            self._show_current()

    def keyPressEvent(self, event: QKeyEvent):
        key = event.key()
        if key in (Qt.Key.Key_Right, Qt.Key.Key_Space):
            self._next()
        elif key == Qt.Key.Key_Left:
            self._prev()
        elif key in (Qt.Key.Key_Escape, Qt.Key.Key_Q):
            self.close()
        elif key == Qt.Key.Key_F:
            if self.isFullScreen():
                self.showNormal()
            else:
                self.showFullScreen()
        elif key == Qt.Key.Key_0:
            self.view.fit_view()
        elif key == Qt.Key.Key_1:
            self.view.zoom_100()
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event):
        self.closed.emit()
        super().closeEvent(event)
