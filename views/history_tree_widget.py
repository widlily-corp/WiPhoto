# views/history_tree_widget.py

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QTreeWidget, QTreeWidgetItem,
                             QPushButton, QHBoxLayout, QLabel)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QIcon
from collections import OrderedDict
from utils import resource_path


class HistoryTreeWidget(QWidget):
    """Дерево истории изменений с визуализацией"""

    jump_to_state = pyqtSignal(int)  # Переход к конкретному состоянию
    history_cleared = pyqtSignal()  # Сигнал очистки истории

    def __init__(self, parent=None):
        super().__init__(parent)
        self.history = []
        self.current_index = -1
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        # Заголовок
        header = QLabel("📜 История изменений")
        header.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(header)

        # Дерево истории
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Действие", "Параметры"])
        self.tree.setColumnWidth(0, 150)
        self.tree.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self.tree)

        # Кнопки управления
        buttons_layout = QHBoxLayout()

        self.clear_btn = QPushButton("🗑️ Очистить историю")
        self.clear_btn.clicked.connect(self._clear_history)
        buttons_layout.addWidget(self.clear_btn)

        layout.addLayout(buttons_layout)

        # Информация о текущем состоянии
        self.info_label = QLabel("История пуста")
        self.info_label.setStyleSheet("color: #888; font-size: 11px;")
        layout.addWidget(self.info_label)

    def update_history(self, history: list, current_index: int):
        """Обновляет отображение истории"""
        self.history = history
        self.current_index = current_index
        self._rebuild_tree()

    def _rebuild_tree(self):
        """Перестраивает дерево истории"""
        self.tree.clear()

        if not self.history:
            self.info_label.setText("История пуста")
            return

        # Создаем элементы дерева
        for idx, state in enumerate(self.history):
            is_current = (idx == self.current_index)
            self._add_state_to_tree(idx, state, is_current)

        # Обновляем информацию
        total = len(self.history)
        current = self.current_index + 1
        self.info_label.setText(f"Состояние {current} из {total}")

        # Разворачиваем текущее состояние
        if self.current_index >= 0:
            current_item = self.tree.topLevelItem(self.current_index)
            if current_item:
                current_item.setExpanded(True)
                self.tree.scrollToItem(current_item)

    def _add_state_to_tree(self, index: int, state: OrderedDict, is_current: bool):
        """Добавляет состояние в дерево"""
        # Корневой элемент для состояния
        root_text = f"{'➤ ' if is_current else ''}Состояние {index + 1}"
        root = QTreeWidgetItem([root_text, ""])

        if is_current:
            root.setBackground(0, Qt.GlobalColor.darkCyan)
            root.setBackground(1, Qt.GlobalColor.darkCyan)

        # Добавляем параметры как дочерние элементы
        for tool_name, params in state.items():
            if not params or tool_name == "base_image":
                continue

            tool_item = QTreeWidgetItem([tool_name, ""])

            # Добавляем параметры инструмента
            if isinstance(params, dict):
                for param_name, value in params.items():
                    if param_name == 'applied':
                        # Для действий показываем просто "Применено"
                        param_item = QTreeWidgetItem(["✓ Применено", ""])
                    else:
                        # Форматируем значение
                        value_str = self._format_value(value)
                        param_item = QTreeWidgetItem([param_name, value_str])

                    tool_item.addChild(param_item)

            root.addChild(tool_item)

        self.tree.addTopLevelItem(root)
        root.setData(0, Qt.ItemDataRole.UserRole, index)

    def _format_value(self, value) -> str:
        """Форматирует значение параметра для отображения"""
        if isinstance(value, float):
            return f"{value:.2f}"
        elif isinstance(value, bool):
            return "✓" if value else "✗"
        elif isinstance(value, (tuple, list)):
            return f"({', '.join(map(str, value))})"
        return str(value)

    def _on_item_clicked(self, item: QTreeWidgetItem, column: int):
        """Обработка клика по элементу"""
        # Ищем корневой элемент (состояние)
        root = item
        while root.parent():
            root = root.parent()

        # Получаем индекс состояния
        state_index = root.data(0, Qt.ItemDataRole.UserRole)
        if state_index is not None and state_index != self.current_index:
            self.jump_to_state.emit(state_index)

    def _clear_history(self):
        """Очищает историю"""
        self.tree.clear()
        self.history = []
        self.current_index = -1
        self.info_label.setText("История очищена")
        self.history_cleared.emit()


class CompactHistoryWidget(QWidget):
    """Компактная версия истории (для боковой панели)"""

    undo_requested = pyqtSignal()
    redo_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Кнопки Undo/Redo
        buttons_layout = QHBoxLayout()

        self.undo_btn = QPushButton("↶ Отменить")
        self.undo_btn.clicked.connect(self.undo_requested.emit)
        self.undo_btn.setEnabled(False)
        buttons_layout.addWidget(self.undo_btn)

        self.redo_btn = QPushButton("↷ Вернуть")
        self.redo_btn.clicked.connect(self.redo_requested.emit)
        self.redo_btn.setEnabled(False)
        buttons_layout.addWidget(self.redo_btn)

        layout.addLayout(buttons_layout)

        # Список последних действий
        self.history_list = QTreeWidget()
        self.history_list.setHeaderHidden(True)
        self.history_list.setMaximumHeight(150)
        layout.addWidget(self.history_list)

        # Счетчик
        self.counter = QLabel("0/0")
        self.counter.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.counter.setStyleSheet("color: #888; font-size: 10px;")
        layout.addWidget(self.counter)

    def update_state(self, history: list, current_index: int):
        """Обновляет состояние виджета"""
        # Обновляем кнопки
        self.undo_btn.setEnabled(current_index > 0)
        self.redo_btn.setEnabled(current_index < len(history) - 1)

        # Обновляем список (показываем последние 5 действий)
        self.history_list.clear()

        start = max(0, current_index - 2)
        end = min(len(history), current_index + 3)

        for idx in range(start, end):
            state = history[idx]
            is_current = (idx == current_index)

            # Создаем краткое описание состояния
            actions = []
            for tool_name, params in state.items():
                if params and tool_name != "base_image":
                    actions.append(tool_name)

            text = f"{'➤ ' if is_current else ''}{', '.join(actions[:2])}"
            if len(actions) > 2:
                text += "..."

            item = QTreeWidgetItem([text])
            if is_current:
                item.setBackground(0, Qt.GlobalColor.darkCyan)

            self.history_list.addTopLevelItem(item)

        # Обновляем счетчик
        self.counter.setText(f"{current_index + 1}/{len(history)}")