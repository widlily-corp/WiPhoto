# views/document_scan_dialog.py

import os
import cv2
import numpy as np
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                             QComboBox, QFileDialog, QGraphicsView, QGraphicsScene,
                             QGraphicsEllipseItem, QGraphicsPolygonItem, QWidget,
                             QSplitter, QGraphicsPixmapItem)
from PyQt6.QtCore import Qt, QPointF, QRectF
from PyQt6.QtGui import QPixmap, QImage, QColor, QPen, QBrush, QPolygonF, QPainter

from core.document_scanner import DocumentScanner, DocumentCorners


HANDLE_RADIUS = 12
HANDLE_COLOR = QColor(0, 120, 255)
HANDLE_HOVER_COLOR = QColor(50, 180, 255)
LINE_COLOR = QColor(0, 200, 100, 180)


class CornerHandle(QGraphicsEllipseItem):
    """Перетаскиваемая точка угла документа"""

    def __init__(self, x: float, y: float, index: int, view: 'CornerEditView'):
        r = HANDLE_RADIUS
        super().__init__(-r, -r, r * 2, r * 2)
        self.setPos(x, y)
        self.index = index
        self._view = view
        self.setBrush(QBrush(HANDLE_COLOR))
        self.setPen(QPen(Qt.GlobalColor.white, 2))
        self.setFlag(QGraphicsEllipseItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsEllipseItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setCursor(Qt.CursorShape.SizeAllCursor)
        self.setZValue(10)
        self.setAcceptHoverEvents(True)

    def hoverEnterEvent(self, event):
        self.setBrush(QBrush(HANDLE_HOVER_COLOR))
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self.setBrush(QBrush(HANDLE_COLOR))
        super().hoverLeaveEvent(event)

    def itemChange(self, change, value):
        if change == QGraphicsEllipseItem.GraphicsItemChange.ItemPositionChange:
            # Clamp to image bounds
            new_pos = value
            rect = self._view.image_rect()
            if rect:
                x = max(rect.left(), min(rect.right(), new_pos.x()))
                y = max(rect.top(), min(rect.bottom(), new_pos.y()))
                new_pos = QPointF(x, y)
            return new_pos
        if change == QGraphicsEllipseItem.GraphicsItemChange.ItemPositionHasChanged:
            self._view.update_polygon()
            self._view.on_corners_changed()
        return super().itemChange(change, value)


class CornerEditView(QGraphicsView):
    """Вид для редактирования углов документа — изображение + перетаскиваемые точки"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setStyleSheet("background: #1e1e1e; border: 1px solid #3c3c3c;")

        self._pixmap_item: QGraphicsPixmapItem = None
        self._handles: list[CornerHandle] = []
        self._polygon: QGraphicsPolygonItem = None
        self._dialog = None  # will be set by dialog
        self._img_w = 0
        self._img_h = 0

    def image_rect(self) -> QRectF:
        if self._pixmap_item:
            return self._pixmap_item.boundingRect()
        return QRectF()

    def set_image(self, cv_img: np.ndarray):
        """Показать изображение"""
        self._scene.clear()
        self._handles = []
        self._polygon = None
        self._pixmap_item = None

        rgb = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        self._img_w = w
        self._img_h = h
        bytes_per_line = w * ch
        q_img = QImage(rgb.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
        pixmap = QPixmap.fromImage(q_img.copy())  # copy to keep data alive
        self._pixmap_item = self._scene.addPixmap(pixmap)
        self._scene.setSceneRect(QRectF(0, 0, w, h))
        self.fitInView(self._scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def set_corners(self, corners: DocumentCorners):
        """Устанавливает углы и создаёт ручки"""
        # Remove old handles & polygon
        for h in self._handles:
            self._scene.removeItem(h)
        if self._polygon:
            self._scene.removeItem(self._polygon)

        self._handles = []
        pts = [corners.top_left, corners.top_right,
               corners.bottom_right, corners.bottom_left]
        for i, (x, y) in enumerate(pts):
            handle = CornerHandle(x, y, i, self)
            self._scene.addItem(handle)
            self._handles.append(handle)

        # Polygon overlay
        self._polygon = QGraphicsPolygonItem()
        self._polygon.setPen(QPen(LINE_COLOR, 3))
        fill = QColor(0, 200, 100, 30)
        self._polygon.setBrush(QBrush(fill))
        self._polygon.setZValue(5)
        self._scene.addItem(self._polygon)
        self.update_polygon()

    def set_default_corners(self):
        """Углы = весь кадр (фоллбэк)"""
        margin = 20
        corners = DocumentCorners(
            top_left=(margin, margin),
            top_right=(self._img_w - margin, margin),
            bottom_right=(self._img_w - margin, self._img_h - margin),
            bottom_left=(margin, self._img_h - margin),
        )
        self.set_corners(corners)

    def get_corners(self) -> DocumentCorners:
        """Возвращает текущие позиции углов"""
        if len(self._handles) != 4:
            return None
        pts = [(int(h.pos().x()), int(h.pos().y())) for h in self._handles]
        return DocumentCorners(
            top_left=pts[0], top_right=pts[1],
            bottom_right=pts[2], bottom_left=pts[3]
        )

    def update_polygon(self):
        if self._polygon and len(self._handles) == 4:
            poly = QPolygonF([h.pos() for h in self._handles])
            self._polygon.setPolygon(poly)

    def on_corners_changed(self):
        if self._dialog:
            self._dialog._update_result()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._pixmap_item:
            self.fitInView(self._scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)


class DocumentScanDialog(QDialog):
    """Диалог сканирования документа с интерактивными углами"""

    def __init__(self, image_path: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Сканер документов")
        self.setMinimumSize(1000, 650)
        self.image_path = image_path
        self.scanner = DocumentScanner()
        self._original = cv2.imread(image_path)
        self._result = None

        if self._original is None:
            return

        self._init_ui()
        self._auto_detect()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # Top bar
        top_bar = QHBoxLayout()

        auto_btn = QPushButton("Автодетект")
        auto_btn.setToolTip("Попробовать найти границы документа автоматически")
        auto_btn.setStyleSheet("padding: 6px 16px; background: #0078d4; color: white; border: none; border-radius: 4px;")
        auto_btn.clicked.connect(self._auto_detect)
        top_bar.addWidget(auto_btn)

        reset_btn = QPushButton("Сброс (весь кадр)")
        reset_btn.setToolTip("Сбросить углы на весь кадр")
        reset_btn.setStyleSheet("padding: 6px 16px;")
        reset_btn.clicked.connect(self._reset_corners)
        top_bar.addWidget(reset_btn)

        top_bar.addSpacing(20)
        top_bar.addWidget(QLabel("Режим:"))
        self.mode_combo = QComboBox()
        self.mode_combo.addItems([
            "Авто", "Чистый документ", "Чёрно-белый", "Цветной", "Без обработки"
        ])
        self.mode_combo.currentIndexChanged.connect(self._update_result)
        top_bar.addWidget(self.mode_combo)

        top_bar.addStretch()
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #888; font-size: 12px;")
        top_bar.addWidget(self.status_label)

        layout.addLayout(top_bar)

        # Hint
        hint = QLabel("Перетащите синие точки для корректировки углов документа")
        hint.setStyleSheet("color: #666; font-size: 11px; font-style: italic; padding: 0 4px;")
        layout.addWidget(hint)

        # Splitter: corner editor | result preview
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: original with draggable corners
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_label = QLabel("Оригинал — выберите углы документа")
        left_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        left_label.setStyleSheet("color: #999; font-size: 11px; font-weight: bold;")
        left_layout.addWidget(left_label)

        self.corner_view = CornerEditView()
        self.corner_view._dialog = self
        left_layout.addWidget(self.corner_view)
        splitter.addWidget(left)

        # Right: result preview
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_label = QLabel("Результат")
        right_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        right_label.setStyleSheet("color: #999; font-size: 11px; font-weight: bold;")
        right_layout.addWidget(right_label)

        self.result_label = QLabel()
        self.result_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.result_label.setStyleSheet("background: #1e1e1e; border: 1px solid #3c3c3c;")
        self.result_label.setMinimumSize(200, 200)
        right_layout.addWidget(self.result_label)
        splitter.addWidget(right)

        splitter.setSizes([500, 500])
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

    def _auto_detect(self):
        """Запуск автодетекта"""
        self.corner_view.set_image(self._original)
        corners = self.scanner.detect_document(self._original)
        if corners:
            self.corner_view.set_corners(corners)
            self.status_label.setText("Документ обнаружен — корректируйте углы если нужно")
            self.status_label.setStyleSheet("color: #2ecc71; font-size: 12px;")
        else:
            self.corner_view.set_default_corners()
            self.status_label.setText("Границы не найдены — выберите углы вручную")
            self.status_label.setStyleSheet("color: #f39c12; font-size: 12px;")
        self._update_result()

    def _reset_corners(self):
        """Сброс углов на весь кадр"""
        self.corner_view.set_default_corners()
        self.status_label.setText("Углы сброшены — перетащите на границы документа")
        self.status_label.setStyleSheet("color: #888; font-size: 12px;")
        self._update_result()

    def _update_result(self):
        """Обновить превью результата по текущим углам"""
        corners = self.corner_view.get_corners()
        if corners is None or self._original is None:
            return

        mode = self._get_mode()
        self._result = self.scanner.scan_with_corners(self._original, corners, mode)
        self._show_result()

    def _show_result(self):
        if self._result is None:
            return
        rgb = cv2.cvtColor(self._result, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        q_img = QImage(rgb.data, w, h, w * ch, QImage.Format.Format_RGB888)
        pixmap = QPixmap.fromImage(q_img.copy())
        scaled = pixmap.scaled(self.result_label.size(),
                               Qt.AspectRatioMode.KeepAspectRatio,
                               Qt.TransformationMode.SmoothTransformation)
        self.result_label.setPixmap(scaled)

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
        if self._result is not None:
            self._show_result()
