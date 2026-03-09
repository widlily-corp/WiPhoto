# views/gallery_widget.py

import os
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QListWidget, QAbstractItemView, QMenu)
from PyQt6.QtGui import QIcon, QAction, QWheelEvent, QKeyEvent
from PyQt6.QtCore import Qt, QSize, pyqtSignal

from models.image_model import ImageInfo
from views.thumbnail_delegate import ThumbnailDelegate
from utils import resource_path


class ThumbnailListWidget(QListWidget):
    """QListWidget with Ctrl+Wheel zoom, ThumbnailDelegate, and rating keys"""

    zoom_changed = pyqtSignal(int)
    rating_changed = pyqtSignal(object, int)  # ImageInfo, rating
    color_label_changed = pyqtSignal(object, str)  # ImageInfo, color
    flag_changed = pyqtSignal(object, str)  # ImageInfo, flag_status

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cell_size = 200
        self._min_size = 100
        self._max_size = 400
        self._step = 20

        self.delegate = ThumbnailDelegate(self)
        self.delegate.set_cell_size(self._cell_size)
        self.setItemDelegate(self.delegate)

        self.setViewMode(QListWidget.ViewMode.IconMode)
        self.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.setMovement(QListWidget.Movement.Static)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setUniformItemSizes(True)
        self.setSpacing(4)

        self._apply_size()

    def set_cell_size(self, size: int):
        self._cell_size = max(self._min_size, min(self._max_size, size))
        self.delegate.set_cell_size(self._cell_size)
        self._apply_size()
        self.delegate.clear_cache()
        self.viewport().update()

    def _apply_size(self):
        total = self._cell_size + 40 + 8  # cell + info bar (36) + padding
        self.setIconSize(QSize(self._cell_size, self._cell_size))
        self.setGridSize(QSize(total, total))

    def keyPressEvent(self, event: QKeyEvent):
        """Handle rating keys (0-5) and color label keys (6-9)"""
        key = event.key()
        # Rating: 0-5
        if Qt.Key.Key_0 <= key <= Qt.Key.Key_5:
            rating = key - Qt.Key.Key_0
            for item in self.selectedItems():
                info = item.data(Qt.ItemDataRole.UserRole)
                if isinstance(info, ImageInfo):
                    info.rating = rating
                    self.rating_changed.emit(info, rating)
            self.viewport().update()
            return
        # Color labels: 6=red, 7=yellow, 8=green, 9=blue
        color_map = {Qt.Key.Key_6: "red", Qt.Key.Key_7: "yellow",
                     Qt.Key.Key_8: "green", Qt.Key.Key_9: "blue"}
        if key in color_map:
            color = color_map[key]
            for item in self.selectedItems():
                info = item.data(Qt.ItemDataRole.UserRole)
                if isinstance(info, ImageInfo):
                    info.color_label = "" if info.color_label == color else color
                    self.color_label_changed.emit(info, info.color_label)
            self.viewport().update()
            return
        # Flag/Reject: P=pick, X=reject, U=unflag
        flag_map = {Qt.Key.Key_P: "picked", Qt.Key.Key_X: "rejected", Qt.Key.Key_U: ""}
        if key in flag_map:
            status = flag_map[key]
            for item in self.selectedItems():
                info = item.data(Qt.ItemDataRole.UserRole)
                if isinstance(info, ImageInfo):
                    info.flag_status = status
                    self.flag_changed.emit(info, status)
            self.viewport().update()
            # Auto-advance to next after flag
            current = self.currentRow()
            if current < self.count() - 1:
                self.setCurrentRow(current + 1)
            return
        super().keyPressEvent(event)

    def wheelEvent(self, event: QWheelEvent):
        if event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            delta = event.angleDelta().y()
            if delta > 0:
                self._cell_size = min(self._max_size, self._cell_size + self._step)
            elif delta < 0:
                self._cell_size = max(self._min_size, self._cell_size - self._step)
            self.delegate.set_cell_size(self._cell_size)
            self._apply_size()
            self.delegate.clear_cache()
            self.viewport().update()
            self.zoom_changed.emit(self._cell_size)
            event.accept()
        else:
            super().wheelEvent(event)


