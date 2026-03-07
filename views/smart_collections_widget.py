# views/smart_collections_widget.py

import logging
import os
from datetime import datetime

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QListWidget, QListWidgetItem, QLabel
from PyQt6.QtCore import Qt, pyqtSignal

from models.image_model import ImageInfo


class SmartCollectionsWidget(QWidget):
    """Sidebar widget: list of smart collections that filter the main gallery"""

    collection_selected = pyqtSignal(list)  # emits filtered list of ImageInfo
    collection_changed = pyqtSignal(str)    # emits collection_id

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

        self._add_standard_collections()

    def _add_standard_collections(self):
        collections = [
            ("Все файлы", "all"),
            ("Сегодня", "today"),
            ("Эта неделя", "this_week"),
            ("Этот месяц", "this_month"),
            ("Лучшие", "best_quality"),
            ("Высокая резкость", "sharp"),
            ("RAW файлы", "raw_files"),
            ("По камере", "by_camera"),
            ("Дубликаты", "all_duplicates"),
            ("Уникальные", "unique"),
            ("С лицами", "with_faces"),
            ("С животными", "with_animals"),
            ("С геотегами", "with_geotags"),
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
            raw_exts = ('.arw', '.cr2', '.cr3', '.nef', '.dng', '.raw', '.rw2', '.orf', '.pef', '.raf')
            return [img for img in self.all_images if img.path.lower().endswith(raw_exts)]
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
        elif collection_id == "with_geotags":
            return [img for img in self.all_images if img.gps_location is not None]

        return []

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
