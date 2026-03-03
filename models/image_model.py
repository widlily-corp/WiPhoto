# models/image_model.py

from dataclasses import dataclass, field
from typing import Optional
from PyQt6.QtGui import QPixmap


@dataclass
class ImageInfo:
    """
    Облегченная структура для хранения информации об изображении.
    Не хранит саму миниатюру в памяти, только путь к ней.
    """
    path: str
    phash: str = None
    sharpness: float = 0.0
    is_best_in_group: bool = False
    group_id: str = None
    thumbnail_path: str = None

    # Автоматический анализ
    faces_count: int = 0
    animals_count: int = 0
    gps_location: Optional[tuple] = None  # (latitude, longitude)
    aspect_ratio: float = 0.0  # Для определения документов