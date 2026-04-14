from PIL import Image
from .base_tool import EditingTool


class FlipHorizontalTool(EditingTool):
    def __init__(self): super().__init__()

    @property
    def name(self) -> str: return "flip_horizontal"

    @property
    def label(self) -> str: return "Отразить по горизонтали"

    def apply(self, image: Image) -> Image:
        return image.transpose(Image.FLIP_LEFT_RIGHT)

    # Этим инструментам не нужен UI на панели, поэтому методы пустые
    def _create_ui(self, parent=None): return None

    def get_params(self) -> dict: return {}

    def set_params(self, params: dict): pass

    def reset(self): pass
# --- END OF FILE core/editing/tool_flip_horizontal.py ---