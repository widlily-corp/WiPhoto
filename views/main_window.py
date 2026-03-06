# views/main_window.py

import os
import logging
import rawpy
import cv2
from PIL import Image
from PyQt6.QtCore import Qt, QSize, pyqtSignal, QPointF
from PyQt6.QtGui import (QPixmap, QIcon, QImage, QColor, QPainter, QPen, QAction, QActionGroup,
                         QTransform, QKeySequence, QPalette, QBrush, QPolygonF)
from PyQt6.QtWidgets import (QMainWindow, QWidget, QHBoxLayout, QListWidgetItem,
                             QTableWidgetItem, QToolBar, QStatusBar, QSizePolicy, QSlider, QTabWidget,
                             QGraphicsDropShadowEffect, QVBoxLayout, QLabel)

from models.image_model import ImageInfo
from views.editor_widget import EditorWidget
from views.gallery_widget import GalleryWidget
from views.about_dialog import AboutDialog
from views.settings_dialog import SettingsDialog
from views.comparison_view import ComparisonView
from views.smart_collections_widget import SmartCollectionsWidget
from views.map_widget import MapWidget
from utils import resource_path, apply_shadow_effect

Image.MAX_IMAGE_PIXELS = None
RAW_FORMATS = ('.arw', '.cr2', '.cr3', '.nef', '.nrw', '.dng', '.raw', '.rw2', '.orf', '.pef',
               '.raf', '.srw', '.x3f')
VIDEO_FORMATS = ('.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v',
                 '.mpg', '.mpeg', '.3gp', '.ogv', '.ts', '.mts', '.m2ts')


