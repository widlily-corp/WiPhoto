# views/map_widget.py

import logging
from datetime import datetime
from collections import defaultdict
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QListWidget,
                             QLabel, QListWidgetItem, QAbstractItemView, QSplitter,
                             QTextEdit, QPushButton, QMenu)
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QIcon, QPixmap
from models.image_model import ImageInfo
import os
import subprocess
import platform


class MapWidget(QWidget):
    """Вкладка 'Карта' - показывает изображения с GPS координатами"""

    image_selected = pyqtSignal(ImageInfo)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.all_images = []
        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)

        # Заголовок
        header = QLabel("Карта изображений с геотегами")
        header.setStyleSheet("font-size: 18px; font-weight: bold; padding: 15px;")
        main_layout.addWidget(header)

        # Splitter для разделения списка и деталей
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Левая панель - список изображений с GPS
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)

        self.stats_label = QLabel("Изображений с GPS: 0")
        self.stats_label.setStyleSheet("padding: 10px; color: #888;")
        left_layout.addWidget(self.stats_label)

        self.images_list = QListWidget()
        self.images_list.setViewMode(QListWidget.ViewMode.IconMode)
        self.images_list.setIconSize(QSize(150, 150))
        self.images_list.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.images_list.setSpacing(10)
        self.images_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.images_list.setStyleSheet("QListWidget { background-color: #23283a; border-radius: 8px; }")
        self.images_list.itemClicked.connect(self._on_image_selected)
        self.images_list.itemDoubleClicked.connect(self._on_image_double_clicked)
        self.images_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.images_list.customContextMenuRequested.connect(self._show_context_menu)
        left_layout.addWidget(self.images_list)

        # Правая панель - детали
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)

        self.details_title = QLabel("Выберите изображение")
        self.details_title.setStyleSheet("font-size: 14px; font-weight: bold; padding: 10px;")
        right_layout.addWidget(self.details_title)

        # Превью изображения
        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setMinimumHeight(300)
        self.preview_label.setStyleSheet("background-color: #1e1e1e; border-radius: 8px;")
        self.preview_label.setScaledContents(False)
        right_layout.addWidget(self.preview_label)

        # Информация о координатах
        self.info_text = QTextEdit()
        self.info_text.setReadOnly(True)
        self.info_text.setMaximumHeight(200)
        self.info_text.setStyleSheet("""
            QTextEdit {
                background-color: #23283a;
                border-radius: 8px;
                padding: 10px;
                color: white;
            }
        """)
        right_layout.addWidget(self.info_text)

        # Кнопка открытия на карте
        self.open_map_button = QPushButton("Открыть на карте (Google Maps)")
        self.open_map_button.setEnabled(False)
        self.open_map_button.clicked.connect(self._open_in_google_maps)
        self.open_map_button.setStyleSheet("""
            QPushButton {
                background-color: #0078d4;
                color: white;
                padding: 10px;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0086f0;
            }
            QPushButton:disabled {
                background-color: #444;
                color: #888;
            }
        """)
        right_layout.addWidget(self.open_map_button)

        # Добавляем панели в splitter
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)

        main_layout.addWidget(splitter)

        self.selected_info = None

    def set_images(self, images: list[ImageInfo]):
        """Устанавливает список изображений и фильтрует те, что с GPS"""
        self.all_images = images
        self._update_display()

    def _update_display(self):
        """Обновляет отображение изображений с GPS"""
        self.images_list.clear()

        # Фильтруем изображения с GPS
        gps_images = [img for img in self.all_images if img.gps_location is not None]

        # Группируем по датам
        grouped_by_date = defaultdict(list)
        for img in gps_images:
            try:
                mtime = os.path.getmtime(img.path)
                file_date = datetime.fromtimestamp(mtime).date()
                grouped_by_date[file_date].append(img)
            except Exception as e:
                logging.error(f"Ошибка получения даты для {img.path}: {e}")

        # Сортируем даты в обратном порядке (новые сверху)
        sorted_dates = sorted(grouped_by_date.keys(), reverse=True)

        # Добавляем изображения по группам
        for date in sorted_dates:
            # Добавляем разделитель с датой
            date_item = QListWidgetItem(f"📅 {date.strftime('%d.%m.%Y')}")
            date_item.setFlags(Qt.ItemFlag.NoItemFlags)
            date_item.setBackground(Qt.GlobalColor.darkGray)
            self.images_list.addItem(date_item)

            # Добавляем изображения этой даты
            for img in grouped_by_date[date]:
                if img.thumbnail_path and os.path.exists(img.thumbnail_path):
                    try:
                        pixmap = QPixmap(img.thumbnail_path)
                        if not pixmap.isNull():
                            icon = QIcon(pixmap)
                            lat, lon = img.gps_location
                            item_text = f"{os.path.basename(img.path)}\n{lat:.4f}, {lon:.4f}"
                            item = QListWidgetItem(icon, item_text)
                            item.setData(Qt.ItemDataRole.UserRole, img)
                            item.setSizeHint(QSize(170, 190))
                            self.images_list.addItem(item)
                    except Exception as e:
                        logging.error(f"Ошибка загрузки изображения: {e}")

        self.stats_label.setText(f"Изображений с GPS: {len(gps_images)}")

    def _on_image_selected(self, item: QListWidgetItem):
        """Обработка выбора изображения"""
        info = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(info, ImageInfo):
            return

        self.selected_info = info
        self.details_title.setText(f"📍 {os.path.basename(info.path)}")

        # Показываем превью
        if info.thumbnail_path and os.path.exists(info.thumbnail_path):
            pixmap = QPixmap(info.thumbnail_path)
            scaled_pixmap = pixmap.scaled(400, 400, Qt.AspectRatioMode.KeepAspectRatio,
                                         Qt.TransformationMode.SmoothTransformation)
            self.preview_label.setPixmap(scaled_pixmap)

        # Показываем информацию
        if info.gps_location:
            lat, lon = info.gps_location
            info_html = f"""
            <h3>GPS Координаты:</h3>
            <p><b>Широта:</b> {lat:.6f}</p>
            <p><b>Долгота:</b> {lon:.6f}</p>
            <p><b>Ссылка:</b> <a href="https://www.google.com/maps?q={lat},{lon}">
            Google Maps</a></p>
            <hr>
            <p><b>Файл:</b> {info.path}</p>
            """
            if info.faces_count > 0:
                info_html += f"<p><b>Лиц:</b> {info.faces_count}</p>"
            if info.animals_count > 0:
                info_html += f"<p><b>Животных:</b> {info.animals_count}</p>"

            self.info_text.setHtml(info_html)
            self.open_map_button.setEnabled(True)

    def _on_image_double_clicked(self, item: QListWidgetItem):
        """Обработка двойного клика - открываем в редакторе"""
        info = item.data(Qt.ItemDataRole.UserRole)
        if isinstance(info, ImageInfo):
            self.image_selected.emit(info)

    def _open_in_google_maps(self):
        """Открывает локацию на Google Maps"""
        if self.selected_info and self.selected_info.gps_location:
            lat, lon = self.selected_info.gps_location
            url = f"https://www.google.com/maps?q={lat},{lon}"
            import webbrowser
            webbrowser.open(url)

    def _show_context_menu(self, position):
        """Показывает контекстное меню"""
        item = self.images_list.itemAt(position)
        if not item:
            return

        info = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(info, ImageInfo):
            return

        menu = QMenu(self)
        open_maps = menu.addAction("🌍 Открыть на Google Maps")
        open_file = menu.addAction("📂 Открыть в проводнике")
        edit_action = menu.addAction("✏️ Редактировать")

        action = menu.exec(self.images_list.mapToGlobal(position))

        if action == open_maps:
            self._open_in_google_maps()
        elif action == open_file:
            self._open_in_explorer(info)
        elif action == edit_action:
            self._on_image_double_clicked(item)

    def _open_in_explorer(self, info: ImageInfo):
        """Открывает файл в проводнике"""
        if platform.system() == "Windows":
            subprocess.run(['explorer', '/select,', os.path.normpath(info.path)])
        elif platform.system() == "Darwin":
            subprocess.run(['open', '-R', info.path])
        else:
            subprocess.run(['xdg-open', os.path.dirname(info.path)])
