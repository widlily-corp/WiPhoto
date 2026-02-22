from collections import OrderedDict
from PIL import Image
from . import ALL_TOOLS_MAP

class ImageProcessor:
    """
    Ядро обработки изображений. Управляет пайплайном неразрушающего редактирования.
    Это центральный класс, который применяет все эффекты.
    """

    def __init__(self, pil_image: Image):
        if pil_image is None:
            raise ValueError("ImageProcessor cannot be initialized with a None image.")
        self.original_image = pil_image
        self.preview_image = None
        self._tools = {name: tool() for name, tool in ALL_TOOLS_MAP.items()}
        self._pipeline = OrderedDict()

    def set_tool_param(self, tool_name: str, param_name: str, value):
        """Устанавливает значение для конкретного параметра инструмента."""
        if tool_name not in self._pipeline:
            self._pipeline[tool_name] = self._tools[tool_name].get_params()
        self._pipeline[tool_name][param_name] = value

    def reset_all(self):
        """Очищает весь пайплайн и сбрасывает все инструменты."""
        self._pipeline.clear()
        for tool in self._tools.values():
            tool.reset()

    def process(self, is_preview=False) -> Image:
        """
        Применяет весь пайплайн к изображению.
        Если is_preview=True, используется уменьшенная копия для скорости.
        """
        if is_preview:
            if self.preview_image is None:
                self.preview_image = self.original_image.copy()
                self.preview_image.thumbnail((1280, 1280), Image.Resampling.LANCZOS)
            image_to_process = self.preview_image.copy()
        else:
            image_to_process = self.original_image.copy()

        for tool_name, params in self._pipeline.items():
            tool = self._tools.get(tool_name)
            if tool:
                tool.set_params(params)
                image_to_process = tool.apply(image_to_process)

        return image_to_process

    def get_state(self) -> OrderedDict:
        """Возвращает текущее состояние пайплайна для сохранения в истории."""
        return OrderedDict({k: v.copy() for k, v in self._pipeline.items()})

    def set_state(self, state: OrderedDict):
        """Восстанавливает пайплайн из сохраненного состояния."""
        self.reset_all()
        self._pipeline = OrderedDict({k: v.copy() for k, v in state.items()})
        for tool_name, params in self._pipeline.items():
            if tool_name in self._tools:
                self._tools[tool_name].set_params(params)
# --- END OF FILE core/editing/image_processor.py ---