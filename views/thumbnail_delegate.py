# views/thumbnail_delegate.py

import os
from PyQt6.QtWidgets import QStyledItemDelegate, QStyle
from PyQt6.QtCore import Qt, QSize, QRect, QRectF, QPointF
from PyQt6.QtGui import (QPainter, QPixmap, QColor, QPen, QFont,
                         QBrush, QPolygonF, QFontMetrics, QPainterPath)
from models.image_model import ImageInfo


class ThumbnailDelegate(QStyledItemDelegate):
    """Professional thumbnail delegate for uniform grid rendering"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cell_size = 200
        self._padding = 4
        self._info_bar_height = 24
        self._pixmap_cache = {}

    def set_cell_size(self, size: int):
        self._cell_size = size

    def sizeHint(self, option, index):
        total = self._cell_size + self._info_bar_height + self._padding * 2
        return QSize(total, total)

    def paint(self, painter: QPainter, option, index):
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        info = index.data(Qt.ItemDataRole.UserRole)
        rect = option.rect

        # Cell background
        cell_rect = rect.adjusted(2, 2, -2, -2)
        bg_color = QColor("#2d2d2d")

        # Selection / hover
        is_selected = option.state & QStyle.StateFlag.State_Selected
        is_hovered = option.state & QStyle.StateFlag.State_MouseOver

        if is_selected:
            bg_color = QColor("#2a4a6b")
        elif is_hovered:
            bg_color = QColor("#333333")

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(bg_color)
        path = QPainterPath()
        path.addRoundedRect(QRectF(cell_rect), 4, 4)
        painter.drawPath(path)

        # Image area
        img_rect = QRect(
            cell_rect.x() + self._padding,
            cell_rect.y() + self._padding,
            cell_rect.width() - self._padding * 2,
            cell_rect.height() - self._padding * 2 - self._info_bar_height
        )

        # Draw thumbnail
        if isinstance(info, ImageInfo) and info.thumbnail_path:
            pixmap = self._get_pixmap(info.thumbnail_path)
            if pixmap and not pixmap.isNull():
                # Scale to fill, keeping aspect ratio, center crop
                scaled = pixmap.scaled(
                    img_rect.size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                x = img_rect.x() + (img_rect.width() - scaled.width()) // 2
                y = img_rect.y() + (img_rect.height() - scaled.height()) // 2
                painter.drawPixmap(x, y, scaled)

                # Duplicate border
                if info.is_best_in_group:
                    painter.setPen(QPen(QColor("#4caf50"), 3))
                    painter.setBrush(Qt.BrushStyle.NoBrush)
                    painter.drawRect(img_rect.adjusted(1, 1, -1, -1))
                elif info.group_id is not None:
                    painter.setPen(QPen(QColor("#ff9800"), 3))
                    painter.setBrush(Qt.BrushStyle.NoBrush)
                    painter.drawRect(img_rect.adjusted(1, 1, -1, -1))

                # Video play icon
                if info.is_video():
                    self._draw_play_icon(painter, img_rect)

                # Face badge
                if info.faces_count > 0:
                    self._draw_badge(painter, img_rect, f"{info.faces_count}", QColor("#4a9eff"))

        # Selection border
        if is_selected:
            painter.setPen(QPen(QColor("#4a9eff"), 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(QRectF(cell_rect), 4, 4)

        # Info bar
        info_rect = QRect(
            cell_rect.x() + self._padding,
            cell_rect.bottom() - self._info_bar_height - self._padding + 2,
            cell_rect.width() - self._padding * 2,
            self._info_bar_height
        )
        self._draw_info_bar(painter, info_rect, info)

        painter.restore()

    def _get_pixmap(self, path: str) -> QPixmap:
        if path not in self._pixmap_cache:
            pixmap = QPixmap(path)
            self._pixmap_cache[path] = pixmap
            # Keep cache bounded
            if len(self._pixmap_cache) > 500:
                # Remove oldest entries
                keys = list(self._pixmap_cache.keys())
                for k in keys[:100]:
                    del self._pixmap_cache[k]
        return self._pixmap_cache.get(path)

    def _draw_play_icon(self, painter: QPainter, rect: QRect):
        cx = rect.center().x()
        cy = rect.center().y()
        radius = 20

        # Circle background
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(0, 0, 0, 160))
        painter.drawEllipse(cx - radius, cy - radius, radius * 2, radius * 2)

        # Triangle
        painter.setBrush(QColor(255, 255, 255, 220))
        triangle = QPolygonF([
            QPointF(cx - 8, cy - 12),
            QPointF(cx - 8, cy + 12),
            QPointF(cx + 12, cy)
        ])
        painter.drawPolygon(triangle)

    def _draw_badge(self, painter: QPainter, rect: QRect, text: str, color: QColor):
        font = QFont("Segoe UI", 9, QFont.Weight.Bold)
        painter.setFont(font)
        fm = QFontMetrics(font)
        text_width = fm.horizontalAdvance(text) + 12
        badge_height = 18
        badge_x = rect.right() - text_width - 4
        badge_y = rect.top() + 4

        # Badge background
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(0, 0, 0, 180))
        badge_rect = QRectF(badge_x, badge_y, text_width, badge_height)
        painter.drawRoundedRect(badge_rect, 9, 9)

        # Badge text
        painter.setPen(color)
        painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, text)

    def _draw_info_bar(self, painter: QPainter, rect: QRect, info):
        if not isinstance(info, ImageInfo):
            return

        filename = os.path.basename(info.path)

        # Truncate filename
        font = QFont("Segoe UI", 10)
        painter.setFont(font)
        fm = QFontMetrics(font)
        elided = fm.elidedText(filename, Qt.TextElideMode.ElideMiddle, rect.width())

        painter.setPen(QColor("#999999"))
        painter.drawText(rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, elided)

    def clear_cache(self):
        self._pixmap_cache.clear()
