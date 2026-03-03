# views/gallery_widget.py

import os
from PyQt6.QtWidgets import (QWidget, QHBoxLayout, QSplitter, QListWidget, QLabel, QVBoxLayout,
                             QTableWidget, QAbstractItemView, QHeaderView, QMenu)
from PyQt6.QtGui import QIcon, QAction, QWheelEvent
from PyQt6.QtCore import Qt, QSize, pyqtSignal

from models.image_model import ImageInfo
from utils import resource_path,apply_shadow_effect


class ThumbnailListWidget(QListWidget):
    """Custom QListWidget with mouse wheel zoom support"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.icon_sizes = [128, 160, 200, 256, 320, 400, 512]
        self.current_size_index = 4  # 320 по умолчанию

    def wheelEvent(self, event: QWheelEvent):
        """Handle mouse wheel to resize thumbnails"""
        if event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            delta = event.angleDelta().y()
            if delta > 0 and self.current_size_index < len(self.icon_sizes) - 1:
                self.current_size_index += 1
            elif delta < 0 and self.current_size_index > 0:
                self.current_size_index -= 1

            new_size = self.icon_sizes[self.current_size_index]
            self.setIconSize(QSize(new_size, new_size))
            event.accept()
        else:
            super().wheelEvent(event)


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
        splitter.setSizes([900, 450])  # Больше места для правой панели с превью

        self._create_actions()

    def _create_thumbnail_view(self) -> ThumbnailListWidget:
        list_widget = ThumbnailListWidget()
        list_widget.setViewMode(QListWidget.ViewMode.IconMode)
        list_widget.setIconSize(QSize(320, 320))  # Увеличенный размер превью
        list_widget.setResizeMode(QListWidget.ResizeMode.Adjust)
        list_widget.setMovement(QListWidget.Movement.Static)
        list_widget.setSpacing(15)  # Больше пространства между элементами
        list_widget.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        list_widget.customContextMenuRequested.connect(self._show_context_menu)
        # Современный стиль с скругленными углами
        list_widget.setStyleSheet("""
            QListWidget {
                background-color: rgba(13, 17, 23, 0.5);
                border: 1px solid rgba(48, 54, 61, 0.3);
                border-radius: 12px;
                padding: 10px;
            }
            QListWidget::item {
                border-radius: 10px;
                padding: 5px;
            }
            QListWidget::item:selected {
                background-color: rgba(88, 166, 255, 0.2);
                border: 2px solid rgba(88, 166, 255, 0.5);
            }
            QListWidget::item:hover:!selected {
                background-color: rgba(56, 139, 253, 0.1);
            }
        """)

        return list_widget

    def _create_right_panel(self) -> QWidget:
        right_panel_widget = QWidget()
        # Устанавливаем прозрачный фон для правой панели
        right_panel_widget.setStyleSheet("QWidget { background-color: transparent; }")
        layout = QVBoxLayout(right_panel_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        splitter = QSplitter(Qt.Orientation.Vertical)

        # Большая область предпросмотра с современным стилем
        self.preview_area = QLabel("Выберите изображение для предпросмотра")
        self.preview_area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_area.setMinimumHeight(400)  # Увеличенная высота
        self.preview_area.setStyleSheet("""
            QLabel {
                background-color: rgba(22, 27, 34, 0.6);
                border: 1px solid rgba(48, 54, 61, 0.5);
                border-radius: 12px;
                color: #8b949e;
                font-size: 14px;
                padding: 20px;
            }
        """)

        # Компактная панель метаданных
        self.metadata_view = QTableWidget()
        self.metadata_view.setColumnCount(2)
        self.metadata_view.setHorizontalHeaderLabels(["Параметр", "Значение"])
        self.metadata_view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.metadata_view.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.metadata_view.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.metadata_view.setMinimumHeight(200)  # Компактная высота
        self.metadata_view.setStyleSheet("""
            QTableWidget {
                background-color: rgba(22, 27, 34, 0.6);
                border: 1px solid rgba(48, 54, 61, 0.5);
                border-radius: 12px;
                gridline-color: rgba(48, 54, 61, 0.3);
            }
            QTableWidget::item {
                padding: 6px;
                border-radius: 4px;
            }
            QHeaderView::section {
                background-color: rgba(13, 17, 23, 0.8);
                padding: 8px;
                border: none;
                border-bottom: 2px solid rgba(88, 166, 255, 0.3);
                font-weight: 600;
                color: #58a6ff;
            }
        """)

        splitter.addWidget(self.preview_area)
        splitter.addWidget(self.metadata_view)
        splitter.setSizes([700, 250])  # Больше места для превью
        layout.addWidget(splitter)
        right_panel_widget.setMinimumWidth(350)  # Немного шире
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