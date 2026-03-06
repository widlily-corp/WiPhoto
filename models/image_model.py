# models/image_model.py

from dataclasses import dataclass, field
from typing import Optional
from PyQt6.QtGui import QPixmap


VIDEO_EXTENSIONS = ('.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v',
                    '.mpg', '.mpeg', '.3gp', '.ogv', '.ts', '.mts', '.m2ts')


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
    aspect_ratio: float = 0.0
    camera_model: str = ""
    date_taken: str = ""

    def is_video(self) -> bool:
        """Проверяет, является ли файл видео"""
        return self.path.lower().endswith(VIDEO_EXTENSIONS)