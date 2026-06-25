
from .tool_exposure import ExposureTool
from .tool_contrast import ContrastTool
from .tool_highlights import HighlightsTool
from .tool_shadows import ShadowsTool
from .tool_whites import WhitesTool
from .tool_blacks import BlacksTool
from .tool_temperature import TemperatureTool
from .tool_tint import TintTool
from .tool_vibrance import VibranceTool
from .tool_saturation import SaturationTool
from .tool_sharpness import SharpnessTool
from .tool_clarity import ClarityTool
from .tool_vignette import VignetteTool
from .tool_crop import CropTool
from .tool_rotation import RotationTool
# <<< НОВОЕ: Импортируем инструменты отражения
from .tool_flip_horizontal import FlipHorizontalTool
from .tool_flip_vertical import FlipVerticalTool
from .tool_smart_retouch import SmartRetouchTool

# --- Группировка инструментов для UI ---
TOOL_GROUPS = {
    "Свет": ["exposure", "contrast", "highlights", "shadows", "whites", "blacks"],
    "Цвет": ["temperature", "tint", "vibrance", "saturation"],
    "Детализация": ["clarity", "sharpness"],
    "Эффекты": ["vignette"]
}

# --- Инструменты с модальным UI (на тулбаре) ---
MODAL_TOOLS = [CropTool, RotationTool, SmartRetouchTool]

# <<< НОВОЕ: Инструменты-действия (на тулбаре) ---
ACTION_TOOLS = [FlipHorizontalTool, FlipVerticalTool]

# --- Полный словарь всех инструментов для быстрого доступа ---
ALL_TOOLS_MAP = {
    "exposure": ExposureTool, "contrast": ContrastTool,
    "highlights": HighlightsTool, "shadows": ShadowsTool,
    "whites": WhitesTool, "blacks": BlacksTool,
    "temperature": TemperatureTool, "tint": TintTool,
    "vibrance": VibranceTool, "saturation": SaturationTool,
    "clarity": ClarityTool, "sharpness": SharpnessTool,
    "vignette": VignetteTool, "crop": CropTool, "rotation": RotationTool,
    "flip_horizontal": FlipHorizontalTool, "flip_vertical": FlipVerticalTool,
    "smart_retouch": SmartRetouchTool,  # <-- Добавлено
}