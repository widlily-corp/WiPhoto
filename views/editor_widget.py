
# views/editor_widget.py

import os
from collections import OrderedDict
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGraphicsView, QGraphicsScene,
                             QGraphicsPixmapItem, QToolBar, QFileDialog, QMessageBox, QSplitter,
                             QToolButton, QTabWidget)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QPixmap, QImage, QAction, QIcon, QPainter, QWheelEvent, QActionGroup
from PIL import Image
import rawpy

from models.image_model import ImageInfo, RAW_EXTENSIONS
from utils import resource_path
from views.control_panel_widget import ControlPanelWidget
from views.history_tree_widget import HistoryTreeWidget, CompactHistoryWidget
from core.editing.image_processor import ImageProcessor
from core.editing.tool_rotation import RotationTool
# Импортируем карту всех инструментов и списки
from core.editing import TOOL_GROUPS, MODAL_TOOLS, ACTION_TOOLS, ALL_TOOLS_MAP

MAX_HISTORY_SIZE = 50

class ZoomableView(QGraphicsView):
    def __init__(self, editor: 'EditorWidget', parent=None):
        super().__init__(parent)
        self.editor = editor
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)

    def wheelEvent(self, event: QWheelEvent):
        if event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            zoom_factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
            self.editor._set_zoom(zoom_factor)
        else:
            super().wheelEvent(event)


