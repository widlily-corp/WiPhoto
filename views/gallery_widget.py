# views/gallery_widget.py

import os
from PyQt6.QtWidgets import (QWidget, QHBoxLayout, QSplitter, QListWidget, QLabel, QVBoxLayout,
                             QTableWidget, QAbstractItemView, QHeaderView, QMenu)
from PyQt6.QtGui import QIcon, QAction
from PyQt6.QtCore import Qt, QSize, pyqtSignal

from models.image_model import ImageInfo
from utils import resource_path,apply_shadow_effect


class GalleryWidget(QWidget):
    # Сигналы, которые этот виджет будет отправлять контроллеру
    edit_requested = pyqtSignal(ImageInfo)

    def __init__(self, parent=None):
        super().__init__(parent)

        # --- Основная структура виджета ---
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(splitter)



        # --- Создаем и добавляем компоненты ---
        self.thumbnail_view = self._create_thumbnail_view()
        self.right_panel = self._create_right_panel()  # Панель превью теперь часть галереи

        apply_shadow_effect(self.right_panel)

        splitter.addWidget(self.thumbnail_view)
        splitter.addWidget(self.right_panel)
        splitter.setSizes([950, 400])

        self._create_actions()

    def _create_thumbnail_view(self) -> QListWidget:
        list_widget = QListWidget()
        list_widget.setViewMode(QListWidget.ViewMode.IconMode)
        list_widget.setIconSize(QSize(256, 256))
        list_widget.setResizeMode(QListWidget.ResizeMode.Adjust)
        list_widget.setMovement(QListWidget.Movement.Static)
        list_widget.setSpacing(10)
        list_widget.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        list_widget.customContextMenuRequested.connect(self._show_context_menu)

        return list_widget

    def _create_right_panel(self) -> QWidget:
        right_panel_widget = QWidget()
        # Устанавливаем прозрачный фон для правой панели
        right_panel_widget.setStyleSheet("QWidget { background-color: transparent; }")
        layout = QVBoxLayout(right_panel_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        splitter = QSplitter(Qt.Orientation.Vertical)

        self.preview_area = QLabel("Выберите изображение для предпросмотра")
        self.preview_area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_area.setMinimumHeight(200)
        # Устанавливаем фон для области предпросмотра


        self.metadata_view = QTableWidget()
        self.metadata_view.setColumnCount(2)
        self.metadata_view.setHorizontalHeaderLabels(["Параметр", "Значение"])
        self.metadata_view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.metadata_view.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.metadata_view.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.metadata_view.setMinimumHeight(150)
        # Устанавливаем фон для таблицы метаданных


        splitter.addWidget(self.preview_area)
        splitter.addWidget(self.metadata_view)
        splitter.setSizes([600, 300])
        layout.addWidget(splitter)
        right_panel_widget.setMinimumWidth(300)
        return right_panel_widget

    def _create_actions(self):
        """Создает действия для контекстного меню."""
        self.edit_action = QAction(QIcon(resource_path("assets/edit.png")), "Редактировать", self)
        self.edit_action.triggered.connect(self._on_edit_triggered)
        # Другие действия для меню создаются в MainWindow и передаются сюда при необходимости

    def _show_context_menu(self, position):
        selected_items = self.thumbnail_view.selectedItems()
        if not selected_items:
            return

        menu = QMenu()

        # Действие "Редактировать" активно только для одного выбранного элемента
        if len(selected_items) == 1:
            menu.addAction(self.edit_action)
            menu.addSeparator()

        # Получаем действия (Копировать, Вставить и т.д.) из главного окна
        main_window = self.window()
        menu.addAction(main_window.copy_action)
        menu.addAction(main_window.move_action)
        menu.addSeparator()

        if len(selected_items) == 1:
            info = selected_items[0].data(Qt.ItemDataRole.UserRole)
            if info.is_best_in_group:
                menu.addAction(main_window.keep_best_action)
                menu.addSeparator()

        menu.addAction(main_window.delete_action)
        menu.exec(self.thumbnail_view.mapToGlobal(position))

    def _on_edit_triggered(self):
        selected = self.thumbnail_view.selectedItems()
        if len(selected) == 1:
            info = selected[0].data(Qt.ItemDataRole.UserRole)
            self.edit_requested.emit(info)

    def _get_selected_image_infos(self) -> list[ImageInfo]:
        """Вспомогательный метод для получения объектов ImageInfo из выбранных элементов."""
        return [item.data(Qt.ItemDataRole.UserRole) for item in self.thumbnail_view.selectedItems()]