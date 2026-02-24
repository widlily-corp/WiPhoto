# views/comparison_view.py

import os
import logging
from PyQt6.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton,
                             QSlider, QGraphicsView, QGraphicsScene, QGraphicsPixmapItem,
                             QSplitter, QToolBar, QFrame)
from PyQt6.QtCore import Qt, pyqtSignal, QRectF
from PyQt6.QtGui import QPixmap, QImage, QWheelEvent, QTransform, QIcon
from PIL import Image
import rawpy

from models.image_model import ImageInfo
from utils import resource_path

RAW_FORMATS = ('.arw', '.cr2', '.nef', '.dng', '.raw')


class SyncedGraphicsView(QGraphicsView):
    """GraphicsView с синхронизированным зумом и прокруткой"""

    zoom_changed = pyqtSignal(float)
    scroll_changed = pyqtSignal(int, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self._zoom_level = 1.0
        self._sync_enabled = True

        # Подключаем синхронизацию скролла
        self.horizontalScrollBar().valueChanged.connect(self._on_scroll_changed)
        self.verticalScrollBar().valueChanged.connect(self._on_scroll_changed)

    def wheelEvent(self, event: QWheelEvent):
        """Обработка зума колесом мыши с Ctrl"""
        if event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            zoom_factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
            self.apply_zoom(zoom_factor)
            if self._sync_enabled:
                self.zoom_changed.emit(zoom_factor)
        else:
            super().wheelEvent(event)

    def apply_zoom(self, factor: float):
        """Применяет зум"""
        self._zoom_level *= factor
        self.scale(factor, factor)

    def reset_zoom(self):
        """Сбрасывает зум"""
        self.resetTransform()
        self._zoom_level = 1.0

    def fit_in_view(self):
        """Вписывает изображение в окно"""
        if self.scene() and self.scene().items():
            self.fitInView(self.scene().itemsBoundingRect(), Qt.AspectRatioMode.KeepAspectRatio)
            self._zoom_level = self.transform().m11()

    def _on_scroll_changed(self):
        """Обработка изменения скролла"""
        if self._sync_enabled:
            h_val = self.horizontalScrollBar().value()
            v_val = self.verticalScrollBar().value()
            self.scroll_changed.emit(h_val, v_val)

    def set_scroll_position(self, h_val: int, v_val: int):
        """Устанавливает позицию скролла без запуска сигнала"""
        self._sync_enabled = False
        self.horizontalScrollBar().setValue(h_val)
        self.verticalScrollBar().setValue(v_val)
        self._sync_enabled = True


class ComparisonView(QWidget):
    """Виджет для сравнения двух изображений side-by-side"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.image1_info = None
        self.image2_info = None
        self.pixmap1_item = None
        self.pixmap2_item = None

        self._init_ui()

    def _init_ui(self):
        """Инициализация интерфейса"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Панель инструментов
        self.toolbar = self._create_toolbar()
        main_layout.addWidget(self.toolbar)

        # Основная область сравнения
        content_widget = QWidget()
        content_layout = QHBoxLayout(content_widget)
        content_layout.setContentsMargins(5, 5, 5, 5)

        # Левая панель
        left_panel = self._create_image_panel("Изображение 1")
        self.scene1 = QGraphicsScene()
        self.view1 = SyncedGraphicsView()
        self.view1.setScene(self.scene1)
        # Устанавливаем фон для области просмотра
        self.view1.setStyleSheet("QGraphicsView { background-color: #23283a; border-radius: 8px; }")
        self.label1 = left_panel[0]
        self.info_label1 = left_panel[1]
        left_container = left_panel[2]
        left_container.layout().addWidget(self.view1)

        # Правая панель
        right_panel = self._create_image_panel("Изображение 2")
        self.scene2 = QGraphicsScene()
        self.view2 = SyncedGraphicsView()
        self.view2.setScene(self.scene2)
        # Устанавливаем фон для области просмотра
        self.view2.setStyleSheet("QGraphicsView { background-color: #23283a; border-radius: 8px; }")
        self.label2 = right_panel[0]
        self.info_label2 = right_panel[1]
        right_container = right_panel[2]
        right_container.layout().addWidget(self.view2)

        # Сплиттер для изменения размера панелей
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left_container)
        splitter.addWidget(right_container)
        splitter.setSizes([800, 800])

        content_layout.addWidget(splitter)
        main_layout.addWidget(content_widget)

        # Синхронизация зума и скролла
        self._connect_sync()

    def _create_toolbar(self) -> QToolBar:
        """Создает панель инструментов"""
        toolbar = QToolBar("Сравнение")
        # Устанавливаем прозрачный фон для тулбара
        toolbar.setStyleSheet("QToolBar { background-color: transparent; border-bottom: 1px solid rgba(255, 255, 255, 0.1); }")

        # Кнопки управления
        self.sync_zoom_btn = QPushButton("🔗 Синхронизировать зум")
        self.sync_zoom_btn.setCheckable(True)
        self.sync_zoom_btn.setChecked(True)
        self.sync_zoom_btn.clicked.connect(self._toggle_sync_zoom)
        toolbar.addWidget(self.sync_zoom_btn)

        toolbar.addSeparator()

        self.fit_view_btn = QPushButton("По размеру окна")
        self.fit_view_btn.clicked.connect(self._fit_both_views)
        toolbar.addWidget(self.fit_view_btn)

        self.zoom_100_btn = QPushButton("100%")
        self.zoom_100_btn.clicked.connect(self._reset_both_zoom)
        toolbar.addWidget(self.zoom_100_btn)

        toolbar.addSeparator()

        self.swap_btn = QPushButton("⇄ Поменять местами")
        self.swap_btn.clicked.connect(self._swap_images)
        toolbar.addWidget(self.swap_btn)

        toolbar.addSeparator()

        # Информация о различиях
        self.diff_label = QLabel("Выберите изображения для сравнения")
        toolbar.addWidget(self.diff_label)

        return toolbar

    def _create_image_panel(self, title: str):
        """Создает панель для одного изображения"""
        container = QFrame()
        container.setFrameShape(QFrame.Shape.StyledPanel)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(5, 5, 5, 5)

        # Заголовок
        title_label = QLabel(title)
        title_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)

        # Информация об изображении
        info_label = QLabel("Не загружено")
        info_label.setStyleSheet("color: #888;")
        info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(info_label)

        return title_label, info_label, container

    def _connect_sync(self):
        """Подключает синхронизацию между двумя view"""
        self.view1.zoom_changed.connect(lambda factor: self.view2.apply_zoom(factor))
        self.view2.zoom_changed.connect(lambda factor: self.view1.apply_zoom(factor))

        self.view1.scroll_changed.connect(lambda h, v: self.view2.set_scroll_position(h, v))
        self.view2.scroll_changed.connect(lambda h, v: self.view1.set_scroll_position(h, v))

    def _toggle_sync_zoom(self, checked: bool):
        """Переключает синхронизацию зума"""
        self.view1._sync_enabled = checked
        self.view2._sync_enabled = checked
        self.sync_zoom_btn.setText("🔗 Синхронизировать зум" if checked else "🔓 Независимый зум")

    def _fit_both_views(self):
        """Вписывает оба изображения в окна"""
        self.view1.fit_in_view()
        self.view2.fit_in_view()

    def _reset_both_zoom(self):
        """Сбрасывает зум обоих изображений"""
        self.view1.reset_zoom()
        self.view2.reset_zoom()

    def _swap_images(self):
        """Меняет изображения местами"""
        if not self.image1_info or not self.image2_info:
            return

        # Меняем данные
        self.image1_info, self.image2_info = self.image2_info, self.image1_info

        # Меняем сцены
        temp_scene = self.scene1
        self.scene1 = self.scene2
        self.scene2 = temp_scene

        self.view1.setScene(self.scene1)
        self.view2.setScene(self.scene2)

        # Обновляем метки
        self._update_info_labels()

    def load_images(self, image_infos: list[ImageInfo]):
        """Загружает два изображения для сравнения"""
        if len(image_infos) != 2:
            self.diff_label.setText("Ошибка: нужно ровно 2 изображения")
            return

        self.image1_info = image_infos[0]
        self.image2_info = image_infos[1]

        # Загружаем изображения
        pixmap1 = self._load_pixmap(self.image1_info.path)
        pixmap2 = self._load_pixmap(self.image2_info.path)

        if not pixmap1 or not pixmap2:
            self.diff_label.setText("Ошибка загрузки изображений")
            return

        # Обновляем сцены
        self.scene1.clear()
        self.scene2.clear()

        self.pixmap1_item = self.scene1.addPixmap(pixmap1)
        self.pixmap2_item = self.scene2.addPixmap(pixmap2)

        self.scene1.setSceneRect(self.pixmap1_item.boundingRect())
        self.scene2.setSceneRect(self.pixmap2_item.boundingRect())

        # Вписываем в окна
        self._fit_both_views()

        # Обновляем информацию
        self._update_info_labels()
        self._calculate_differences()

    def _load_pixmap(self, image_path: str) -> QPixmap:
        """Загружает изображение как QPixmap"""
        try:
            is_raw = image_path.lower().endswith(RAW_FORMATS)

            if is_raw:
                with rawpy.imread(image_path) as raw:
                    rgb = raw.postprocess(use_camera_wb=True, output_bps=8)
                pil_image = Image.fromarray(rgb)
            else:
                pil_image = Image.open(image_path)

            if pil_image.mode != 'RGB':
                pil_image = pil_image.convert('RGB')

            q_image = QImage(
                pil_image.tobytes(),
                pil_image.width,
                pil_image.height,
                pil_image.width * 3,
                QImage.Format.Format_RGB888
            )

            return QPixmap.fromImage(q_image)

        except Exception as e:
            logging.error(f"Ошибка загрузки изображения {image_path}: {e}")
            return None

    def _update_info_labels(self):
        """Обновляет информационные метки"""
        if self.image1_info:
            name1 = os.path.basename(self.image1_info.path)
            size1 = os.path.getsize(self.image1_info.path) / (1024 * 1024)  # MB
            self.info_label1.setText(f"{name1}\n{size1:.2f} MB")

        if self.image2_info:
            name2 = os.path.basename(self.image2_info.path)
            size2 = os.path.getsize(self.image2_info.path) / (1024 * 1024)  # MB
            self.info_label2.setText(f"{name2}\n{size2:.2f} MB")

    def _calculate_differences(self):
        """Вычисляет и отображает различия между изображениями"""
        if not self.image1_info or not self.image2_info:
            return

        try:
            # Размеры
            if self.pixmap1_item and self.pixmap2_item:
                size1 = self.pixmap1_item.pixmap().size()
                size2 = self.pixmap2_item.pixmap().size()

                size_diff = ""
                if size1 != size2:
                    size_diff = f"Разрешение: {size1.width()}×{size1.height()} vs {size2.width()}×{size2.height()}"

            # Резкость (если есть)
            sharpness_diff = ""
            if hasattr(self.image1_info, 'sharpness') and hasattr(self.image2_info, 'sharpness'):
                if self.image1_info.sharpness > 0 and self.image2_info.sharpness > 0:
                    diff_percent = abs(self.image1_info.sharpness - self.image2_info.sharpness) / max(
                        self.image1_info.sharpness, self.image2_info.sharpness) * 100
                    better = "←" if self.image1_info.sharpness > self.image2_info.sharpness else "→"
                    sharpness_diff = f"Резкость: {diff_percent:.1f}% {better}"

            # Размер файла
            file_size1 = os.path.getsize(self.image1_info.path) / (1024 * 1024)
            file_size2 = os.path.getsize(self.image2_info.path) / (1024 * 1024)
            size_diff_mb = abs(file_size1 - file_size2)

            # Формируем итоговое сообщение
            diff_parts = []
            if size_diff:
                diff_parts.append(size_diff)
            if sharpness_diff:
                diff_parts.append(sharpness_diff)
            diff_parts.append(f"Размер файлов: ±{size_diff_mb:.2f} MB")

            self.diff_label.setText(" | ".join(diff_parts))

        except Exception as e:
            self.diff_label.setText("Ошибка анализа")