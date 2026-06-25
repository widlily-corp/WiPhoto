from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QPushButton, QGroupBox, QScrollArea,
                             QFrame, QSizePolicy)
from PyQt6.QtCore import Qt, pyqtSignal, QPropertyAnimation, QEasingCurve
from core.editing.base_tool import EditingTool

class CollapsibleGroupBox(QGroupBox):
    def __init__(self, title="", parent=None):
        super().__init__(title, parent)
        self.setCheckable(True); self.setChecked(False)
        self.content_layout = QVBoxLayout()
        self.content_widget = QWidget(); self.content_widget.setLayout(self.content_layout)
        self.content_widget.setMaximumHeight(0); self.content_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        main_layout = QVBoxLayout(self); main_layout.setSpacing(0); main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.content_widget)
        self.animation = QPropertyAnimation(self.content_widget, b"maximumHeight")
        self.animation.setDuration(200); self.animation.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self.toggled.connect(self.toggle_animation)
    def add_widget(self, widget: QWidget): self.content_layout.addWidget(widget)
    def toggle_animation(self, checked):
        start_height = self.content_widget.height()
        end_height = self.content_widget.sizeHint().height() if checked else 0
        self.animation.setStartValue(start_height); self.animation.setEndValue(end_height); self.animation.start()

class ControlPanelWidget(QWidget):
    reset_all_requested = pyqtSignal()
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(320); self.setObjectName("ControlPanel")
        main_layout = QVBoxLayout(self); main_layout.setAlignment(Qt.AlignmentFlag.AlignTop); main_layout.setContentsMargins(5, 5, 5, 5)
        self.reset_all_button = QPushButton("Сбросить все настройки"); self.reset_all_button.clicked.connect(self.reset_all_requested.emit)
        main_layout.addWidget(self.reset_all_button)
        self.modal_tool_container = QFrame(); self.modal_tool_container.setObjectName("ModalToolFrame")
        self.modal_tool_layout = QVBoxLayout(self.modal_tool_container)
        self.modal_tool_container.setVisible(False)
        main_layout.addWidget(self.modal_tool_container)
        separator = QFrame(); separator.setFrameShape(QFrame.Shape.HLine); separator.setFrameShadow(QFrame.Shadow.Sunken)
        main_layout.addWidget(separator)
        scroll_area = QScrollArea(); scroll_area.setWidgetResizable(True); scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setObjectName("ControlPanelScrollArea")
        # Устанавливаем прозрачный фон для scroll area
        scroll_area.setStyleSheet("QScrollArea { background-color: transparent; border: none; } QScrollArea > QWidget > QWidget { background-color: transparent; }")
        self.tools_scroll_area = scroll_area
        self.tools_container = QWidget()
        self.tools_layout = QVBoxLayout(self.tools_container); self.tools_layout.setAlignment(Qt.AlignmentFlag.AlignTop); self.tools_layout.setSpacing(5)
        scroll_area.setWidget(self.tools_container)
        main_layout.addWidget(scroll_area)

    def add_tool_group(self, group_name: str, tools: list[EditingTool]):
        group_box = CollapsibleGroupBox(group_name)
        for tool in tools:
            tool_ui = tool.get_ui()
            if tool_ui: group_box.add_widget(tool_ui)
        self.tools_layout.addWidget(group_box)

    def show_modal_tool_ui(self, tool_ui: QWidget):
        self.clear_modal_ui(); self.modal_tool_layout.addWidget(tool_ui)
        self.modal_tool_container.setVisible(True); self.tools_scroll_area.setEnabled(False)

    def hide_modal_tool_ui(self):
        self.clear_modal_ui(); self.modal_tool_container.setVisible(False)
        self.tools_scroll_area.setEnabled(True)

    def clear_modal_ui(self):
        """Безопасно очищает контейнер, открепляя виджет, но не удаляя его."""
        while self.modal_tool_layout.count():
            child = self.modal_tool_layout.takeAt(0)
            if child.widget():
                # <<< ИСПРАВЛЕНИЕ: Просто открепляем виджет. Он будет удален в EditorWidget.
                child.widget().setParent(None)
# --- END OF FILE views/control_panel_widget.py ---