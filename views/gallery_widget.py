# views/gallery_widget.py

import os
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QListWidget,
                             QAbstractItemView, QMenu, QLineEdit, QComboBox,
                             QPushButton, QLabel, QToolButton)
from PyQt6.QtGui import QIcon, QAction, QWheelEvent, QKeyEvent
from PyQt6.QtCore import Qt, QSize, pyqtSignal, QTimer

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
    """Gallery grid widget with search, sort, filter bar"""

    edit_requested = pyqtSignal(ImageInfo)
    find_similar_requested = pyqtSignal(ImageInfo)
    filter_applied = pyqtSignal(list)  # emits filtered ImageInfo list

    def __init__(self, parent=None):
        super().__init__(parent)
        self._all_items_data = []  # full unfiltered data
        self._current_sort = "name"
        self._sort_reverse = False
        self._search_timer = QTimer()
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(300)
        self._search_timer.timeout.connect(self._apply_filters)

        self._active_rating_filter = -1  # -1 = all
        self._active_color_filter = ""   # "" = all
        self._active_flag_filter = ""    # "" = all

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # === Toolbar: search + sort ===
        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(4, 4, 4, 2)
        toolbar.setSpacing(4)

        # Search
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Поиск по имени файла...")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.setMaximumHeight(28)
        self.search_edit.setStyleSheet("""
            QLineEdit {
                background: #2a2a2a; border: 1px solid #444;
                border-radius: 4px; padding: 2px 8px; color: #ddd; font-size: 12px;
            }
            QLineEdit:focus { border-color: #0078d4; }
        """)
        self.search_edit.textChanged.connect(lambda: self._search_timer.start())
        toolbar.addWidget(self.search_edit, stretch=1)

        # Sort combo
        self.sort_combo = QComboBox()
        self.sort_combo.setMaximumHeight(28)
        self.sort_combo.addItems([
            "Имя ↑", "Имя ↓",
            "Дата ↑", "Дата ↓",
            "Размер ↑", "Размер ↓",
            "Рейтинг ↑", "Рейтинг ↓",
            "Резкость ↑", "Резкость ↓",
        ])
        self.sort_combo.setStyleSheet("""
            QComboBox {
                background: #2a2a2a; border: 1px solid #444;
                border-radius: 4px; padding: 2px 6px; color: #ddd; font-size: 11px;
                min-width: 100px;
            }
        """)
        self.sort_combo.currentIndexChanged.connect(self._on_sort_changed)
        toolbar.addWidget(self.sort_combo)

        # Count label
        self.count_label = QLabel("0")
        self.count_label.setStyleSheet("color: #888; font-size: 11px; padding: 0 4px;")
        toolbar.addWidget(self.count_label)

        layout.addLayout(toolbar)

        # === Filter bar: stars + colors + flags ===
        filter_bar = QHBoxLayout()
        filter_bar.setContentsMargins(4, 0, 4, 2)
        filter_bar.setSpacing(2)

        # Star filter buttons
        self._star_buttons = []
        for i in range(6):
            btn = QToolButton()
            if i == 0:
                btn.setText("All")
                btn.setToolTip("Все рейтинги")
            else:
                btn.setText("\u2605" * i)
                btn.setToolTip(f"Рейтинг {i}+")
            btn.setCheckable(True)
            btn.setChecked(i == 0)
            btn.setMaximumHeight(22)
            btn.setStyleSheet(self._filter_btn_style())
            btn.clicked.connect(lambda checked, r=i: self._on_rating_filter(r))
            self._star_buttons.append(btn)
            filter_bar.addWidget(btn)

        filter_bar.addSpacing(8)

        # Color filter buttons
        color_defs = [
            ("", "#666", "Все"),
            ("red", "#e74c3c", "Красная"),
            ("yellow", "#f1c40f", "Желтая"),
            ("green", "#2ecc71", "Зеленая"),
            ("blue", "#3498db", "Синяя"),
        ]
        self._color_buttons = []
        for color_id, hex_color, tooltip in color_defs:
            btn = QToolButton()
            if color_id:
                btn.setText("\u25cf")
                btn.setStyleSheet(self._color_btn_style(hex_color))
            else:
                btn.setText("All")
                btn.setStyleSheet(self._filter_btn_style())
            btn.setCheckable(True)
            btn.setChecked(color_id == "")
            btn.setMaximumHeight(22)
            btn.setToolTip(tooltip)
            btn.clicked.connect(lambda checked, c=color_id: self._on_color_filter(c))
            self._color_buttons.append((color_id, btn))
            filter_bar.addWidget(btn)

        filter_bar.addSpacing(8)

        # Flag filter buttons
        flag_defs = [("", "All", "Все"), ("picked", "\u2713", "Выбранные"), ("rejected", "\u2717", "Отклонённые")]
        self._flag_buttons = []
        for flag_id, text, tooltip in flag_defs:
            btn = QToolButton()
            btn.setText(text)
            btn.setCheckable(True)
            btn.setChecked(flag_id == "")
            btn.setMaximumHeight(22)
            btn.setStyleSheet(self._filter_btn_style())
            btn.setToolTip(tooltip)
            btn.clicked.connect(lambda checked, f=flag_id: self._on_flag_filter(f))
            self._flag_buttons.append((flag_id, btn))
            filter_bar.addWidget(btn)

        filter_bar.addStretch()
        layout.addLayout(filter_bar)

        # === Thumbnail grid ===
        self.thumbnail_view = ThumbnailListWidget()
        self.thumbnail_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.thumbnail_view.customContextMenuRequested.connect(self._show_context_menu)
        layout.addWidget(self.thumbnail_view)

        self._create_actions()

    def _filter_btn_style(self):
        return """
            QToolButton {
                background: transparent; border: 1px solid transparent;
                border-radius: 3px; padding: 1px 5px; color: #aaa; font-size: 11px;
            }
            QToolButton:hover { background: #333; border-color: #555; }
            QToolButton:checked { background: #0078d4; color: white; border-color: #0078d4; }
        """

    def _color_btn_style(self, hex_color):
        return f"""
            QToolButton {{
                background: transparent; border: 1px solid transparent;
                border-radius: 3px; padding: 1px 5px; color: {hex_color}; font-size: 14px;
            }}
            QToolButton:hover {{ background: #333; border-color: #555; }}
            QToolButton:checked {{ background: #333; border-color: {hex_color}; }}
        """

    # --- Filter logic ---

    def _on_rating_filter(self, rating: int):
        self._active_rating_filter = rating
        for i, btn in enumerate(self._star_buttons):
            btn.setChecked(i == rating)
        self._apply_filters()

    def _on_color_filter(self, color: str):
        self._active_color_filter = color
        for cid, btn in self._color_buttons:
            btn.setChecked(cid == color)
        self._apply_filters()

    def _on_flag_filter(self, flag: str):
        self._active_flag_filter = flag
        for fid, btn in self._flag_buttons:
            btn.setChecked(fid == flag)
        self._apply_filters()

    def _on_sort_changed(self, index):
        sort_keys = [
            ("name", False), ("name", True),
            ("date", False), ("date", True),
            ("size", False), ("size", True),
            ("rating", False), ("rating", True),
            ("sharpness", False), ("sharpness", True),
        ]
        if 0 <= index < len(sort_keys):
            self._current_sort, self._sort_reverse = sort_keys[index]
            self._apply_filters()

    def set_all_items(self, items_data: list):
        """Store full unfiltered data for search/filter/sort"""
        self._all_items_data = list(items_data)
        self._apply_filters()

    def _apply_filters(self):
        """Apply search + rating + color + flag filters, then sort"""
        search_text = self.search_edit.text().strip().lower()
        result = self._all_items_data

        # Search filter
        if search_text:
            result = [info for info in result
                      if search_text in os.path.basename(info.path).lower()]

        # Rating filter
        if self._active_rating_filter > 0:
            result = [info for info in result if info.rating >= self._active_rating_filter]

        # Color filter
        if self._active_color_filter:
            result = [info for info in result if info.color_label == self._active_color_filter]

        # Flag filter
        if self._active_flag_filter:
            result = [info for info in result if info.flag_status == self._active_flag_filter]

        # Sort
        result = self._sort_items(result)

        # Update count
        total = len(self._all_items_data)
        shown = len(result)
        if shown == total:
            self.count_label.setText(f"{total}")
        else:
            self.count_label.setText(f"{shown}/{total}")

        # Emit filtered list
        self.filter_applied.emit(result)

    def _sort_items(self, items: list) -> list:
        key_funcs = {
            "name": lambda i: os.path.basename(i.path).lower(),
            "date": lambda i: i.date_taken or "",
            "size": lambda i: i.file_size,
            "rating": lambda i: i.rating,
            "sharpness": lambda i: i.sharpness,
        }
        key_fn = key_funcs.get(self._current_sort, key_funcs["name"])
        return sorted(items, key=key_fn, reverse=self._sort_reverse)

    # --- Actions & context menu ---

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
