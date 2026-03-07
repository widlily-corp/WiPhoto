# views/main_window.py

import os
import logging
import rawpy
import cv2
from PIL import Image
from PyQt6.QtCore import Qt, QSize, pyqtSignal, QPointF
from PyQt6.QtGui import (QPixmap, QIcon, QImage, QColor, QPainter, QPen, QAction, QActionGroup,
                         QTransform, QKeySequence, QPolygonF)
from PyQt6.QtWidgets import (QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QListWidgetItem,
                             QTableWidgetItem, QToolBar, QStatusBar, QSizePolicy, QSlider,
                             QSplitter, QStackedWidget, QLabel, QTableWidget, QAbstractItemView,
                             QHeaderView, QPushButton)

from models.image_model import ImageInfo
from views.editor_widget import EditorWidget
from views.gallery_widget import GalleryWidget
from views.about_dialog import AboutDialog
from views.settings_dialog import SettingsDialog
from views.comparison_view import ComparisonView
from views.smart_collections_widget import SmartCollectionsWidget
from views.map_widget import MapWidget
from utils import resource_path

Image.MAX_IMAGE_PIXELS = None
RAW_FORMATS = ('.arw', '.cr2', '.cr3', '.nef', '.nrw', '.dng', '.raw', '.rw2', '.orf', '.pef',
               '.raf', '.srw', '.x3f')
VIDEO_FORMATS = ('.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v',
                 '.mpg', '.mpeg', '.3gp', '.ogv', '.ts', '.mts', '.m2ts')


