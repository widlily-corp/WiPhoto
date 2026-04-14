# views/folder_tree_widget.py

import os
import logging
from PyQt6.QtWidgets import QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget, QLabel
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QIcon

logger = logging.getLogger(__name__)


class FolderTreeWidget(QWidget):
    """Виджет дерева папок для навигации по файловой структуре"""

    folder_selected = pyqtSignal(str)  # emits folder path

    def __init__(self, parent=None):
        super().__init__(parent)
        self._root_path = ""
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.header_label = QLabel("ПАПКИ")
        self.header_label.setStyleSheet("color: #999; font-size: 11px; font-weight: bold; padding: 4px;")
        layout.addWidget(self.header_label)

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setIndentation(16)
        self.tree.setAnimated(True)
        self.tree.setStyleSheet("""
            QTreeWidget {
                background-color: transparent;
                border: none;
                color: #cccccc;
                font-size: 12px;
            }
            QTreeWidget::item {
                padding: 3px 0;
            }
            QTreeWidget::item:hover {
                background-color: #333333;
            }
            QTreeWidget::item:selected {
                background-color: #4a9eff;
                color: white;
            }
        """)
        self.tree.itemClicked.connect(self._on_item_clicked)
        self.tree.itemExpanded.connect(self._on_item_expanded)
        layout.addWidget(self.tree)

    def set_root(self, folder_path: str):
        """Устанавливает корневую папку и строит дерево"""
        self._root_path = folder_path
        self.tree.clear()

        if not folder_path or not os.path.isdir(folder_path):
            return

        root_name = os.path.basename(folder_path) or folder_path
        root_item = QTreeWidgetItem(self.tree, [f"📁 {root_name}"])
        root_item.setData(0, Qt.ItemDataRole.UserRole, folder_path)
        root_item.setExpanded(True)

        # "All" item - show all files
        all_item = QTreeWidgetItem(root_item, ["📋 Все файлы"])
        all_item.setData(0, Qt.ItemDataRole.UserRole, folder_path)

        # Populate first level of subfolders
        self._populate_children(root_item, folder_path)

    def _populate_children(self, parent_item: QTreeWidgetItem, folder_path: str):
        """Добавляет дочерние папки (lazy loading — только 1 уровень)"""
        try:
            entries = sorted(os.scandir(folder_path), key=lambda e: e.name.lower())
            for entry in entries:
                if entry.is_dir() and not entry.name.startswith('.'):
                    child = QTreeWidgetItem(parent_item, [f"📁 {entry.name}"])
                    child.setData(0, Qt.ItemDataRole.UserRole, entry.path)
                    # Add dummy child for expand arrow (lazy loading)
                    if self._has_subdirs(entry.path):
                        QTreeWidgetItem(child, ["..."])
        except PermissionError:
            pass
        except Exception as e:
            logger.error(f"Error populating folder tree: {e}")

    def _has_subdirs(self, folder_path: str) -> bool:
        """Проверяет наличие подпапок (для lazy loading)"""
        try:
            for entry in os.scandir(folder_path):
                if entry.is_dir() and not entry.name.startswith('.'):
                    return True
        except (PermissionError, OSError):
            pass
        return False

    def _on_item_expanded(self, item: QTreeWidgetItem):
        """Lazy-load: подгружаем подпапки при раскрытии"""
        # Check if has dummy child
        if item.childCount() == 1 and item.child(0).text(0) == "...":
            item.removeChild(item.child(0))
            folder_path = item.data(0, Qt.ItemDataRole.UserRole)
            if folder_path:
                self._populate_children(item, folder_path)

    def _on_item_clicked(self, item: QTreeWidgetItem, column: int):
        """Обработка выбора папки"""
        folder_path = item.data(0, Qt.ItemDataRole.UserRole)
        if folder_path and os.path.isdir(folder_path):
            self.folder_selected.emit(folder_path)

    def get_file_count(self, folder_path: str) -> int:
        """Подсчёт файлов изображений в папке (не рекурсивно)"""
        from models.image_model import SUPPORTED_EXTENSIONS
        count = 0
        try:
            for entry in os.scandir(folder_path):
                if entry.is_file() and entry.name.lower().endswith(SUPPORTED_EXTENSIONS):
                    count += 1
        except (PermissionError, OSError):
            pass
        return count
