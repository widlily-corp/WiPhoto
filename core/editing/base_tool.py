from abc import ABC, abstractmethod, ABCMeta
from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import QObject, pyqtSignal
from PIL.Image import Image

class QObjectABCMeta(type(QObject), ABCMeta):
    pass

class EditingTool(QObject, ABC, metaclass=QObjectABCMeta):
    """
    Абстрактный базовый класс для всех инструментов редактирования.
    Определяет единый интерфейс для взаимодействия с UI и ядром обработки.
    """
    # Унифицированный сигнал для всех инструментов.
    # Аргументы: tool_name, param_name, value, is_preview
    valueChanged = pyqtSignal(str, str, int, bool)

    def __init__(self):
        super().__init__()
        self._ui_widget = None

    @property
    @abstractmethod
    def name(self) -> str:
        """Техническое имя инструмента (например, 'clarity')."""
        pass

    @property
    @abstractmethod
    def label(self) -> str:
        """Отображаемое имя для UI (например, 'Четкость')."""
        pass

    def get_ui(self, parent=None) -> QWidget:
        """Возвращает UI виджет, создавая его при первом вызове (ленивая инициализация)."""
        if self._ui_widget is None:
            self._ui_widget = self._create_ui(parent)
        return self._ui_widget

    @abstractmethod
    def _create_ui(self, parent=None) -> QWidget:
        """
        Создает и возвращает виджет с элементами управления (слайдеры, кнопки).
        Реализуется в каждом дочернем классе.
        """
        pass

    @abstractmethod
    def apply(self, image: Image) -> Image:
        """
        Применяет эффект к изображению PIL.Image и возвращает обработанное изображение.
        """
        pass

    @abstractmethod
    def get_params(self) -> dict:
        """Возвращает текущие параметры инструмента в виде словаря."""
        pass

    @abstractmethod
    def set_params(self, params: dict):
        """Устанавливает параметры инструмента из словаря."""
        pass

    @abstractmethod
    def reset(self):
        """Сбрасывает параметры инструмента к значениям по умолчанию."""
        pass
# --- END OF FILE core/editing/base_tool.py ---