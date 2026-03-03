# views/smart_collections_widget.py - ФИНАЛЬНАЯ ВЕРСИЯ

import logging
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QListWidget,
                             QPushButton, QLabel, QListWidgetItem, QAbstractItemView,
                             QMenu, QMessageBox)
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QIcon, QPixmap
from models.image_model import ImageInfo
from utils import resource_path
from datetime import datetime
import os
import subprocess
import platform


class SmartCollectionsWidget(QWidget):
    """Умные коллекции - автоматическая группировка по критериям"""

    collection_changed = pyqtSignal(str)
    image_selected = pyqtSignal(ImageInfo)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.all_images = []
        self._init_ui()

    def _init_ui(self):
        layout = QHBoxLayout(self)

        # Левая панель - список коллекций
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_panel.setMaximumWidth(250)

        title = QLabel("Умные коллекции")
        title.setStyleSheet("font-size: 16px; font-weight: bold; padding: 10px;")
        left_layout.addWidget(title)

        self.collections_list = QListWidget()
        self.collections_list.itemClicked.connect(self._on_collection_selected)
        self.collections_list.setStyleSheet("""
            QListWidget {
                background-color: #23283a;
                border-radius: 8px;
            }
            QListWidget::item {
                padding: 8px;
                border-radius: 4px;
                margin: 2px;
            }
            QListWidget::item:selected {
                background-color: #0078d4;
                color: white;
            }
            QListWidget::item:hover {
                background-color: rgba(255, 255, 255, 0.1);
            }
        """)
        left_layout.addWidget(self.collections_list)

        # Добавляем стандартные коллекции
        self._add_standard_collections()

        # Правая панель - превью изображений
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)

        self.collection_title = QLabel("Выберите коллекцию")
        self.collection_title.setStyleSheet("font-size: 14px; font-weight: bold; padding: 10px;")
        right_layout.addWidget(self.collection_title)

        self.images_grid = QListWidget()
        self.images_grid.setViewMode(QListWidget.ViewMode.IconMode)
        self.images_grid.setIconSize(QSize(200, 200))
        self.images_grid.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.images_grid.setSpacing(10)
        self.images_grid.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.images_grid.setMovement(QListWidget.Movement.Static)
        # Устанавливаем фон для сетки изображений
        self.images_grid.setStyleSheet("QListWidget { background-color: #23283a; border-radius: 8px; }")

        # Подключаем обработчики
        self.images_grid.itemDoubleClicked.connect(self._on_image_double_clicked)
        self.images_grid.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.images_grid.customContextMenuRequested.connect(self._show_context_menu)

        right_layout.addWidget(self.images_grid)

        # Статистика
        self.stats_label = QLabel("")
        self.stats_label.setStyleSheet("padding: 10px; color: #888;")
        right_layout.addWidget(self.stats_label)

        # Добавляем панели
        layout.addWidget(left_panel)
        layout.addWidget(right_panel)

    def _add_standard_collections(self):
        """Добавляет стандартные умные коллекции"""
        collections = [
            ("📅 Сегодня", "today"),
            ("📅 Эта неделя", "this_week"),
            ("📅 Этот месяц", "this_month"),
            ("📅 Этот год", "this_year"),
            ("⭐ Лучшие", "best_quality"),
            ("🎯 Высокая резкость", "sharp"),
            ("🎨 RAW файлы", "raw_files"),
            ("📸 По камере", "by_camera"),
            ("🔍 Все дубликаты", "all_duplicates"),
            ("✨ Уникальные", "unique"),
            ("😊 С лицами", "with_faces"),
            ("🐾 С животными", "with_animals"),
            ("🌍 С геотегами", "with_geotags"),
        ]

        for name, collection_id in collections:
            item = QListWidgetItem(name)
            item.setData(Qt.ItemDataRole.UserRole, collection_id)
            self.collections_list.addItem(item)

    def set_images(self, images: list[ImageInfo]):
        """Устанавливает список изображений для фильтрации"""
        self.all_images = images
        if self.collections_list.count() > 0:
            self.collections_list.setCurrentRow(0)
            self._on_collection_selected(self.collections_list.item(0))

    def _on_collection_selected(self, item):
        """Обработка выбора коллекции"""
        if not item:
            return

        collection_id = item.data(Qt.ItemDataRole.UserRole)
        collection_name = item.text()

        self.collection_title.setText(f"📂 {collection_name}")
        self.collection_changed.emit(collection_id)

        filtered = self._filter_by_collection(collection_id)
        self._display_images(filtered)
        self.stats_label.setText(f"Найдено изображений: {len(filtered)}")

    def _filter_by_collection(self, collection_id: str) -> list[ImageInfo]:
        """Фильтрует изображения по ID коллекции"""
        now = datetime.now()

        if collection_id == "today":
            return self._filter_by_date(lambda d: d.date() == now.date())
        elif collection_id == "this_week":
            return self._filter_by_date(lambda d: d.isocalendar()[1] == now.isocalendar()[1])
        elif collection_id == "this_month":
            return self._filter_by_date(lambda d: d.month == now.month and d.year == now.year)
        elif collection_id == "this_year":
            return self._filter_by_date(lambda d: d.year == now.year)
        elif collection_id == "best_quality":
            return [img for img in self.all_images if img.is_best_in_group]
        elif collection_id == "sharp":
            if not self.all_images:
                return []
            sorted_imgs = sorted(self.all_images, key=lambda x: x.sharpness, reverse=True)
            threshold_idx = max(1, len(sorted_imgs) // 5)
            return sorted_imgs[:threshold_idx]
        elif collection_id == "raw_files":
            raw_exts = ('.arw', '.cr2', '.nef', '.dng', '.raw')
            return [img for img in self.all_images if img.path.lower().endswith(raw_exts)]
        elif collection_id == "by_camera":
            return self.all_images
        elif collection_id == "all_duplicates":
            return [img for img in self.all_images if img.group_id is not None]
        elif collection_id == "unique":
            return [img for img in self.all_images if img.group_id is None]
        elif collection_id == "with_faces":
            return [img for img in self.all_images if img.faces_count > 0]
        elif collection_id == "with_animals":
            return [img for img in self.all_images if img.animals_count > 0]
        elif collection_id == "with_geotags":
            return [img for img in self.all_images if img.gps_location is not None]

        return []

    def _filter_by_date(self, date_condition) -> list[ImageInfo]:
        """Фильтрует по дате модификации файла"""
        result = []
        for img in self.all_images:
            try:
                mtime = os.path.getmtime(img.path)
                file_date = datetime.fromtimestamp(mtime)
                if date_condition(file_date):
                    result.append(img)
            except Exception as e:
                logging.error(f"Ошибка фильтрации по дате для {img.path}: {e}")
        return result

    def _display_images(self, images: list[ImageInfo]):
        """Отображает изображения в сетке"""
        self.images_grid.clear()

        for info in images:
            if info.thumbnail_path and os.path.exists(info.thumbnail_path):
                try:
                    pixmap = QPixmap(info.thumbnail_path)
                    if not pixmap.isNull():
                        icon = QIcon(pixmap)
                        item = QListWidgetItem(icon, os.path.basename(info.path))
                        item.setData(Qt.ItemDataRole.UserRole, info)
                        item.setSizeHint(QSize(220, 220))
                        self.images_grid.addItem(item)
                except Exception as e:
                    logging.error(f"Ошибка загрузки изображения в коллекцию: {e}")

    def _on_image_double_clicked(self, item: QListWidgetItem):
        """Обработка двойного клика по изображению"""
        info = item.data(Qt.ItemDataRole.UserRole)
        if isinstance(info, ImageInfo):
            self.image_selected.emit(info)

    def _show_context_menu(self, position):
        """Показывает контекстное меню для изображений"""
        item = self.images_grid.itemAt(position)
        if not item:
            return

        menu = QMenu(self)

        open_action = menu.addAction("📂 Открыть в проводнике")
        edit_action = menu.addAction("✏️ Редактировать")
        menu.addSeparator()
        delete_action = menu.addAction("🗑️ Удалить")

        action = menu.exec(self.images_grid.mapToGlobal(position))

        if action == open_action:
            self._open_in_explorer(item)
        elif action == edit_action:
            self._on_image_double_clicked(item)
        elif action == delete_action:
            self._delete_image(item)

    def _open_in_explorer(self, item: QListWidgetItem):
        """Открывает файл в проводнике"""
        info = item.data(Qt.ItemDataRole.UserRole)
        if isinstance(info, ImageInfo):
            if platform.system() == "Windows":
                subprocess.run(['explorer', '/select,', os.path.normpath(info.path)])
            elif platform.system() == "Darwin":
                subprocess.run(['open', '-R', info.path])
            else:
                subprocess.run(['xdg-open', os.path.dirname(info.path)])

    def _delete_image(self, item: QListWidgetItem):
        """Удаляет изображение"""
        info = item.data(Qt.ItemDataRole.UserRole)
        if isinstance(info, ImageInfo):
            reply = QMessageBox.question(
                self,
                "Подтверждение",
                f"Удалить файл {os.path.basename(info.path)}?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )

            if reply == QMessageBox.StandardButton.Yes:
                try:
                    os.remove(info.path)
                    self.images_grid.takeItem(self.images_grid.row(item))
                    self.all_images.remove(info)
                    QMessageBox.information(self, "Успех", "Файл удален")
                except Exception as e:
                    QMessageBox.critical(self, "Ошибка", f"Не удалось удалить:\n{e}")