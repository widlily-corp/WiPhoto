
from PyQt6.QtWidgets import QGraphicsObject
from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QPainter, QColor, QPen, QImage, QPixmap


class MaskDrawingItem(QGraphicsObject):
    def __init__(self, rect, parent=None):
        super().__init__(parent)
        self._rect = rect
        self._brush_size = 40
        self._last_point = None

        width = int(rect.width())
        height = int(rect.height())

        # 1. Слой для экрана (Прозрачный фон, Красная кисть)
        self._display_buffer = QPixmap(width, height)
        self._display_buffer.fill(Qt.GlobalColor.transparent)

        # 2. Слой для нейросети (Черный фон, Белая кисть)
        # Format_RGB32 гарантирует, что цвета будут чистыми (0,0,0 и 255,255,255)
        self._neural_mask = QImage(width, height, QImage.Format.Format_RGB32)
        self._neural_mask.fill(Qt.GlobalColor.black)

        # Полупрозрачность только для отображения на экране
        self.setOpacity(0.5)

        self.setAcceptHoverEvents(True)
        self.setAcceptedMouseButtons(Qt.MouseButton.LeftButton)

    def boundingRect(self):
        return self._rect

    def setBrushSize(self, size):
        self._brush_size = size
        self.update()

    def paint(self, painter, option, widget=None):
        # На экране рисуем только красивый красный слой
        painter.drawPixmap(0, 0, self._display_buffer)

        # Рисуем курсор
        if self._last_point:
            painter.setPen(QPen(Qt.GlobalColor.white, 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(self._last_point, self._brush_size / 2, self._brush_size / 2)

    def hoverMoveEvent(self, event):
        self._last_point = event.pos()
        self.update()
        super().hoverMoveEvent(event)

    def mousePressEvent(self, event):
        self._last_point = event.pos()
        self._draw_line(self._last_point, self._last_point)
        event.accept()

    def mouseMoveEvent(self, event):
        current_point = event.pos()
        if self._last_point:
            self._draw_line(self._last_point, current_point)
        self._last_point = current_point
        event.accept()

    def mouseReleaseEvent(self, event):
        self._last_point = event.pos()
        super().mouseReleaseEvent(event)

    def _draw_line(self, p1, p2):
        """Рисуем одновременно на двух слоях"""

        # 1. Рисуем Красным на экране
        painter_display = QPainter(self._display_buffer)
        pen_display = QPen(QColor(255, 0, 0))  # Красный
        pen_display.setWidth(self._brush_size)
        pen_display.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen_display.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter_display.setPen(pen_display)
        painter_display.drawLine(p1, p2)
        painter_display.end()

        # 2. Рисуем Белым на маске для нейросети
        painter_mask = QPainter(self._neural_mask)
        pen_mask = QPen(QColor(255, 255, 255))  # Белый
        pen_mask.setWidth(self._brush_size)
        pen_mask.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen_mask.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter_mask.setPen(pen_mask)
        painter_mask.drawLine(p1, p2)
        painter_mask.end()

        self.update()

    def get_mask_image(self, width, height):
        """
        Просто возвращаем готовую черно-белую маску,
        масштабируя её при необходимости.
        """
        if self._neural_mask.width() != width or self._neural_mask.height() != height:
            return self._neural_mask.scaled(int(width), int(height),
                                            Qt.AspectRatioMode.IgnoreAspectRatio,
                                            Qt.TransformationMode.SmoothTransformation)
        return self._neural_mask