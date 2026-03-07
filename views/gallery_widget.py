# views/gallery_widget.py

import os
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QListWidget, QAbstractItemView, QMenu)
from PyQt6.QtGui import QIcon, QAction, QWheelEvent
from PyQt6.QtCore import Qt, QSize, pyqtSignal

from models.image_model import ImageInfo
from views.thumbnail_delegate import ThumbnailDelegate
from utils import resource_path


class ThumbnailListWidget(QListWidget):
    """QListWidget with Ctrl+Wheel zoom and ThumbnailDelegate"""

    zoom_changed = pyqtSignal(int)

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
        total = self._cell_size + 28 + 8  # cell + info bar + padding
        self.setIconSize(QSize(self._cell_size, self._cell_size))
        self.setGridSize(QSize(total, total))

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

        menu.exec(self.thumbnail_view.mapToGlobal(position))

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