class EditorWidget(QWidget):
    back_to_gallery = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_image_info = None
        self.processor: ImageProcessor = None
        self.current_pixmap_item = None
        self.history = []
        self.history_index = -1
        self.active_modal_tool = None
        self.update_timer = QTimer()
        self.update_timer.setSingleShot(True)
        self.update_timer.setInterval(250)
        self.update_timer.timeout.connect(self._on_update_finished)
        self._init_ui()
        self._load_tools()
        self._populate_ui_with_tools()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Верхняя панель инструментов - более компактная
        self.toolbar = QToolBar("Панель редактирования")
        self.toolbar.setStyleSheet("""
            QToolBar {
                background-color: rgba(22, 27, 34, 0.8);
                border-bottom: 1px solid rgba(48, 54, 61, 0.5);
                padding: 4px;
                spacing: 6px;
            }
        """)
        main_layout.addWidget(self.toolbar)

        # Основная область с тремя панелями
        content_splitter = QSplitter(Qt.Orientation.Horizontal)

        # --- ЛЕВАЯ ПАНЕЛЬ: Вертикальная панель инструментов ---
        left_panel = QWidget()
        left_panel.setStyleSheet("""
            QWidget {
                background-color: rgba(22, 27, 34, 0.7);
                border-right: 1px solid rgba(48, 54, 61, 0.5);
                border-radius: 0px;
            }
        """)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(8, 8, 8, 8)
        left_layout.setSpacing(8)

        # Компактная история сверху
        self.compact_history = CompactHistoryWidget()
        self.compact_history.undo_requested.connect(self.undo)
        self.compact_history.redo_requested.connect(self.redo)
        left_layout.addWidget(self.compact_history)

        # Панель контролов
        self.control_panel = ControlPanelWidget(self)
        self.control_panel.setStyleSheet("""
            QWidget {
                background-color: transparent;
            }
        """)
        left_layout.addWidget(self.control_panel)
        left_panel.setMaximumWidth(320)  # Фиксированная ширина для вертикальной панели

        # --- ЦЕНТРАЛЬНАЯ ПАНЕЛЬ: Холст (большая область редактирования) ---
        self.scene = QGraphicsScene(self)
        self.view = ZoomableView(editor=self)
        self.view.setScene(self.scene)
        # Современный стиль для области редактирования
        self.view.setStyleSheet("""
            QGraphicsView {
                background-color: rgba(13, 17, 23, 0.9);
                border: 1px solid rgba(48, 54, 61, 0.5);
                border-radius: 12px;
            }
        """)

        # --- ПРАВАЯ ПАНЕЛЬ: Детальная история (компактная) ---
        right_panel = QTabWidget()
        right_panel.setStyleSheet("""
            QTabWidget {
                background-color: transparent;
            }
            QTabWidget::pane {
                background-color: rgba(22, 27, 34, 0.7);
                border: 1px solid rgba(48, 54, 61, 0.5);
                border-radius: 10px;
            }
        """)

        self.history_tree = HistoryTreeWidget()
        self.history_tree.jump_to_state.connect(self._jump_to_history_state)
        self.history_tree.history_cleared.connect(self._on_history_cleared)
        right_panel.addTab(self.history_tree, "История")
        right_panel.setMaximumWidth(280)

        # Добавляем панели в splitter с акцентом на большую область редактирования
        content_splitter.addWidget(left_panel)
        content_splitter.addWidget(self.view)
        content_splitter.addWidget(right_panel)
        content_splitter.setSizes([320, 1200, 280])  # Больше места для холста

        main_layout.addWidget(content_splitter)

    def _load_tools(self):
        self.tools = {name: tool() for name, tool in ALL_TOOLS_MAP.items()}

    def _populate_ui_with_tools(self):
        button_style = """
            QToolButton {
                padding: 8px;
                border: 1px solid rgba(240, 246, 252, 0.1);
                border-radius: 8px;
                background-color: rgba(22, 27, 34, 0.6);
                color: #c9d1d9;
            }
            QToolButton:hover {
                border: 1px solid rgba(88, 166, 255, 0.5);
                background-color: rgba(56, 139, 253, 0.15);
            }
            QToolButton:checked {
                background-color: rgba(88, 166, 255, 0.3);
                border: 1px solid rgba(88, 166, 255, 0.8);
                color: #ffffff;
            }
            QToolButton:pressed {
                background-color: rgba(31, 111, 235, 0.4);
            }
        """
        actions_to_style = []

        # Основные действия
        self.back_action = QAction("← Галерея", self)
        self.back_action.setShortcut("Escape")
        self.back_action.triggered.connect(self.back_to_gallery.emit)
        self.toolbar.addAction(self.back_action)
        self.toolbar.addSeparator()

        self.save_action = QAction(QIcon(resource_path("assets/save.png")), "Сохранить как...", self)
        self.save_action.setShortcut("Ctrl+S")
        self.undo_action = QAction(QIcon(resource_path("assets/undo.png")), "Отменить", self)
        self.undo_action.setShortcut("Ctrl+Z")
        self.redo_action = QAction(QIcon(resource_path("assets/redo.png")), "Повторить", self)
        self.redo_action.setShortcut("Ctrl+Y")
        self.save_action.triggered.connect(self._save_image)
        self.undo_action.triggered.connect(self.undo)
        self.redo_action.triggered.connect(self.redo)
        self.toolbar.addAction(self.save_action)
        self.toolbar.addSeparator()
        self.toolbar.addAction(self.undo_action)
        self.toolbar.addAction(self.redo_action)
        actions_to_style.extend([self.save_action, self.undo_action, self.redo_action])

        # Зум
        self.toolbar.addSeparator()
        self.zoom_in_action = QAction(QIcon(resource_path("assets/zoom-in.png")), "Приблизить", self)
        self.zoom_in_action.setShortcut("Ctrl+=")
        self.zoom_out_action = QAction(QIcon(resource_path("assets/zoom-out.png")), "Отдалить", self)
        self.zoom_out_action.setShortcut("Ctrl+-")
        self.fit_view_action = QAction(QIcon(resource_path("assets/zoom-fit.png")), "Подогнать по размеру", self)
        self.fit_view_action.setShortcut("Ctrl+0")
        self.actual_size_action = QAction(QIcon(resource_path("assets/zoom-100.png")), "Реальный размер (100%)", self)
        self.actual_size_action.setShortcut("Ctrl+1")
        self.toolbar.addSeparator()
        self.before_after_action = QAction("До/После", self)
        self.before_after_action.setCheckable(True)
        self.before_after_action.setToolTip("Сравнение до/после (разделённый вид)")
        self.before_after_action.triggered.connect(self._toggle_before_after)
        self.toolbar.addAction(self.before_after_action)
        self._before_after_mode = False
        self._split_pos = 0.5  # 0.0 - 1.0

        self.zoom_in_action.triggered.connect(lambda: self._set_zoom(1.25))
        self.zoom_out_action.triggered.connect(lambda: self._set_zoom(0.8))
        self.fit_view_action.triggered.connect(self._fit_to_view)
        self.actual_size_action.triggered.connect(self._zoom_actual_size)
        self.toolbar.addAction(self.zoom_in_action)
        self.toolbar.addAction(self.zoom_out_action)
        self.toolbar.addAction(self.fit_view_action)
        self.toolbar.addAction(self.actual_size_action)
        actions_to_style.extend(
            [self.zoom_in_action, self.zoom_out_action, self.fit_view_action, self.actual_size_action])

        # Трансформации
        self.toolbar.addSeparator()
        modal_tools_group = QActionGroup(self)
        modal_tools_group.setExclusive(True)
        all_transform_tools = MODAL_TOOLS + ACTION_TOOLS
        for tool_class in all_transform_tools:
            # Получаем экземпляр инструмента, который мы уже создали в _load_tools
            # У инструмента есть свойство name, используем его для поиска
            temp_tool = tool_class()
            tool_name = temp_tool.name
            tool_instance = self.tools[tool_name]

            icon_path = resource_path(f"assets/{tool_instance.name}.png")
            # Если иконки нет, ставим заглушку, чтобы не падало
            if not os.path.exists(icon_path):
                icon_path = resource_path("assets/icon.ico")

            icon = QIcon(icon_path)
            action = QAction(icon, tool_instance.label, self)
            actions_to_style.append(action)

            if tool_class in MODAL_TOOLS:
                action.setCheckable(True)
                action.triggered.connect(
                    lambda checked, name=tool_instance.name: self._toggle_modal_tool(name, checked))
                modal_tools_group.addAction(action)
            else:
                action.triggered.connect(lambda checked=False, name=tool_instance.name: self._apply_action_tool(name))
            self.toolbar.addAction(action)

        for action in actions_to_style:
            widget = self.toolbar.widgetForAction(action)
            if isinstance(widget, QToolButton):
                widget.setStyleSheet(button_style)

        self._update_history_buttons()
        for group_name, tool_names in TOOL_GROUPS.items():
            tool_instances = [self.tools[name] for name in tool_names if name in self.tools]
            if tool_instances:
                self.control_panel.add_tool_group(group_name, tool_instances)
        for tool in self.tools.values():
            tool.valueChanged.connect(self._on_adjustment_changed)
        self.control_panel.reset_all_requested.connect(self._reset_all)

    def _set_zoom(self, factor: float):
        self.view.scale(factor, factor)

    def _fit_to_view(self):
        if self.current_pixmap_item:
            self.view.fitInView(self.current_pixmap_item, Qt.AspectRatioMode.KeepAspectRatio)

    def _zoom_actual_size(self):
        self.view.resetTransform()

    def _apply_action_tool(self, tool_name: str):
        if not self.processor:
            return
        tool = self.tools[tool_name]
        current_image = self.processor.process(is_preview=False)
        new_base_image = tool.apply(current_image)
        self.processor = ImageProcessor(new_base_image)
        state = self.processor.get_state()
        state[tool_name] = {'applied': True}
        self._add_to_history(state)
        self._render_image()

    def load_image(self, image_info: ImageInfo):
        self._deactivate_current_modal_tool()
        try:
            self.current_image_info = image_info
            path = image_info.path
            pil_image = self._load_pil_image(path)
            if pil_image:
                self.processor = ImageProcessor(pil_image)
                self._reset_all()
            else:
                QMessageBox.critical(self, "Ошибка", "Не удалось загрузить изображение.")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка загрузки", f"Не удалось загрузить изображение:\n{e}")

    def _on_rotation_preview(self, angle: float):
        if self.current_pixmap_item:
            center = self.current_pixmap_item.boundingRect().center()
            self.current_pixmap_item.setTransformOriginPoint(center)
            self.current_pixmap_item.setRotation(angle)

    def _deactivate_current_modal_tool(self):
        if not self.active_modal_tool:
            return
        if isinstance(self.active_modal_tool, RotationTool):
            try:
                self.active_modal_tool.live_update.disconnect(self._on_rotation_preview)
            except TypeError:
                pass
        try:
            self.active_modal_tool.applied.disconnect()
            self.active_modal_tool.cancelled.disconnect()
        except TypeError:
            pass
        self.active_modal_tool.deactivate(self.scene)
        self.control_panel.hide_modal_tool_ui()

        # <<< ИСПРАВЛЕНИЕ: Мы не удаляем виджет, так как он может переиспользоваться инструментом.
        # Вместо этого ControlPanel просто убирает его из layout.
        # if self.active_modal_tool._ui_widget:
        #    self.active_modal_tool._ui_widget.deleteLater()
        #    self.active_modal_tool._ui_widget = None

        self.active_modal_tool = None
        for action in self.toolbar.actions():
            if action.isCheckable():
                action.setChecked(False)
        self._render_image()

    def _load_pil_image(self, path: str) -> Image:
        if path.lower().endswith(RAW_EXTENSIONS):
            with rawpy.imread(path) as raw:
                rgb = raw.postprocess(use_camera_wb=True, output_bps=8)
            return Image.fromarray(rgb)
        else:
            img = Image.open(path)
            return img.convert('RGB') if img.mode != 'RGB' else img

    def _on_adjustment_changed(self, tool_name, param_name, value, is_preview):
        if not self.processor:
            return
        self.processor.set_tool_param(tool_name, param_name, value)
        if is_preview:
            self._render_image(preview=True)
            self.update_timer.start()
        else:
            self.update_timer.stop()
            self._on_update_finished()

    def _on_update_finished(self):
        if not self.processor:
            return
        self._render_image(preview=False)
        self._add_to_history(self.processor.get_state())

    def _toggle_modal_tool(self, tool_name: str, is_active: bool):
        if not is_active:
            if self.active_modal_tool and self.active_modal_tool.name == tool_name:
                self._deactivate_current_modal_tool()
            return

        self._deactivate_current_modal_tool()
        tool = self.tools.get(tool_name)
        if tool and self.current_pixmap_item:
            self.active_modal_tool = tool
            image_rect = self.current_pixmap_item.boundingRect()

            # <<< ВАЖНО: Сначала получаем UI, чтобы инструмент инициализировал свои кнопки
            tool_ui = tool.get_ui()
            self.control_panel.show_modal_tool_ui(tool_ui)

            # --- ХАК ДЛЯ SMART RETOUCH ---
            # Теперь, когда UI создан, мы можем безопасно обращаться к кнопкам
            if tool_name == 'smart_retouch':
                try:
                    # Отключаем дефолтные сигналы, чтобы не дублировать
                    tool.apply_btn.clicked.disconnect()
                except Exception:
                    pass
                # Подключаем наш метод, который имеет доступ к изображению
                tool.apply_btn.clicked.connect(lambda: self._run_smart_retouch(tool))
            # -----------------------------

            tool.activate(self.scene, image_rect)
            tool.applied.connect(self._apply_modal_tool_changes)
            tool.cancelled.connect(self._deactivate_current_modal_tool)
            if isinstance(tool, RotationTool):
                tool.live_update.connect(self._on_rotation_preview)

    def _run_smart_retouch(self, tool):
        """Запускает процесс ретуши, передавая текущее изображение"""
        if not self.processor:
            return
        # Получаем текущее состояние картинки (со всеми фильтрами)
        # Важно передать False для is_preview, чтобы отправить качественное фото (или True для скорости)
        current_img = self.processor.process(is_preview=False)
        tool.process_with_image(current_img)

    def _apply_modal_tool_changes(self):
        if not self.active_modal_tool:
            return
        self._on_rotation_preview(0)

        # Получаем текущее состояние
        current_image = self.processor.process(is_preview=False)

        # Применяем инструмент
        new_base_image = self.active_modal_tool.apply(current_image)

        # Обновляем базу процессора
        self.processor = ImageProcessor(new_base_image)

        tool_name = self.active_modal_tool.name
        self._deactivate_current_modal_tool()

        state = self.processor.get_state()
        state[tool_name] = {'applied': True}
        self._add_to_history(state)
        self._render_image()

    def _toggle_before_after(self, checked):
        self._before_after_mode = checked
        self._render_image()

    def _render_image(self, preview=False):
        if not self.processor:
            return
        processed_image = self.processor.process(is_preview=preview)

        if self._before_after_mode and self.processor.original_image:
            pixmap = self._create_split_pixmap(self.processor.original_image, processed_image)
        else:
            pixmap = self._pil_to_pixmap(processed_image)
        self._update_scene(pixmap)

    def _create_split_pixmap(self, original: Image.Image, edited: Image.Image) -> QPixmap:
        """Create a side-by-side split comparison image"""
        w, h = edited.size
        split_x = int(w * self._split_pos)

        result = original.copy()
        # Paste edited portion on the right side
        right_crop = edited.crop((split_x, 0, w, h))
        result.paste(right_crop, (split_x, 0))

        # Draw split line
        from PIL import ImageDraw
        draw = ImageDraw.Draw(result)
        draw.line([(split_x, 0), (split_x, h)], fill=(255, 255, 255), width=2)

        # Labels
        try:
            from PIL import ImageFont
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", max(14, h // 40))
        except Exception:
            font = ImageFont.load_default()

        draw.text((10, 10), "ДО", fill=(255, 255, 255), font=font)
        draw.text((split_x + 10, 10), "ПОСЛЕ", fill=(255, 255, 255), font=font)

        return self._pil_to_pixmap(result)

    def _add_to_history(self, state: OrderedDict):
        if self.history_index > -1 and state == self.history[self.history_index]:
            return
        if self.history_index < len(self.history) - 1:
            self.history = self.history[:self.history_index + 1]
        self.history.append(state)
        self.history_index += 1
        if len(self.history) > MAX_HISTORY_SIZE:
            self.history.pop(0)
            self.history_index -= 1
        self._update_history_buttons()
        self._update_history_widgets()

    def _reset_all(self):
        if not self.processor:
            return
        self._deactivate_current_modal_tool()
        self.processor.reset_all()
        for tool in self.tools.values():
            tool.reset()
        self.history.clear()
        self.history_index = -1
        self._add_to_history(self.processor.get_state())
        self._render_image()

    def undo(self):
        if self.history_index > 0:
            self.history_index -= 1
            self._load_state_from_history()

    def redo(self):
        if self.history_index < len(self.history) - 1:
            self.history_index += 1
            self._load_state_from_history()

    def _jump_to_history_state(self, state_index: int):
        """Переход к конкретному состоянию из дерева истории"""
        if 0 <= state_index < len(self.history):
            self.history_index = state_index
            self._load_state_from_history()

    def _load_state_from_history(self):
        state = self.history[self.history_index]
        self.processor.set_state(state)
        for tool in self.tools.values():
            tool_state = state.get(tool.name, None)
            tool.set_params(tool_state) if tool_state else tool.reset()
        self._render_image()
        self._update_history_buttons()
        self._update_history_widgets()

    def _on_history_cleared(self):
        """Reset editor history when tree widget clears"""
        if self.processor and self.processor.original_image:
            self.history = [self.processor.get_state()]
            self.history_index = 0
            self._render_image()
            self._update_history_buttons()

    def _update_history_buttons(self):
        self.undo_action.setEnabled(self.history_index > 0)
        self.redo_action.setEnabled(self.history_index < len(self.history) - 1)

    def _update_history_widgets(self):
        """Обновляет все виджеты истории"""
        self.compact_history.update_state(self.history, self.history_index)
        self.history_tree.update_history(self.history, self.history_index)

    def _update_scene(self, pixmap: QPixmap):
        self.view.resetTransform()
        self.scene.clear()
        self.current_pixmap_item = self.scene.addPixmap(pixmap)
        self.scene.setSceneRect(self.current_pixmap_item.boundingRect())
        self._fit_to_view()

    def _pil_to_pixmap(self, pil_image: Image) -> QPixmap:
        img_data = pil_image.tobytes("raw", "RGB")
        q_image = QImage(img_data, pil_image.width, pil_image.height, pil_image.width * 3, QImage.Format.Format_RGB888)
        return QPixmap.fromImage(q_image)

    def _save_image(self):
        if not self.processor:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Сохранить изображение", "", "JPEG (*.jpg);;PNG (*.png)")
        if path:
            final_image = self.processor.process(is_preview=False)
            final_image.save(path, quality=95 if path.lower().endswith('.jpg') else 100)
            QMessageBox.information(self, "Успех", f"Изображение сохранено: {path}")

    def closeEvent(self, event):
        self.history.clear()
        self.processor = None
        super().closeEvent(event)