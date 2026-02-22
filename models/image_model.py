# models/image_model.py

from dataclasses import dataclass, field
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