class GalleryWidget(QWidget):
    """Gallery grid widget — just the thumbnail grid, no right panel"""

    edit_requested = pyqtSignal(ImageInfo)

    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.thumbnail_view = ThumbnailListWidget()
        self.thumbnail_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.thumbnail_view.customContextMenuRequested.connect(self._show_context_menu)

        layout.addWidget(self.thumbnail_view)

        self._create_actions()

    def _create_actions(self):
        self.edit_action = QAction(QIcon(resource_path("assets/edit.png")), "Редактировать", self)
        self.edit_action.triggered.connect(self._on_edit_triggered)

    def _show_context_menu(self, position):
        selected_items = self.thumbnail_view.selectedItems()
        if not selected_items:
            return

        menu = QMenu()

        if len(selected_items) == 1:
            menu.addAction(self.edit_action)
            menu.addSeparator()

        main_window = self.window()
        if hasattr(main_window, 'copy_action'):
            menu.addAction(main_window.copy_action)
            menu.addAction(main_window.move_action)
            menu.addSeparator()

            if len(selected_items) == 1:
                info = selected_items[0].data(Qt.ItemDataRole.UserRole)
                if isinstance(info, ImageInfo) and info.is_best_in_group:
                    menu.addAction(main_window.keep_best_action)
                    menu.addSeparator()

            menu.addAction(main_window.delete_action)

        # Rating submenu
        menu.addSeparator()
        rating_menu = menu.addMenu("Рейтинг")
        for r in range(6):
            label = "\u2605" * r if r > 0 else "Без рейтинга"
            action = rating_menu.addAction(f"{label}  ({r})")
            action.triggered.connect(lambda checked, rating=r: self._set_rating(rating))

        # Color label submenu
        color_menu = menu.addMenu("Цветная метка")
        colors = [("Красная", "red"), ("Желтая", "yellow"),
                  ("Зеленая", "green"), ("Синяя", "blue"), ("Без метки", "")]
        for label, color in colors:
            action = color_menu.addAction(label)
            action.triggered.connect(lambda checked, c=color: self._set_color_label(c))

        # Flag submenu
        flag_menu = menu.addMenu("Флаг")
        for label, status in [("\u2713 Выбрано (P)", "picked"), ("\u2717 Отклонено (X)", "rejected"), ("Без флага (U)", "")]:
            action = flag_menu.addAction(label)
            action.triggered.connect(lambda checked, s=status: self._set_flag(s))

        # Find similar (single selection)
        if len(selected_items) == 1:
            menu.addSeparator()
            find_similar_action = menu.addAction("Найти похожие")
            find_similar_action.triggered.connect(self._on_find_similar)

        menu.exec(self.thumbnail_view.mapToGlobal(position))

    def _set_rating(self, rating: int):
        for item in self.thumbnail_view.selectedItems():
            info = item.data(Qt.ItemDataRole.UserRole)
            if isinstance(info, ImageInfo):
                info.rating = rating
        self.thumbnail_view.viewport().update()

    def _set_color_label(self, color: str):
        for item in self.thumbnail_view.selectedItems():
            info = item.data(Qt.ItemDataRole.UserRole)
            if isinstance(info, ImageInfo):
                info.color_label = color
        self.thumbnail_view.viewport().update()

    find_similar_requested = pyqtSignal(ImageInfo)

    def _set_flag(self, status: str):
        for item in self.thumbnail_view.selectedItems():
            info = item.data(Qt.ItemDataRole.UserRole)
            if isinstance(info, ImageInfo):
                info.flag_status = status
        self.thumbnail_view.viewport().update()

    def _on_find_similar(self):
        selected = self.thumbnail_view.selectedItems()
        if len(selected) == 1:
            info = selected[0].data(Qt.ItemDataRole.UserRole)
            if isinstance(info, ImageInfo):
                self.find_similar_requested.emit(info)

    def _on_edit_triggered(self):
        selected = self.thumbnail_view.selectedItems()
        if len(selected) == 1:
            info = selected[0].data(Qt.ItemDataRole.UserRole)
            if isinstance(info, ImageInfo):
                self.edit_requested.emit(info)

    def _get_selected_image_infos(self) -> list[ImageInfo]:
        return [item.data(Qt.ItemDataRole.UserRole)
                for item in self.thumbnail_view.selectedItems()
                if isinstance(item.data(Qt.ItemDataRole.UserRole), ImageInfo)]

    def set_thumbnail_size(self, size: int):
        self.thumbnail_view.set_cell_size(size)