class MainWindow(QMainWindow):
    delete_requested = pyqtSignal(list)
    copy_requested = pyqtSignal(list)
    move_requested = pyqtSignal(list)
    keep_best_requested = pyqtSignal(ImageInfo)
    filter_changed = pyqtSignal(str)
    thumbnail_size_changed = pyqtSignal(int)
    rotate_requested = pyqtSignal(int)
    style_copy_requested = pyqtSignal()
    files_dropped = pyqtSignal(list)
    compare_requested = pyqtSignal(list)
    refresh_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("WiPhoto")
        self.setWindowIcon(QIcon(resource_path("assets/icon.ico")))
        self.setGeometry(100, 100, 1600, 900)
        self.current_preview_pixmap = None

        self.setAcceptDrops(True)

        # --- Create widgets ---
        self.gallery_widget = GalleryWidget(self)
        self.editor_widget = EditorWidget(self)
        self.comparison_view = ComparisonView(self)
        self.smart_collections = SmartCollectionsWidget(self)
        self.map_widget = MapWidget(self)

        # --- Build layout ---
        self._build_layout()
        self._create_actions()
        self._create_menu_bar()
        self._create_tool_bar()
        self._create_status_bar()

        self.gallery_widget.thumbnail_view.itemSelectionChanged.connect(self._update_status_bar)

    def _build_layout(self):
        """3-column layout: left sidebar | center content | right sidebar"""
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(self.main_splitter)

        # === LEFT SIDEBAR ===
        self.left_sidebar = self._create_left_sidebar()

        # === CENTER AREA ===
        self.center_stack = QStackedWidget()
        self.center_stack.addWidget(self.gallery_widget)    # index 0
        self.center_stack.addWidget(self.map_widget)        # index 1
        self.center_stack.addWidget(self.comparison_view)   # index 2
        self.center_stack.addWidget(self.editor_widget)     # index 3
        self.center_stack.setCurrentIndex(0)

        # === RIGHT SIDEBAR ===
        self.right_sidebar = self._create_right_sidebar()

        self.main_splitter.addWidget(self.left_sidebar)
        self.main_splitter.addWidget(self.center_stack)
        self.main_splitter.addWidget(self.right_sidebar)
        self.main_splitter.setSizes([200, 1000, 300])
        self.main_splitter.setStretchFactor(0, 0)
        self.main_splitter.setStretchFactor(1, 1)
        self.main_splitter.setStretchFactor(2, 0)

    def _create_left_sidebar(self) -> QWidget:
        sidebar = QWidget()
        sidebar.setMinimumWidth(160)
        sidebar.setMaximumWidth(300)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Filter buttons
        filter_label = QLabel("ФИЛЬТР")
        filter_label.setStyleSheet("color: #999; font-size: 11px; font-weight: bold; padding: 4px;")
        layout.addWidget(filter_label)

        self._filter_buttons = {}
        for text, filter_id in [("Все", "all"), ("Лучшие", "best"), ("Дубликаты", "duplicates")]:
            btn = QPushButton(text)
            btn.setCheckable(True)
            btn.setChecked(filter_id == "all")
            btn.clicked.connect(lambda checked, fid=filter_id: self._on_filter_clicked(fid))
            btn.setStyleSheet("""
                QPushButton { text-align: left; padding: 6px 10px; border: none; border-radius: 3px; }
                QPushButton:hover { background-color: #333333; }
                QPushButton:checked { background-color: #4a9eff; color: white; }
            """)
            layout.addWidget(btn)
            self._filter_buttons[filter_id] = btn

        # Smart collections
        layout.addWidget(self.smart_collections)
        layout.addStretch()

        # Toggle left sidebar button
        self.toggle_left_btn = QPushButton("Скрыть")
        self.toggle_left_btn.setFixedHeight(24)
        self.toggle_left_btn.setStyleSheet("font-size: 11px; border: none; color: #808080;")
        self.toggle_left_btn.clicked.connect(self._toggle_left_sidebar)
        layout.addWidget(self.toggle_left_btn)

        return sidebar

    def _create_right_sidebar(self) -> QWidget:
        sidebar = QWidget()
        sidebar.setMinimumWidth(250)
        sidebar.setMaximumWidth(500)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Right sidebar splitter (preview / metadata)
        right_splitter = QSplitter(Qt.Orientation.Vertical)

        # Preview
        self.preview_area = QLabel("Выберите файл")
        self.preview_area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_area.setMinimumHeight(200)
        self.preview_area.setStyleSheet("""
            QLabel {
                background-color: #252526;
                border: 1px solid #3c3c3c;
                color: #808080;
                font-size: 13px;
            }
        """)
        right_splitter.addWidget(self.preview_area)

        # Metadata table
        meta_container = QWidget()
        meta_layout = QVBoxLayout(meta_container)
        meta_layout.setContentsMargins(0, 0, 0, 0)
        meta_layout.setSpacing(0)

        meta_label = QLabel("МЕТАДАННЫЕ")
        meta_label.setStyleSheet("color: #999; font-size: 11px; font-weight: bold; padding: 4px;")
        meta_layout.addWidget(meta_label)

        self.metadata_view = QTableWidget()
        self.metadata_view.setColumnCount(2)
        self.metadata_view.setHorizontalHeaderLabels(["Параметр", "Значение"])
        self.metadata_view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.metadata_view.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.metadata_view.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.metadata_view.verticalHeader().setVisible(False)
        meta_layout.addWidget(self.metadata_view)
        right_splitter.addWidget(meta_container)

        # AI Info panel
        ai_container = QWidget()
        ai_layout = QVBoxLayout(ai_container)
        ai_layout.setContentsMargins(0, 0, 0, 0)
        ai_layout.setSpacing(0)

        ai_label = QLabel("АНАЛИЗ")
        ai_label.setStyleSheet("color: #999; font-size: 11px; font-weight: bold; padding: 4px;")
        ai_layout.addWidget(ai_label)

        self.ai_info_label = QLabel("")
        self.ai_info_label.setWordWrap(True)
        self.ai_info_label.setStyleSheet("padding: 6px; color: #cccccc; font-size: 12px;")
        ai_layout.addWidget(self.ai_info_label)
        ai_layout.addStretch()
        right_splitter.addWidget(ai_container)

        right_splitter.setSizes([400, 200, 100])

        layout.addWidget(right_splitter)

        # Toggle right sidebar button
        self.toggle_right_btn = QPushButton("Скрыть")
        self.toggle_right_btn.setFixedHeight(24)
        self.toggle_right_btn.setStyleSheet("font-size: 11px; border: none; color: #808080;")
        self.toggle_right_btn.clicked.connect(self._toggle_right_sidebar)
        layout.addWidget(self.toggle_right_btn)

        return sidebar

    def _on_filter_clicked(self, filter_id: str):
        for fid, btn in self._filter_buttons.items():
            btn.setChecked(fid == filter_id)
        self.filter_changed.emit(filter_id)

    def _toggle_left_sidebar(self):
        vis = self.left_sidebar.isVisible()
        self.left_sidebar.setVisible(not vis)
        self.toggle_left_btn.setText("Показать" if vis else "Скрыть")

    def _toggle_right_sidebar(self):
        vis = self.right_sidebar.isVisible()
        self.right_sidebar.setVisible(not vis)
        self.toggle_right_btn.setText("Показать" if vis else "Скрыть")

    # ========== DRAG & DROP ==========
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.statusBar().showMessage("Отпустите файлы для обработки...")

    def dragLeaveEvent(self, event):
        self.statusBar().showMessage("Готово")

    def dropEvent(self, event):
        try:
            files = []
            all_exts = ('.jpg', '.jpeg', '.png', '.bmp', '.gif', '.tiff', '.tif',
                        '.webp', '.heic', '.heif') + RAW_FORMATS + VIDEO_FORMATS
            for url in event.mimeData().urls():
                file_path = url.toLocalFile()
                if os.path.isdir(file_path):
                    for root, dirs, filenames in os.walk(file_path):
                        for filename in filenames:
                            if filename.lower().endswith(all_exts):
                                files.append(os.path.join(root, filename))
                elif os.path.isfile(file_path):
                    if file_path.lower().endswith(all_exts):
                        files.append(file_path)

            if files:
                self.files_dropped.emit(files)
                self.statusBar().showMessage(f"Добавлено файлов: {len(files)}")
            else:
                self.statusBar().showMessage("Нет подходящих файлов")
        except Exception as e:
            self.statusBar().showMessage(f"Ошибка: {e}")

    # ========== ACTIONS ==========
    def switch_to_editor(self, image_info: ImageInfo):
        try:
            self.center_stack.setCurrentWidget(self.editor_widget)
            self.editor_widget.load_image(image_info)
        except Exception as e:
            self.statusBar().showMessage(f"Ошибка загрузки в редактор: {e}")

    def switch_to_gallery(self):
        self.center_stack.setCurrentIndex(0)

    def switch_to_map(self):
        self.center_stack.setCurrentIndex(1)

    def switch_to_compare(self):
        self.center_stack.setCurrentIndex(2)

    def _create_actions(self):
        try:
            self.delete_action = QAction(QIcon(resource_path("assets/trash-2.png")), "Удалить", self)
            self.copy_action = QAction(QIcon(resource_path("assets/copy.png")), "Копировать в...", self)
            self.move_action = QAction(QIcon(resource_path("assets/move.png")), "Переместить в...", self)
            self.keep_best_action = QAction(QIcon(resource_path("assets/star.png")), "Оставить лучшее", self)
            self.rotate_action = QAction(QIcon(resource_path("assets/rotate-cw.png")), "Повернуть", self)
            self.exit_action = QAction(QIcon(resource_path("assets/log-out.png")), "Выход", self)
            self.style_action = QAction(QIcon(resource_path("assets/pipette.png")), "Копировать стиль", self)
            self.settings_action = QAction(QIcon(resource_path("assets/settings.png")), "Настройки", self)
            self.about_action = QAction("О программе WiPhoto", self)
            self.compare_action = QAction(QIcon(resource_path("assets/compare.png")), "Сравнить", self)
            self.fullscreen_action = QAction("Полноэкранный режим", self)
            self.quick_view_action = QAction("Быстрый просмотр", self)
            self.next_image_action = QAction("Следующее", self)
            self.prev_image_action = QAction("Предыдущее", self)
            self.select_all_action = QAction("Выбрать все", self)
            self.deselect_all_action = QAction("Снять выделение", self)
            self.refresh_action = QAction("Обновить", self)

            # View mode actions
            self.view_gallery_action = QAction("Галерея", self)
            self.view_gallery_action.setCheckable(True)
            self.view_gallery_action.setChecked(True)
            self.view_map_action = QAction("Карта", self)
            self.view_map_action.setCheckable(True)

            # Shortcuts
            self.settings_action.setShortcut(QKeySequence("Ctrl+,"))
            self.delete_action.setShortcut(QKeySequence.StandardKey.Delete)
            self.copy_action.setShortcut(QKeySequence.StandardKey.Copy)
            self.move_action.setShortcut(QKeySequence.StandardKey.Cut)
            self.rotate_action.setShortcut(QKeySequence("R"))
            self.exit_action.setShortcut(QKeySequence("Ctrl+Q"))
            self.select_all_action.setShortcut(QKeySequence.StandardKey.SelectAll)
            self.deselect_all_action.setShortcut(QKeySequence("Ctrl+Shift+A"))
            self.compare_action.setShortcut(QKeySequence("Ctrl+D"))
            self.fullscreen_action.setShortcut(QKeySequence("F11"))
            self.quick_view_action.setShortcut(QKeySequence("Space"))
            self.next_image_action.setShortcut(QKeySequence("Right"))
            self.prev_image_action.setShortcut(QKeySequence("Left"))
            self.refresh_action.setShortcut(QKeySequence("F5"))

            # Connect signals
            self.settings_action.triggered.connect(self.open_settings_dialog)
            self.delete_action.triggered.connect(self._on_delete_triggered)
            self.copy_action.triggered.connect(self._on_copy_triggered)
            self.move_action.triggered.connect(self._on_move_triggered)
            self.keep_best_action.triggered.connect(self._on_keep_best_triggered)
            self.rotate_action.triggered.connect(self.rotate_preview)
            self.exit_action.triggered.connect(self.close)
            self.style_action.triggered.connect(self.style_copy_requested.emit)
            self.about_action.triggered.connect(self._open_about_dialog)
            self.select_all_action.triggered.connect(self.gallery_widget.thumbnail_view.selectAll)
            self.deselect_all_action.triggered.connect(self.gallery_widget.thumbnail_view.clearSelection)
            self.compare_action.triggered.connect(self._on_compare_triggered)
            self.fullscreen_action.triggered.connect(self._toggle_fullscreen)
            self.quick_view_action.triggered.connect(self._quick_view)
            self.next_image_action.triggered.connect(self._next_image)
            self.prev_image_action.triggered.connect(self._prev_image)
            self.refresh_action.triggered.connect(self._refresh_gallery)

            self.view_gallery_action.triggered.connect(self.switch_to_gallery)
            self.view_map_action.triggered.connect(self.switch_to_map)

            self.addActions([
                self.delete_action, self.copy_action, self.move_action,
                self.rotate_action, self.exit_action, self.select_all_action,
                self.deselect_all_action, self.settings_action, self.compare_action,
                self.fullscreen_action, self.quick_view_action, self.next_image_action,
                self.prev_image_action, self.refresh_action
            ])
        except Exception as e:
            logging.error(f"Error creating actions: {e}")

    def _create_menu_bar(self):
        menu_bar = self.menuBar()

        file_menu = menu_bar.addMenu("Файл")
        file_menu.addAction(self.settings_action)
        file_menu.addAction(self.refresh_action)
        file_menu.addSeparator()
        file_menu.addAction(self.exit_action)

        edit_menu = menu_bar.addMenu("Правка")
        edit_menu.addAction(self.select_all_action)
        edit_menu.addAction(self.deselect_all_action)

        view_menu = menu_bar.addMenu("Вид")
        view_menu.addAction(self.view_gallery_action)
        view_menu.addAction(self.view_map_action)
        view_menu.addSeparator()
        view_menu.addAction(self.fullscreen_action)
        view_menu.addAction(self.quick_view_action)

        tools_menu = menu_bar.addMenu("Инструменты")
        tools_menu.addAction(self.compare_action)
        tools_menu.addAction(self.style_action)

        help_menu = menu_bar.addMenu("Справка")
        help_menu.addAction(self.about_action)

    def _create_tool_bar(self):
        try:
            toolbar = QToolBar("Инструменты")
            self.addToolBar(toolbar)
            toolbar.setMovable(False)
            toolbar.setIconSize(QSize(18, 18))

            # View mode buttons
            view_group = QActionGroup(self)
            view_group.setExclusive(True)
            view_group.addAction(self.view_gallery_action)
            view_group.addAction(self.view_map_action)
            toolbar.addActions(view_group.actions())
            toolbar.addSeparator()

            # Main actions
            toolbar.addAction(self.delete_action)
            toolbar.addAction(self.copy_action)
            toolbar.addAction(self.move_action)
            toolbar.addSeparator()
            toolbar.addAction(self.keep_best_action)
            toolbar.addAction(self.compare_action)
            toolbar.addSeparator()
            toolbar.addAction(self.style_action)
            toolbar.addAction(self.rotate_action)
            toolbar.addSeparator()
            toolbar.addAction(self.settings_action)

            # Spacer
            spacer = QWidget()
            spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            toolbar.addWidget(spacer)

            # Zoom slider
            zoom_label = QLabel(" Размер: ")
            zoom_label.setStyleSheet("color: #808080; font-size: 12px;")
            toolbar.addWidget(zoom_label)

            self.size_slider = QSlider(Qt.Orientation.Horizontal)
            self.size_slider.setRange(100, 400)
            self.size_slider.setValue(200)
            self.size_slider.setFixedWidth(120)
            self.size_slider.valueChanged.connect(self.thumbnail_size_changed.emit)
            toolbar.addWidget(self.size_slider)
        except Exception as e:
            logging.error(f"Error creating toolbar: {e}")

    def _create_status_bar(self):
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Готово")

    # ========== HOTKEYS ==========
    def _on_compare_triggered(self):
        selected = self._get_selected_image_infos()
        if len(selected) == 2:
            self.compare_requested.emit(selected)
            self.center_stack.setCurrentWidget(self.comparison_view)
        else:
            self.statusBar().showMessage("Выберите 2 фото для сравнения")

    def _toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def _quick_view(self):
        selected = self._get_selected_image_infos()
        if len(selected) != 1:
            return
        info = selected[0]
        if not hasattr(self, '_quick_view_overlay') or self._quick_view_overlay is None:
            self._quick_view_overlay = QuickViewOverlay(self)
        if self._quick_view_overlay.isVisible():
            self._quick_view_overlay.hide()
        else:
            self._quick_view_overlay.show_image(info.path)

    def _next_image(self):
        view = self.gallery_widget.thumbnail_view
        current = view.currentRow()
        if current < view.count() - 1:
            view.setCurrentRow(current + 1)

    def _prev_image(self):
        view = self.gallery_widget.thumbnail_view
        current = view.currentRow()
        if current > 0:
            view.setCurrentRow(current - 1)

    def _refresh_gallery(self):
        self.statusBar().showMessage("Обновление...")
        self.refresh_requested.emit()

    def _open_about_dialog(self):
        try:
            dialog = AboutDialog(self)
            dialog.exec()
        except Exception as e:
            logging.error(f"Error: {e}")

    def open_settings_dialog(self):
        try:
            dialog = SettingsDialog(self)
            dialog.exec()
        except Exception as e:
            logging.error(f"Error: {e}")

    def enter_style_copy_mode(self, active: bool):
        self.setCursor(Qt.CursorShape.CrossCursor if active else Qt.CursorShape.ArrowCursor)

    # ========== THUMBNAIL MANAGEMENT ==========
    def add_thumbnails_batch(self, image_infos: list):
        view = self.gallery_widget.thumbnail_view
        view.setUpdatesEnabled(False)
        try:
            for info in image_infos:
                if info.thumbnail_path and os.path.exists(info.thumbnail_path):
                    try:
                        item = QListWidgetItem(os.path.basename(info.path))
                        item.setData(Qt.ItemDataRole.UserRole, info)
                        total_size = self.gallery_widget.thumbnail_view.gridSize()
                        item.setSizeHint(total_size)
                        view.addItem(item)
                    except Exception as e:
                        logging.error(f"Error adding thumbnail: {e}")
        finally:
            view.setUpdatesEnabled(True)

    def update_thumbnail_styles(self):
        """Force repaint of all thumbnails (delegate handles styling)"""
        self.gallery_widget.thumbnail_view.viewport().update()

    def clear_thumbnails(self):
        self.gallery_widget.thumbnail_view.clear()
        self.gallery_widget.thumbnail_view.delegate.clear_cache()
        self.clear_preview_and_metadata()

    def set_thumbnail_size(self, size: int):
        self.gallery_widget.set_thumbnail_size(size)

    def remove_thumbnails(self, infos_to_remove: list):
        try:
            paths_to_remove = {info.path for info in infos_to_remove}
            view = self.gallery_widget.thumbnail_view
            for i in reversed(range(view.count())):
                item = view.item(i)
                data = item.data(Qt.ItemDataRole.UserRole)
                if isinstance(data, ImageInfo) and data.path in paths_to_remove:
                    view.takeItem(i)
            self._update_status_bar()
        except Exception as e:
            logging.error(f"Error removing thumbnails: {e}")

    # ========== PREVIEW ==========
    def show_preview(self, image_path: str):
        try:
            pil_image = None
            is_raw = image_path.lower().endswith(RAW_FORMATS)
            is_video = image_path.lower().endswith(VIDEO_FORMATS)

            if is_video:
                cap = cv2.VideoCapture(image_path)
                ret, frame = cap.read()
                cap.release()
                if ret and frame is not None:
                    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    pil_image = Image.fromarray(rgb)
                else:
                    self.preview_area.setText("Видео не загружено")
                    return
            elif is_raw:
                with rawpy.imread(image_path) as raw:
                    rgb = raw.postprocess(use_camera_wb=True, output_bps=8)
                pil_image = Image.fromarray(rgb)
            else:
                pil_image = Image.open(image_path)

            if pil_image:
                if pil_image.mode != 'RGB':
                    pil_image = pil_image.convert('RGB')

                q_image = QImage(
                    pil_image.tobytes(),
                    pil_image.width,
                    pil_image.height,
                    pil_image.width * 3,
                    QImage.Format.Format_RGB888
                )
                self.current_preview_pixmap = QPixmap.fromImage(q_image)

                self.preview_area.setPixmap(
                    self.current_preview_pixmap.scaled(
                        self.preview_area.size(),
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation
                    )
                )
            else:
                self.preview_area.setText("Не удалось загрузить")
        except Exception as e:
            self.preview_area.setText(f"Ошибка: {e}")

    def update_metadata(self, data: dict):
        try:
            self.metadata_view.setRowCount(0)
            self.metadata_view.setRowCount(len(data))
            for row, (key, value) in enumerate(data.items()):
                self.metadata_view.setItem(row, 0, QTableWidgetItem(key))
                self.metadata_view.setItem(row, 1, QTableWidgetItem(str(value)))
        except Exception as e:
            logging.error(f"Error updating metadata: {e}")

    def update_ai_info(self, info: ImageInfo):
        """Update AI analysis panel in right sidebar"""
        parts = []
        if info.faces_count > 0:
            parts.append(f"Лица: {info.faces_count}")
        if info.animals_count > 0:
            parts.append(f"Животные: {info.animals_count}")
        if info.sharpness > 0:
            parts.append(f"Резкость: {info.sharpness:.1f}")
        if info.camera_model:
            parts.append(f"Камера: {info.camera_model}")
        if info.date_taken:
            parts.append(f"Дата: {info.date_taken}")
        if info.gps_location:
            lat, lon = info.gps_location
            parts.append(f"GPS: {lat:.4f}, {lon:.4f}")
        if info.group_id is not None:
            if info.is_best_in_group:
                parts.append("Лучшее в группе")
            else:
                parts.append(f"Дубликат (группа {info.group_id})")

        self.ai_info_label.setText("\n".join(parts) if parts else "Нет данных анализа")

    def clear_preview_and_metadata(self):
        self.preview_area.setText("Выберите файл")
        self.preview_area.setPixmap(QPixmap())
        self.metadata_view.setRowCount(0)
        self.ai_info_label.setText("")

    def rotate_preview(self):
        if self.current_preview_pixmap and not self.current_preview_pixmap.isNull():
            try:
                transform = QTransform().rotate(90)
                self.current_preview_pixmap = self.current_preview_pixmap.transformed(
                    transform, Qt.TransformationMode.SmoothTransformation)
                self.preview_area.setPixmap(
                    self.current_preview_pixmap.scaled(
                        self.preview_area.size(),
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation
                    )
                )
            except Exception as e:
                logging.error(f"Error rotating: {e}")

    # ========== HELPERS ==========
    def _get_selected_image_infos(self) -> list:
        return self.gallery_widget._get_selected_image_infos()

    def _on_delete_triggered(self):
        selected = self._get_selected_image_infos()
        if selected:
            self.delete_requested.emit(selected)

    def _on_copy_triggered(self):
        selected = self._get_selected_image_infos()
        if selected:
            self.copy_requested.emit(selected)

    def _on_move_triggered(self):
        selected = self._get_selected_image_infos()
        if selected:
            self.move_requested.emit(selected)

    def _on_keep_best_triggered(self):
        selected = self._get_selected_image_infos()
        if len(selected) == 1:
            self.keep_best_requested.emit(selected[0])

    def _update_status_bar(self):
        try:
            total = self.gallery_widget.thumbnail_view.count()
            selected = len(self.gallery_widget.thumbnail_view.selectedItems())
            self.status_bar.showMessage(f"Всего: {total} | Выбрано: {selected}")
        except Exception as e:
            logging.error(f"Error: {e}")

    def closeEvent(self, event):
        try:
            if hasattr(self, 'editor_widget'):
                self.editor_widget.close()
            event.accept()
        except Exception as e:
            logging.error(f"Error closing: {e}")
            event.accept()


