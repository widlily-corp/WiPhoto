from PyQt6.QtWidgets import QGraphicsRectItem, QGraphicsItem
from PyQt6.QtGui import QPen, QColor, QBrush, QPainter, QCursor
from PyQt6.QtCore import Qt, QRectF, QPointF

# Размер визуального маркера
HANDLE_SIZE = 14.0
# Дополнительная область вокруг маркера, где он тоже будет срабатывать (для удобства хвата)
SENSITIVITY = 10.0


class CropBoxItem(QGraphicsRectItem):
    """
    Интерактивный виджет рамки для кадрирования с улучшенным удобством использования.
    """

    def __init__(self, rect: QRectF, parent: QGraphicsItem = None):
        super().__init__(rect, parent)
        self.setAcceptHoverEvents(True)
        # Флаги для возможности перемещения и уведомления об изменениях
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)

        # Устанавливаем высокий Z-Value, чтобы рамка всегда была поверх картинки
        self.setZValue(1000)

        self._handles = {}
        self._active_handle = None
        self._mouse_press_pos = QPointF()
        self._mouse_press_rect = QRectF()

        self.update_handles()

    def boundingRect(self) -> QRectF:
        # Увеличиваем область перерисовки с учетом чувствительности,
        # чтобы не оставалось артефактов при движении
        adjust = HANDLE_SIZE + SENSITIVITY
        return self.rect().adjusted(-adjust, -adjust, adjust, adjust)

    def paint(self, painter: QPainter, option, widget=None):
        # 1. Рисуем затемнение внешней области (опционально, для лучшего контраста)
        # Можно добавить, если есть доступ к rect сцены, но пока рисуем саму рамку

        # 2. Рисуем основную пунктирную рамку
        pen = QPen(QColor(255, 255, 255, 255), 1.5, Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.setBrush(QBrush(Qt.GlobalColor.transparent))
        painter.drawRect(self.rect())

        # 3. Рисуем сетку третей (Rule of Thirds)
        pen.setStyle(Qt.PenStyle.SolidLine)
        pen.setWidthF(0.8)
        pen.setColor(QColor(255, 255, 255, 120))  # Полупрозрачные линии
        painter.setPen(pen)

        rect = self.rect()
        width = rect.width()
        height = rect.height()

        one_third_w = width / 3
        two_thirds_w = width * 2 / 3
        one_third_h = height / 3
        two_thirds_h = height * 2 / 3

        # Вертикальные линии
        painter.drawLine(QPointF(rect.left() + one_third_w, rect.top()),
                         QPointF(rect.left() + one_third_w, rect.bottom()))
        painter.drawLine(QPointF(rect.left() + two_thirds_w, rect.top()),
                         QPointF(rect.left() + two_thirds_w, rect.bottom()))
        # Горизонтальные линии
        painter.drawLine(QPointF(rect.left(), rect.top() + one_third_h),
                         QPointF(rect.right(), rect.top() + one_third_h))
        painter.drawLine(QPointF(rect.left(), rect.top() + two_thirds_h),
                         QPointF(rect.right(), rect.top() + two_thirds_h))

        # 4. Рисуем маркеры (ручки)
        painter.setBrush(QBrush(QColor(255, 255, 255, 255)))
        pen.setWidth(1)
        pen.setColor(QColor(0, 0, 0, 200))  # Черная обводка для контраста
        painter.setPen(pen)

        for handle_rect in self._handles.values():
            # Рисуем круги вместо квадратов - приятнее глазу
            painter.drawEllipse(handle_rect)

    def update_handles(self):
        """Пересчитывает позиции маркеров относительно текущего прямоугольника"""
        s = HANDLE_SIZE
        r = self.rect()

        # 1: TopLeft, 2: Top, 3: TopRight
        # 4: Right, 5: BottomRight, 6: Bottom
        # 7: BottomLeft, 8: Left

        self._handles[1] = QRectF(r.left() - s / 2, r.top() - s / 2, s, s)
        self._handles[2] = QRectF(r.center().x() - s / 2, r.top() - s / 2, s, s)
        self._handles[3] = QRectF(r.right() - s / 2, r.top() - s / 2, s, s)

        self._handles[4] = QRectF(r.right() - s / 2, r.center().y() - s / 2, s, s)
        self._handles[5] = QRectF(r.right() - s / 2, r.bottom() - s / 2, s, s)
        self._handles[6] = QRectF(r.center().x() - s / 2, r.bottom() - s / 2, s, s)

        self._handles[7] = QRectF(r.left() - s / 2, r.bottom() - s / 2, s, s)
        self._handles[8] = QRectF(r.left() - s / 2, r.center().y() - s / 2, s, s)

    def _get_handle_at(self, pos: QPointF):
        """
        Возвращает индекс маркера под курсором или None.
        Использует увеличенную область (SENSITIVITY) для проверки.
        """
        for i, rect in self._handles.items():
            # Создаем увеличенную зону захвата вокруг маркера
            hit_rect = rect.adjusted(-SENSITIVITY, -SENSITIVITY, SENSITIVITY, SENSITIVITY)
            if hit_rect.contains(pos):
                return i
        return None

    def hoverMoveEvent(self, event):
        handle = self._get_handle_at(event.pos())
        if handle is not None:
            self.setCursor(self.get_cursor_for_handle(handle))
        else:
            # Если мы внутри рамки, но не на маркере - курсор перемещения
            if self.rect().contains(event.pos()):
                self.setCursor(Qt.CursorShape.SizeAllCursor)
            else:
                self.setCursor(Qt.CursorShape.ArrowCursor)
        super().hoverMoveEvent(event)

    def mousePressEvent(self, event):
        self._mouse_press_pos = event.pos()
        self._mouse_press_rect = self.rect()

        handle = self._get_handle_at(event.pos())

        if handle is not None:
            self._active_handle = handle
        else:
            # 0 означает перемещение всей рамки
            self._active_handle = 0
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._active_handle is None:
            return

        # Если перемещаем всю рамку
        if self._active_handle == 0:
            super().mouseMoveEvent(event)
            return

        # Логика изменения размера
        pos = event.pos()
        rect = QRectF(self._mouse_press_rect)

        # Вычисляем дельту от начальной точки нажатия?
        # Нет, здесь проще работать с абсолютными координатами мыши относительно item,
        # но так как item трансформируется, надежнее использовать дельту от нажатия
        # и применять её к сохраненному rect.

        delta = pos - self._mouse_press_pos

        new_rect = QRectF(self._mouse_press_rect)

        # Top
        if self._active_handle in [1, 2, 3]:
            new_rect.setTop(min(new_rect.bottom() - 10, new_rect.top() + delta.y()))
        # Right
        if self._active_handle in [3, 4, 5]:
            new_rect.setRight(max(new_rect.left() + 10, new_rect.right() + delta.x()))
        # Bottom
        if self._active_handle in [5, 6, 7]:
            new_rect.setBottom(max(new_rect.top() + 10, new_rect.bottom() + delta.y()))
        # Left
        if self._active_handle in [7, 8, 1]:
            new_rect.setLeft(min(new_rect.right() - 10, new_rect.left() + delta.x()))

        self.prepareGeometryChange()
        self.setRect(new_rect.normalized())
        self.update_handles()

    def mouseReleaseEvent(self, event):
        self._active_handle = None
        super().mouseReleaseEvent(event)

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange:
            # При перемещении рамки ручки не меняются относительно рамки,
            # но если бы мы рисовали что-то внешнее, нужно было бы обновить.
            pass
        return super().itemChange(change, value)

    def get_cursor_for_handle(self, handle_index: int) -> QCursor:
        cursors = {
            1: Qt.CursorShape.SizeFDiagCursor,  # Top-Left
            2: Qt.CursorShape.SizeVerCursor,  # Top
            3: Qt.CursorShape.SizeBDiagCursor,  # Top-Right
            4: Qt.CursorShape.SizeHorCursor,  # Right
            5: Qt.CursorShape.SizeFDiagCursor,  # Bottom-Right
            6: Qt.CursorShape.SizeVerCursor,  # Bottom
            7: Qt.CursorShape.SizeBDiagCursor,  # Bottom-Left
            8: Qt.CursorShape.SizeHorCursor  # Left
        }
        return QCursor(cursors.get(handle_index, Qt.CursorShape.SizeAllCursor))