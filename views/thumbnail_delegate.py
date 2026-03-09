# views/thumbnail_delegate.py

import os
from collections import OrderedDict
from PyQt6.QtWidgets import QStyledItemDelegate, QStyle
from PyQt6.QtCore import Qt, QSize, QRect, QRectF, QPointF
from PyQt6.QtGui import (QPainter, QPixmap, QColor, QPen, QFont,
                         QBrush, QPolygonF, QFontMetrics, QPainterPath)
from models.image_model import ImageInfo


def _format_size(size_bytes: int) -> str:
    if size_bytes <= 0:
        return ""
    if size_bytes < 1024:
        return f"{size_bytes}B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.0f}K"
    else:
        return f"{size_bytes / (1024 * 1024):.1f}M"


class ThumbnailDelegate(QStyledItemDelegate):
    """Professional thumbnail delegate with ratings, badges, and info overlay"""

    STAR_FILLED = "\u2605"   # ★
    STAR_EMPTY = "\u2606"    # ☆

    COLOR_LABELS = {
        "red": "#e74c3c",
        "yellow": "#f1c40f",
        "green": "#2ecc71",
        "blue": "#3498db",
        "purple": "#9b59b6",
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cell_size = 200
        self._padding = 4
        self._info_bar_height = 36  # taller for two lines
        self._pixmap_cache = OrderedDict()
        self._cache_limit = 300

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

        is_selected = option.state & QStyle.StateFlag.State_Selected
        is_hovered = option.state & QStyle.StateFlag.State_MouseOver

        if is_selected:
            bg_color = QColor("#2a4a6b")
        elif is_hovered:
            bg_color = QColor("#353535")

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

        if isinstance(info, ImageInfo) and info.thumbnail_path:
            pixmap = self._get_pixmap(info.thumbnail_path)
            if pixmap and not pixmap.isNull():
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

                # Color label dot (top-left)
                if info.color_label and info.color_label in self.COLOR_LABELS:
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.setBrush(QColor(self.COLOR_LABELS[info.color_label]))
                    painter.drawEllipse(img_rect.x() + 6, img_rect.y() + 6, 10, 10)

                # Video play icon
                if info.is_video():
                    self._draw_play_icon(painter, img_rect)

                # Top-right badges
                badge_y = img_rect.top() + 4
                badge_x = img_rect.right() - 4

                # Face badge
                if info.faces_count > 0:
                    badge_x = self._draw_badge_right(painter, badge_x, badge_y,
                                                      str(info.faces_count), QColor("#4a9eff"))

                # Animal badge
                if info.animals_count > 0:
                    badge_x = self._draw_badge_right(painter, badge_x, badge_y,
                                                      "A", QColor("#2ecc71"))

                # Stars (bottom-left of image)
                if info.rating > 0:
                    self._draw_stars(painter, img_rect, info.rating)

                # Flag/Reject overlay
                if info.flag_status == "rejected":
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.setBrush(QColor(0, 0, 0, 140))
                    painter.drawRect(img_rect)
                    # X mark
                    painter.setPen(QPen(QColor("#e74c3c"), 3))
                    m = min(img_rect.width(), img_rect.height()) // 4
                    cx, cy = img_rect.center().x(), img_rect.center().y()
                    painter.drawLine(cx - m, cy - m, cx + m, cy + m)
                    painter.drawLine(cx + m, cy - m, cx - m, cy + m)
                elif info.flag_status == "picked":
                    self._draw_badge_right(painter, img_rect.right() - 4,
                                           img_rect.bottom() - 20, "\u2713", QColor("#2ecc71"))

        # Selection border
        if is_selected:
            painter.setPen(QPen(QColor("#4a9eff"), 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(QRectF(cell_rect), 4, 4)

        # Info bar (two lines: filename + details)
        info_rect = QRect(
            cell_rect.x() + self._padding,
            cell_rect.bottom() - self._info_bar_height - self._padding + 2,
            cell_rect.width() - self._padding * 2,
            self._info_bar_height
        )
        self._draw_info_bar(painter, info_rect, info)

        painter.restore()

    def _get_pixmap(self, path: str) -> QPixmap:
        if path in self._pixmap_cache:
            self._pixmap_cache.move_to_end(path)
            return self._pixmap_cache[path]
        pixmap = QPixmap(path)
        self._pixmap_cache[path] = pixmap
        while len(self._pixmap_cache) > self._cache_limit:
            self._pixmap_cache.popitem(last=False)  # LRU eviction
        return pixmap

    def _draw_play_icon(self, painter: QPainter, rect: QRect):
        cx = rect.center().x()
        cy = rect.center().y()
        radius = min(20, rect.width() // 6)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(0, 0, 0, 160))
        painter.drawEllipse(cx - radius, cy - radius, radius * 2, radius * 2)

        painter.setBrush(QColor(255, 255, 255, 220))
        s = radius * 0.6
        triangle = QPolygonF([
            QPointF(cx - s * 0.5, cy - s),
            QPointF(cx - s * 0.5, cy + s),
            QPointF(cx + s, cy)
        ])
        painter.drawPolygon(triangle)

    def _draw_badge_right(self, painter: QPainter, right_x: float, y: float,
                           text: str, color: QColor) -> float:
        """Draw badge anchored to right_x, returns new right_x for next badge"""
        font = QFont("Segoe UI", 8, QFont.Weight.Bold)
        painter.setFont(font)
        fm = QFontMetrics(font)
        text_width = fm.horizontalAdvance(text) + 10
        badge_height = 16
        badge_x = right_x - text_width

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(0, 0, 0, 180))
        badge_rect = QRectF(badge_x, y, text_width, badge_height)
        painter.drawRoundedRect(badge_rect, 8, 8)

        painter.setPen(color)
        painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, text)
        return badge_x - 3  # gap between badges

    def _draw_stars(self, painter: QPainter, img_rect: QRect, rating: int):
        """Draw star rating at bottom-left of image"""
        font = QFont("Segoe UI", 10)
        painter.setFont(font)

        # Background strip
        star_text = self.STAR_FILLED * rating
        fm = QFontMetrics(font)
        tw = fm.horizontalAdvance(star_text) + 8
        th = 18
        sx = img_rect.x() + 4
        sy = img_rect.bottom() - th - 4

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(0, 0, 0, 160))
        painter.drawRoundedRect(QRectF(sx, sy, tw, th), 4, 4)

        painter.setPen(QColor("#f1c40f"))
        painter.drawText(QRectF(sx, sy, tw, th), Qt.AlignmentFlag.AlignCenter, star_text)

    def _draw_info_bar(self, painter: QPainter, rect: QRect, info):
        if not isinstance(info, ImageInfo):
            return

        filename = os.path.basename(info.path)

        # Line 1: filename
        font1 = QFont("Segoe UI", 9)
        painter.setFont(font1)
        fm1 = QFontMetrics(font1)
        line1_rect = QRect(rect.x(), rect.y(), rect.width(), rect.height() // 2)
        elided = fm1.elidedText(filename, Qt.TextElideMode.ElideMiddle, rect.width())
        painter.setPen(QColor("#cccccc"))
        painter.drawText(line1_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, elided)

        # Line 2: details (resolution + size)
        details = []
        if info.width > 0 and info.height > 0:
            details.append(f"{info.width}x{info.height}")
        size_str = _format_size(info.file_size)
        if size_str:
            details.append(size_str)
        if info.camera_model:
            details.append(info.camera_model)

        if details:
            font2 = QFont("Segoe UI", 8)
            painter.setFont(font2)
            line2_rect = QRect(rect.x(), rect.y() + rect.height() // 2, rect.width(), rect.height() // 2)
            detail_text = " | ".join(details)
            fm2 = QFontMetrics(font2)
            elided2 = fm2.elidedText(detail_text, Qt.TextElideMode.ElideRight, rect.width())
            painter.setPen(QColor("#777777"))
            painter.drawText(line2_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, elided2)

    def clear_cache(self):
        self._pixmap_cache.clear()