class QuickViewOverlay(QWidget):
    """Fullscreen overlay for quick preview (Space key)"""

    def __init__(self, parent):
        super().__init__(parent)
        self.setStyleSheet("background-color: rgba(0, 0, 0, 230);")
        self._label = QLabel(self)
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.addWidget(self._label)
        self.hide()

    def show_image(self, image_path: str):
        self.setGeometry(self.parent().rect())
        try:
            is_video = image_path.lower().endswith(VIDEO_FORMATS)
            is_raw = image_path.lower().endswith(RAW_FORMATS)

            if is_video:
                cap = cv2.VideoCapture(image_path)
                ret, frame = cap.read()
                cap.release()
                if ret:
                    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    h, w, ch = rgb.shape
                    q_img = QImage(rgb.data, w, h, ch * w, QImage.Format.Format_RGB888).copy()
                    pixmap = QPixmap.fromImage(q_img)
                else:
                    self._label.setText("Видео не загружено")
                    self.show()
                    self.raise_()
                    return
            elif is_raw:
                with rawpy.imread(image_path) as raw:
                    rgb = raw.postprocess(use_camera_wb=True, output_bps=8)
                pil_img = Image.fromarray(rgb)
                if pil_img.mode != 'RGB':
                    pil_img = pil_img.convert('RGB')
                q_img = QImage(pil_img.tobytes(), pil_img.width, pil_img.height,
                               pil_img.width * 3, QImage.Format.Format_RGB888)
                pixmap = QPixmap.fromImage(q_img)
            else:
                pixmap = QPixmap(image_path)

            if not pixmap.isNull():
                self._label.setPixmap(pixmap.scaled(
                    self.size(), Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                ))
            else:
                self._label.setText("Ошибка загрузки")
        except Exception as e:
            self._label.setText(f"Ошибка: {e}")

        self.show()
        self.raise_()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Space, Qt.Key.Key_Escape):
            self.hide()

    def mousePressEvent(self, event):
        self.hide()
