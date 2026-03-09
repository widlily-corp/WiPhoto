# views/timeline_widget.py

import os
import logging
from datetime import datetime
from collections import defaultdict

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QScrollArea, QLabel,
                             QHBoxLayout, QFrame, QSizePolicy, QLayout)
from PyQt6.QtCore import Qt, QSize, QRect, QPoint, pyqtSignal
from PyQt6.QtGui import QPixmap, QFont, QColor, QPainter, QPen

from models.image_model import ImageInfo


class FlowLayout(QLayout):
    """Flow layout that wraps widgets to the next row when they exceed width"""

    def __init__(self, parent=None, spacing=4):
        super().__init__(parent)
        self._items = []
        self._spacing = spacing

    def addItem(self, item):
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, index):
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index):
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._do_layout(QRect(0, 0, width, 0), test_only=True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._do_layout(rect, test_only=False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        return size

    def _do_layout(self, rect, test_only):
        x = rect.x()
        y = rect.y()
        row_height = 0

        for item in self._items:
            item_size = item.sizeHint()
            next_x = x + item_size.width() + self._spacing

            if next_x - self._spacing > rect.right() and row_height > 0:
                x = rect.x()
                y = y + row_height + self._spacing
                next_x = x + item_size.width() + self._spacing
                row_height = 0

            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), item_size))

            x = next_x
            row_height = max(row_height, item_size.height())

        return y + row_height - rect.y()


class TimelineThumbnail(QLabel):
    """Clickable thumbnail for timeline"""
    clicked = pyqtSignal(ImageInfo)

    def __init__(self, info: ImageInfo, size: int = 120, parent=None):
        super().__init__(parent)
        self.info = info
        self.setFixedSize(size, size)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet("""
            QLabel {
                border: 2px solid transparent;
                border-radius: 4px;
                background: #252526;
            }
            QLabel:hover {
                border-color: #4a9eff;
            }
        """)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setToolTip(os.path.basename(info.path))
        self._load_thumbnail(size)

    def _load_thumbnail(self, size):
        path = self.info.thumbnail_path or self.info.path
        if path and os.path.exists(path):
            pixmap = QPixmap(path)
            if not pixmap.isNull():
                self.setPixmap(pixmap.scaled(
                    size - 4, size - 4,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                ))
                return
        self.setText(os.path.basename(self.info.path)[:10])

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.info)


class DateGroup(QWidget):
    """A group of thumbnails under a date header"""
    image_clicked = pyqtSignal(ImageInfo)

    def __init__(self, date_str: str, images: list, thumb_size: int = 120, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 8)
        layout.setSpacing(4)

        # Date header
        header = QLabel(date_str)
        header.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        header.setStyleSheet("color: #cccccc; padding: 8px 4px 4px 4px;")
        layout.addWidget(header)

        # Count label
        count_label = QLabel(f"{len(images)} фото")
        count_label.setStyleSheet("color: #808080; font-size: 11px; padding-left: 4px;")
        layout.addWidget(count_label)

        # Flow layout for thumbnails (wraps to next row)
        flow = QWidget()
        flow_layout = FlowLayout(flow, spacing=4)

        for info in images:
            thumb = TimelineThumbnail(info, thumb_size)
            thumb.clicked.connect(self.image_clicked.emit)
            flow_layout.addWidget(thumb)

        flow.setLayout(flow_layout)
        layout.addWidget(flow)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #3c3c3c;")
        layout.addWidget(sep)


class TimelineWidget(QWidget):
    """Timeline/Calendar view — photos organized by date"""
    image_selected = pyqtSignal(ImageInfo)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._images = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Scrollable area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setStyleSheet("QScrollArea { border: none; background: #1e1e1e; }")

        self.container = QWidget()
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setContentsMargins(12, 8, 12, 8)
        self.container_layout.setSpacing(0)
        self.container_layout.addStretch()

        self.scroll_area.setWidget(self.container)
        layout.addWidget(self.scroll_area)

    def set_images(self, images: list):
        self._images = images
        self._rebuild()

    def _rebuild(self):
        # Clear existing
        while self.container_layout.count() > 0:
            item = self.container_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not self._images:
            empty = QLabel("Нет фотографий")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setStyleSheet("color: #808080; font-size: 16px; padding: 40px;")
            self.container_layout.addWidget(empty)
            self.container_layout.addStretch()
            return

        # Group by date
        groups = defaultdict(list)
        for info in self._images:
            date_key = self._get_date_key(info)
            groups[date_key].append(info)

        # Sort dates descending (newest first)
        sorted_dates = sorted(groups.keys(), reverse=True)

        MONTH_NAMES = {
            1: "Январь", 2: "Февраль", 3: "Март", 4: "Апрель",
            5: "Май", 6: "Июнь", 7: "Июль", 8: "Август",
            9: "Сентябрь", 10: "Октябрь", 11: "Ноябрь", 12: "Декабрь"
        }
        WEEKDAYS = {
            0: "Понедельник", 1: "Вторник", 2: "Среда", 3: "Четверг",
            4: "Пятница", 5: "Суббота", 6: "Воскресенье"
        }

        for date_key in sorted_dates:
            images = groups[date_key]
            try:
                dt = datetime.strptime(date_key, "%Y-%m-%d")
                weekday = WEEKDAYS.get(dt.weekday(), "")
                month = MONTH_NAMES.get(dt.month, "")
                date_str = f"{weekday}, {dt.day} {month} {dt.year}"
            except ValueError:
                date_str = date_key

            group = DateGroup(date_str, images)
            group.image_clicked.connect(self.image_selected.emit)
            self.container_layout.addWidget(group)

        self.container_layout.addStretch()

    def _get_date_key(self, info: ImageInfo) -> str:
        """Get date string for grouping"""
        if info.date_taken:
            try:
                dt = datetime.strptime(info.date_taken, "%Y:%m:%d %H:%M:%S")
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                pass
        # Fallback to file modification time
        try:
            mtime = os.path.getmtime(info.path)
            return datetime.fromtimestamp(mtime).strftime("%Y-%m-%d")
        except Exception:
            return "Неизвестная дата"
