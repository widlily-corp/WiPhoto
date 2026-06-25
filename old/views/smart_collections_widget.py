# views/smart_collections_widget.py

import logging
import os
from datetime import datetime

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QListWidget, QListWidgetItem, QLabel, QPushButton, QHBoxLayout
from PyQt6.QtCore import Qt, pyqtSignal

from models.image_model import ImageInfo, RAW_EXTENSIONS


class SmartCollectionsWidget(QWidget):
    """Sidebar widget: list of smart collections that filter the main gallery"""

    collection_selected = pyqtSignal(list)  # emits filtered list of ImageInfo
    collection_changed = pyqtSignal(str)    # emits collection_id
    delete_all_from_trash_requested = pyqtSignal()  # delete all trash items
    restore_all_from_trash_requested = pyqtSignal()  # restore all trash items

    def __init__(self, parent=None):
        super().__init__(parent)
        self.all_images = []
        self._current_collection = None
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        title = QLabel("КОЛЛЕКЦИИ")
        title.setStyleSheet("""
            color: #999999;
            font-size: 11px;
            font-weight: bold;
            padding: 8px 8px 4px 8px;
        """)
        layout.addWidget(title)

        self.collections_list = QListWidget()
        self.collections_list.itemClicked.connect(self._on_collection_clicked)
        layout.addWidget(self.collections_list)

        # Trash management buttons (hidden by default)
        self.trash_buttons_widget = QWidget()
        self.trash_buttons_widget.setVisible(False)
        trash_layout = QHBoxLayout(self.trash_buttons_widget)
        trash_layout.setContentsMargins(8, 4, 8, 8)
        trash_layout.setSpacing(4)

        self.delete_all_btn = QPushButton("Очистить всё")
        self.delete_all_btn.setStyleSheet("""
            QPushButton {
                background-color: #ff4444;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #ff6666;
            }
        """)
        self.delete_all_btn.clicked.connect(lambda: self.delete_all_from_trash_requested.emit())

        self.restore_all_btn = QPushButton("Восстановить всё")
        self.restore_all_btn.setStyleSheet("""
            QPushButton {
                background-color: #44aa44;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #66cc66;
            }
        """)
        self.restore_all_btn.clicked.connect(lambda: self.restore_all_from_trash_requested.emit())

        trash_layout.addWidget(self.restore_all_btn)
        trash_layout.addWidget(self.delete_all_btn)
        layout.addWidget(self.trash_buttons_widget)

        self._add_standard_collections()

    def _add_standard_collections(self):
        collections = [
            ("\U0001f4c2 Все файлы", "all"),
            ("\U0001f4c5 Сегодня", "today"),
            ("\U0001f5d3 Эта неделя", "this_week"),
            ("\U0001f4c6 Этот месяц", "this_month"),
            ("\u2b50 Лучшие", "best_quality"),
            ("\U0001f50d Высокая резкость", "sharp"),
            ("\U0001f4f7 RAW файлы", "raw_files"),
            ("\U0001f4f8 По камере", "by_camera"),
            ("\U0001f501 Дубликаты", "all_duplicates"),
            ("\u2728 Уникальные", "unique"),
            ("\U0001f464 С лицами", "with_faces"),
            ("\U0001f43e С животными", "with_animals"),
            ("\U0001f431 Коты", "cats"),
            ("\U0001f436 Собаки", "dogs"),
            ("\U0001f426 Птицы", "birds"),
            ("\U0001f4cd С геотегами", "with_geotags"),
            ("\u2b50 По рейтингу (4+)", "rated_high"),
            ("\U0001f3ac Видео", "videos"),
            ("\U0001f5d1 Корзина", "trash"),
        ]

        for name, collection_id in collections:
            item = QListWidgetItem(name)
            item.setData(Qt.ItemDataRole.UserRole, collection_id)
            self.collections_list.addItem(item)

    def set_images(self, images: list):
        self.all_images = images

    def _on_collection_clicked(self, item):
        if not item:
            return

        collection_id = item.data(Qt.ItemDataRole.UserRole)
        self._current_collection = collection_id
        self.collection_changed.emit(collection_id)

        filtered = self._filter_by_collection(collection_id)
        self.collection_selected.emit(filtered)

        # Show/hide trash buttons
        self.trash_buttons_widget.setVisible(collection_id == "trash")

    def _filter_by_collection(self, collection_id: str) -> list:
        if collection_id == "all":
            return list(self.all_images)

        now = datetime.now()

        if collection_id == "today":
            return self._filter_by_date(lambda d: d.date() == now.date())
        elif collection_id == "this_week":
            return self._filter_by_date(lambda d: d.isocalendar()[1] == now.isocalendar()[1] and d.year == now.year)
        elif collection_id == "this_month":
            return self._filter_by_date(lambda d: d.month == now.month and d.year == now.year)
        elif collection_id == "best_quality":
            return [img for img in self.all_images if img.is_best_in_group]
        elif collection_id == "sharp":
            if not self.all_images:
                return []
            sorted_imgs = sorted(self.all_images, key=lambda x: x.sharpness, reverse=True)
            threshold_idx = max(1, len(sorted_imgs) // 5)
            return sorted_imgs[:threshold_idx]
        elif collection_id == "raw_files":
            return [img for img in self.all_images if img.path.lower().endswith(RAW_EXTENSIONS)]
        elif collection_id == "by_camera":
            return [img for img in self.all_images if img.camera_model]
        elif collection_id == "all_duplicates":
            return [img for img in self.all_images if img.group_id is not None]
        elif collection_id == "unique":
            return [img for img in self.all_images if img.group_id is None]
        elif collection_id == "with_faces":
            return [img for img in self.all_images if img.faces_count > 0]
        elif collection_id == "with_animals":
            return [img for img in self.all_images if img.animals_count > 0]
        elif collection_id == "cats":
            return [img for img in self.all_images if 'cat' in img.animal_species]
        elif collection_id == "dogs":
            return [img for img in self.all_images if 'dog' in img.animal_species]
        elif collection_id == "birds":
            return [img for img in self.all_images if 'bird' in img.animal_species]
        elif collection_id == "with_geotags":
            return [img for img in self.all_images if img.gps_location is not None]
        elif collection_id == "rated_high":
            return [img for img in self.all_images if img.rating >= 4]
        elif collection_id == "videos":
            return [img for img in self.all_images if img.is_video()]
        elif collection_id == "trash":
            return self._get_trash_items()

        return []

    def _get_trash_items(self) -> list:
        """Get items from WiPhoto trash"""
        trash_dir = os.path.join(os.path.expanduser("~"), ".wiphoto", "trash")
        if not os.path.isdir(trash_dir):
            return []
        items = []
        for f in os.listdir(trash_dir):
            path = os.path.join(trash_dir, f)
            if os.path.isfile(path):
                items.append(ImageInfo(
                    path=path,
                    thumbnail_path=path,
                    file_size=os.path.getsize(path)
                ))
        return items

    def _filter_by_date(self, date_condition) -> list:
        result = []
        for img in self.all_images:
            try:
                file_date = None
                if img.date_taken:
                    try:
                        file_date = datetime.strptime(img.date_taken, "%Y:%m:%d %H:%M:%S")
                    except ValueError:
                        pass
                if file_date is None:
                    mtime = os.path.getmtime(img.path)
                    file_date = datetime.fromtimestamp(mtime)
                if date_condition(file_date):
                    result.append(img)
            except Exception as e:
                logging.error(f"Date filter error for {img.path}: {e}")
        return result