class BackgroundWidget(QWidget):
    """Виджет, который рисует фоновое изображение или сплошной цвет, если оно не найдено."""

    def __init__(self, parent=None):
        super().__init__(parent)
        # Отключаем автозаполнение, чтобы рисовать свой фон
        self.setAutoFillBackground(False)
        self.background_pixmap = self._load_background()

    def _load_background(self) -> QPixmap:
        for ext in ["png", "jpg", "jpeg"]:
            path = resource_path(f"assets/background.{ext}")
            if os.path.exists(path):
                print(f"Фоновое изображение найдено: {path}")
                return QPixmap(path)
        print("Файл фонового изображения не найден. Используется цвет по умолчанию.")
        return None

    def paintEvent(self, event):
        painter = QPainter(self)
        if self.background_pixmap and not self.background_pixmap.isNull():
            scaled_pixmap = self.background_pixmap.scaled(
                self.size(), Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
            x = (self.width() - scaled_pixmap.width()) / 2
            y = (self.height() - scaled_pixmap.height()) / 2
            painter.drawPixmap(int(x), int(y), scaled_pixmap)
        else:
            # Современный градиентный фон
            from PyQt6.QtGui import QLinearGradient
            gradient = QLinearGradient(0, 0, 0, self.height())
            gradient.setColorAt(0, QColor("#0d1117"))
            gradient.setColorAt(1, QColor("#161b22"))
            painter.fillRect(self.rect(), gradient)


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
        self.setWindowTitle("WiPhoto - Менеджер фотографий")
        self.setWindowIcon(QIcon(resource_path("assets/icon.ico")))
        self.setGeometry(100, 100, 1600, 900)
        self.current_preview_pixmap = None

        # Отключаем автозаполнение фона палитрой
        # Это позволяет BackgroundWidget рисовать свой кастомный фон
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
        self.setAutoFillBackground(False)

        # Включаем Drag & Drop
        self.setAcceptDrops(True)

        # Создаем фоновый виджет
        self.background = BackgroundWidget(self)

        # Создаем главный виджет компоновки
        central_layout_widget = QWidget()
        central_layout_widget.setStyleSheet("background: transparent;")
        main_layout = QHBoxLayout(central_layout_widget)
        main_layout.setContentsMargins(5, 5, 5, 5)  # Уменьшены отступы

        # Устанавливаем фоновый виджет как центральный
        self.setCentralWidget(self.background)

        # Помещаем нашу компоновку ВНУТРЬ фонового виджета
        layout_for_background = QVBoxLayout(self.background)
        layout_for_background.addWidget(central_layout_widget)

        # Создаем вкладки
        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)

        self.gallery_widget = GalleryWidget(self)
        self.editor_widget = EditorWidget(self)
        self.comparison_view = ComparisonView(self)  # Новое окно сравнения
        self.smart_collections = SmartCollectionsWidget(self)  # Умные коллекции
        self.map_widget = MapWidget(self)  # Вкладка карты

        # Применяем тень к вкладкам для эффекта объема
        try:
            shadow = QGraphicsDropShadowEffect(self)
            shadow.setBlurRadius(25)
            shadow.setColor(QColor(0, 0, 0, 150))
            shadow.setOffset(0, 0)
            self.tab_widget.setGraphicsEffect(shadow)
        except Exception as e:
            logging.error(f"Не удалось применить эффект тени: {e}")

        self.tab_widget.addTab(self.gallery_widget, "Галерея")
        self.tab_widget.addTab(self.smart_collections, "Умные коллекции")
        self.tab_widget.addTab(self.map_widget, "Карта")
        self.tab_widget.addTab(self.comparison_view, "Сравнение")
        self.tab_widget.addTab(self.editor_widget, "Редактирование")

        self._create_actions()
        self._create_menu_bar()
        self._create_tool_bar()
        self._create_status_bar()

        self.gallery_widget.thumbnail_view.itemSelectionChanged.connect(self._update_status_bar)


    # ========== DRAG & DROP ==========
    def dragEnterEvent(self, event):
        """Обработка входа перетаскиваемых файлов"""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.statusBar().showMessage("Отпустите файлы для обработки...")

    def dragLeaveEvent(self, event):
        """Обработка выхода за пределы окна"""
        self.statusBar().showMessage("Готово")

    def dropEvent(self, event):
        """Обработка отпускания файлов"""
        try:
            files = []
            for url in event.mimeData().urls():
                file_path = url.toLocalFile()
                if os.path.isdir(file_path):
                    # Если папка - добавляем все изображения из неё
                    for root, dirs, filenames in os.walk(file_path):
                        for filename in filenames:
                            if filename.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp',
                                                          '.gif', '.tiff', '.webp', '.arw',
                                                          '.cr2', '.nef', '.dng', '.raw')):
                                files.append(os.path.join(root, filename))
                elif os.path.isfile(file_path):
                    if file_path.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp',
                                                   '.gif', '.tiff', '.webp', '.arw',
                                                   '.cr2', '.nef', '.dng', '.raw')):
                        files.append(file_path)

            if files:
                self.files_dropped.emit(files)
                self.statusBar().showMessage(f"Добавлено файлов: {len(files)}")
            else:
                self.statusBar().showMessage("Нет подходящих файлов для обработки")

        except Exception as e:
            self.statusBar().showMessage(f"Ошибка: {e}")

    # ========== HOTKEYS & ACTIONS ==========
    def switch_to_editor(self, image_info: ImageInfo):
        """Переключается на вкладку редактора и загружает изображение"""
        try:
            self.tab_widget.setCurrentWidget(self.editor_widget)
            self.editor_widget.load_image(image_info)
        except Exception as e:
            self.statusBar().showMessage(f"Ошибка загрузки в редактор: {e}")

    def _create_actions(self):
        """Создает действия для меню и панели инструментов"""
        try:
            # Основные действия
            self.delete_action = QAction(QIcon(resource_path("assets/trash-2.png")), "Удалить", self)
            self.copy_action = QAction(QIcon(resource_path("assets/copy.png")), "Копировать в...", self)
            self.move_action = QAction(QIcon(resource_path("assets/move.png")), "Переместить в...", self)
            self.keep_best_action = QAction(QIcon(resource_path("assets/star.png")), "Оставить лучшее...", self)
            self.rotate_action = QAction(QIcon(resource_path("assets/rotate-cw.png")), "Повернуть", self)
            self.exit_action = QAction(QIcon(resource_path("assets/log-out.png")), "Выход", self)
            self.style_action = QAction(QIcon(resource_path("assets/pipette.png")), "Копировать стиль", self)
            self.settings_action = QAction(QIcon(resource_path("assets/settings.png")), "Настройки...", self)
            self.about_action = QAction("О программе WiPhoto", self)

            # Новые действия
            self.compare_action = QAction(QIcon(resource_path("assets/compare.png")), "Сравнить выбранные", self)
            self.fullscreen_action = QAction("Полноэкранный режим", self)
            self.quick_view_action = QAction("Быстрый просмотр", self)
            self.next_image_action = QAction("Следующее фото", self)
            self.prev_image_action = QAction("Предыдущее фото", self)
            self.select_all_action = QAction("Выбрать все", self)
            self.deselect_all_action = QAction("Снять выделение", self)
            self.refresh_action = QAction("Обновить", self)


            # Горячие клавиши
            self.settings_action.setShortcut(QKeySequence("Ctrl+,"))
            self.delete_action.setShortcut(QKeySequence.StandardKey.Delete)
            self.copy_action.setShortcut(QKeySequence.StandardKey.Copy)
            self.move_action.setShortcut(QKeySequence.StandardKey.Cut)
            self.rotate_action.setShortcut(QKeySequence("R"))
            self.exit_action.setShortcut(QKeySequence("Ctrl+Q"))
            self.select_all_action.setShortcut(QKeySequence.StandardKey.SelectAll)
            self.deselect_all_action.setShortcut(QKeySequence("Ctrl+Shift+A"))

            # Новые горячие клавиши
            self.compare_action.setShortcut(QKeySequence("Ctrl+D"))
            self.fullscreen_action.setShortcut(QKeySequence("F11"))
            self.quick_view_action.setShortcut(QKeySequence("Space"))
            self.next_image_action.setShortcut(QKeySequence("Right"))
            self.prev_image_action.setShortcut(QKeySequence("Left"))
            self.refresh_action.setShortcut(QKeySequence("F5"))

            # Подключение сигналов
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

            # Новые подключения
            self.compare_action.triggered.connect(self._on_compare_triggered)
            self.fullscreen_action.triggered.connect(self._toggle_fullscreen)
            self.quick_view_action.triggered.connect(self._quick_view)
            self.next_image_action.triggered.connect(self._next_image)
            self.prev_image_action.triggered.connect(self._prev_image)
            self.refresh_action.triggered.connect(self._refresh_gallery)

            # Добавляем действия в окно
            self.addActions([
                self.delete_action, self.copy_action, self.move_action,
                self.rotate_action, self.exit_action, self.select_all_action,
                self.deselect_all_action, self.settings_action, self.compare_action,
                self.fullscreen_action, self.quick_view_action, self.next_image_action,
                self.prev_image_action, self.refresh_action
            ])
        except Exception as e:
            logging.error(f"Ошибка создания действий: {e}")

    def _create_menu_bar(self):
        """Создает верхнее меню приложения"""
        menu_bar = self.menuBar()
        menu_bar.setStyleSheet("""
            QMenuBar {
                background-color: rgba(30, 35, 45, 0.8);
                padding: 5px;
            }
            QMenuBar::item {
                padding: 5px 10px;
                background: transparent;
                border-radius: 4px;
            }
            QMenuBar::item:selected {
                background-color: rgba(255, 255, 255, 0.1);
            }
        """)

        # Меню "Файл"
        file_menu = menu_bar.addMenu("Файл")
        file_menu.addAction(self.settings_action)
        file_menu.addAction(self.refresh_action)
        file_menu.addSeparator()
        file_menu.addAction(self.exit_action)

        # Меню "Правка"
        edit_menu = menu_bar.addMenu("Правка")
        edit_menu.addAction(self.select_all_action)
        edit_menu.addAction(self.deselect_all_action)

        # Меню "Вид"
        view_menu = menu_bar.addMenu("Вид")
        view_menu.addAction(self.fullscreen_action)
        view_menu.addAction(self.quick_view_action)

        # Меню "Инструменты"
        tools_menu = menu_bar.addMenu("Инструменты")
        tools_menu.addAction(self.compare_action)
        tools_menu.addAction(self.style_action)

        # Меню "Справка"
        help_menu = menu_bar.addMenu("Справка")
        help_menu.addAction(self.about_action)

    def _create_tool_bar(self):
        """Создает панель инструментов"""
        try:
            toolbar = QToolBar("Основные действия")
            self.addToolBar(toolbar)

            toolbar.setStyleSheet("""
                            QToolButton {
                                padding: 5px 8px;
                                margin: 1px;
                                border-radius: 4px;
                            }
                            QToolButton:hover {
                                background-color: rgba(255, 255, 255, 0.1);
                            }
                            QToolButton:checked {
                                background-color: #8A2BE2; /* Яркий фиолетовый цвет, похожий на ваш */
                                color: white;             /* <<<<<<< ГЛАВНОЕ ИЗМЕНЕНИЕ */
                                border: 1px solid #9932CC;
                            }
                        """)

            toolbar.addAction(self.delete_action)
            toolbar.addSeparator()
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
            toolbar.addSeparator()

            # Фильтры
            filter_group = QActionGroup(self)
            filter_group.setExclusive(True)
            all_action = QAction("Все", self, checkable=True, checked=True)
            all_action.triggered.connect(lambda: self.filter_changed.emit("all"))
            best_action = QAction("Лучшие", self, checkable=True)
            best_action.triggered.connect(lambda: self.filter_changed.emit("best"))
            duplicates_action = QAction("Дубликаты", self, checkable=True)
            duplicates_action.triggered.connect(lambda: self.filter_changed.emit("duplicates"))
            filter_group.addAction(all_action)
            filter_group.addAction(best_action)
            filter_group.addAction(duplicates_action)
            toolbar.addActions(filter_group.actions())
            toolbar.addAction(self.exit_action)

            # Слайдер размера миниатюр
            spacer = QWidget()
            spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            toolbar.addWidget(spacer)

            size_slider = QSlider(Qt.Orientation.Horizontal)
            size_slider.setRange(128, 512)
            size_slider.setValue(380)  # Увеличен размер по умолчанию
            size_slider.setFixedWidth(150)
            size_slider.valueChanged.connect(self.thumbnail_size_changed.emit)
            toolbar.addWidget(size_slider)
        except Exception as e:
            logging.error(f"Ошибка создания тулбара: {e}")

    # ========== НОВЫЕ МЕТОДЫ HOTKEYS ==========
    def _on_compare_triggered(self):
        """Обработка запроса сравнения"""
        selected = self._get_selected_image_infos()
        if len(selected) == 2:
            self.compare_requested.emit(selected)
            self.tab_widget.setCurrentWidget(self.comparison_view)
        else:
            self.statusBar().showMessage("Выберите ровно 2 фото для сравнения")

    def _toggle_fullscreen(self):
        """Переключение полноэкранного режима"""
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def _quick_view(self):
        """Быстрый просмотр (Space) — полноэкранный оверлей"""
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
        """Следующее изображение (Right)"""
        view = self.gallery_widget.thumbnail_view
        current = view.currentRow()
        if current < view.count() - 1:
            view.setCurrentRow(current + 1)

    def _prev_image(self):
        """Предыдущее изображение (Left)"""
        view = self.gallery_widget.thumbnail_view
        current = view.currentRow()
        if current > 0:
            view.setCurrentRow(current - 1)

    def _refresh_gallery(self):
        """Обновить галерею (F5)"""
        self.statusBar().showMessage("Обновление галереи...")
        self.refresh_requested.emit()

    def _open_about_dialog(self):
        """Открывает диалог 'О программе'"""
        try:
            dialog = AboutDialog(self)
            dialog.exec()
        except Exception as e:
            logging.error(f"Ошибка открытия диалога О программе: {e}")

    def _create_status_bar(self):
        """Создает строку состояния"""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Готово")

    def enter_style_copy_mode(self, active: bool):
        """Меняет курсор в режиме копирования стиля"""
        self.setCursor(Qt.CursorShape.CrossCursor if active else Qt.CursorShape.ArrowCursor)

    def open_settings_dialog(self):
        """Открывает диалог настроек"""
        try:
            dialog = SettingsDialog(self)
            dialog.exec()
        except Exception as e:
            logging.error(f"Ошибка открытия настроек: {e}")

    def add_thumbnails_batch(self, image_infos: list[ImageInfo]):
        """Добавляет миниатюры пакетом"""
        view = self.gallery_widget.thumbnail_view
        view.setUpdatesEnabled(False)
        try:
            for info in image_infos:
                if info.thumbnail_path and os.path.exists(info.thumbnail_path):
                    try:
                        pixmap = QPixmap(info.thumbnail_path)
                        if not pixmap.isNull():
                            # Play icon overlay for videos
                            if info.is_video():
                                painter = QPainter(pixmap)
                                painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                                cx, cy = pixmap.width() // 2, pixmap.height() // 2
                                painter.setBrush(QColor(0, 0, 0, 160))
                                painter.setPen(Qt.PenStyle.NoPen)
                                painter.drawEllipse(cx - 25, cy - 25, 50, 50)
                                painter.setBrush(QColor(255, 255, 255, 220))
                                triangle = QPolygonF([
                                    QPointF(cx - 10, cy - 15),
                                    QPointF(cx - 10, cy + 15),
                                    QPointF(cx + 15, cy)
                                ])
                                painter.drawPolygon(triangle)
                                painter.end()
                            icon = QIcon(pixmap)
                            item = QListWidgetItem(icon, os.path.basename(info.path))
                            item.setData(Qt.ItemDataRole.UserRole, info)
                            item.setSizeHint(QSize(400, 400))  # Увеличен размер
                            view.addItem(item)
                    except Exception as e:
                        logging.error(f"Ошибка добавления миниатюры: {e}")
        finally:
            view.setUpdatesEnabled(True)

    def update_thumbnail_styles(self):
        """Обновляет стили миниатюр (рамки для дубликатов)"""
        view = self.gallery_widget.thumbnail_view
        try:
            for i in range(view.count()):
                item = view.item(i)
                info = item.data(Qt.ItemDataRole.UserRole)

                if isinstance(info, ImageInfo) and info.thumbnail_path:
                    try:
                        pixmap = QPixmap(info.thumbnail_path)
                        if pixmap.isNull():
                            continue

                        painter = QPainter(pixmap)
                        pen = QPen(Qt.GlobalColor.transparent)

                        if info.is_best_in_group:
                            pen = QPen(QColor("#28a745"), 8)
                        elif info.group_id is not None:
                            pen = QPen(QColor("#ffc107"), 8)

                        painter.setPen(pen)
                        painter.drawRect(pixmap.rect().adjusted(4, 4, -4, -4))
                        painter.end()
                        item.setIcon(QIcon(pixmap))
                    except Exception as e:
                        logging.error(f"Ошибка обновления иконки: {e}")
        except Exception as e:
            logging.error(f"Ошибка обновления выделения: {e}")

    def clear_thumbnails(self):
        """Очищает все миниатюры"""
        self.gallery_widget.thumbnail_view.clear()
        self.clear_preview_and_metadata()

    def rotate_preview(self):
        """Поворачивает превью на 90 градусов"""
        if self.tab_widget.currentWidget() is not self.gallery_widget:
            return

        if self.current_preview_pixmap and not self.current_preview_pixmap.isNull():
            try:
                transform = QTransform().rotate(90)
                self.current_preview_pixmap = self.current_preview_pixmap.transformed(
                    transform,
                    Qt.TransformationMode.SmoothTransformation
                )
                self.gallery_widget.preview_area.setPixmap(
                    self.current_preview_pixmap.scaled(
                        self.gallery_widget.preview_area.size(),
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation
                    )
                )
            except Exception as e:
                logging.error(f"Ошибка изменения размера превью: {e}")

    def set_thumbnail_size(self, size: int):
        """Устанавливает размер миниатюр"""
        try:
            view = self.gallery_widget.thumbnail_view
            view.setIconSize(QSize(size, size))
            view.setGridSize(QSize(size + 20, size + 20))
        except Exception as e:
            logging.error(f"Ошибка установки размера миниатюр: {e}")

    def _get_selected_image_infos(self) -> list[ImageInfo]:
        """Получает список выбранных ImageInfo"""
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
        """Обновляет строку состояния"""
        try:
            total = self.gallery_widget.thumbnail_view.count()
            selected = len(self.gallery_widget.thumbnail_view.selectedItems())
            self.status_bar.showMessage(f"Всего: {total} | Выбрано: {selected}")
        except Exception as e:
            logging.error(f"Ошибка обновления счетчика: {e}")

    def remove_thumbnails(self, infos_to_remove: list[ImageInfo]):
        """Удаляет миниатюры из списка"""
        try:
            paths_to_remove = {info.path for info in infos_to_remove}
            view = self.gallery_widget.thumbnail_view

            for i in reversed(range(view.count())):
                item = view.item(i)
                if item.data(Qt.ItemDataRole.UserRole).path in paths_to_remove:
                    view.takeItem(i)

            self._update_status_bar()
        except Exception as e:
            logging.error(f"Ошибка удаления миниатюр: {e}")

    def show_preview(self, image_path: str):
        """Показывает превью изображения или кадр видео"""
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
                    self.gallery_widget.preview_area.setText("Не удалось загрузить видео")
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

                self.gallery_widget.preview_area.setPixmap(
                    self.current_preview_pixmap.scaled(
                        self.gallery_widget.preview_area.size(),
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation
                    )
                )
            else:
                self.gallery_widget.preview_area.setText("Не удалось загрузить изображение.")

        except Exception as e:
            self.gallery_widget.preview_area.setText(f"Ошибка:\n{e}")

    def update_metadata(self, data: dict):
        """Обновляет таблицу метаданных"""
        try:
            view = self.gallery_widget.metadata_view
            view.setRowCount(0)
            view.setRowCount(len(data))

            for row, (key, value) in enumerate(data.items()):
                view.setItem(row, 0, QTableWidgetItem(key))
                view.setItem(row, 1, QTableWidgetItem(str(value)))
        except Exception as e:
            logging.error(f"Ошибка отображения метаданных: {e}")

    def clear_preview_and_metadata(self):
        """Очищает превью и метаданные"""
        self.gallery_widget.preview_area.setText("Выберите изображение для предпросмотра")
        self.gallery_widget.preview_area.setPixmap(QPixmap())
        self.gallery_widget.metadata_view.setRowCount(0)


    def closeEvent(self, event):
        """Обработка закрытия окна"""
        try:
            if hasattr(self, 'editor_widget'):
                self.editor_widget.close()
            event.accept()
        except Exception as e:
            logging.error(f"Ошибка при закрытии окна: {e}")
            event.accept()


class QuickViewOverlay(QWidget):
    """Полноэкранный оверлей быстрого просмотра (Space)"""

    def __init__(self, parent):
        super().__init__(parent)
        self.setStyleSheet("background-color: rgba(0, 0, 0, 220);")
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
                    self._label.setText("Не удалось загрузить видео")
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
                self._label.setText("Не удалось загрузить изображение")
        except Exception as e:
            self._label.setText(f"Ошибка: {e}")

        self.show()
        self.raise_()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Space, Qt.Key.Key_Escape):
            self.hide()

    def mousePressEvent(self, event):
        self.hide()