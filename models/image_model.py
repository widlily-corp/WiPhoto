# models/image_model.py

from dataclasses import dataclass, field
from typing import Optional
from PyQt6.QtGui import QPixmap


VIDEO_EXTENSIONS = ('.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v',
                    '.mpg', '.mpeg', '.3gp', '.ogv', '.ts', '.mts', '.m2ts')

RAW_EXTENSIONS = ('.arw', '.cr2', '.cr3', '.nef', '.nrw', '.dng', '.raw', '.rw2', '.orf', '.pef',
                  '.raf', '.srw', '.x3f')


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
    rating: int = 0  # 0-5 stars
    file_size: int = 0  # bytes
    width: int = 0
    height: int = 0
    color_label: str = ""  # red, yellow, green, blue, purple
    flag_status: str = ""  # "" = unflagged, "picked" = picked, "rejected" = rejected
    tags: list = field(default_factory=list)  # AI-generated tags

    def is_video(self) -> bool:
        """Проверяет, является ли файл видео"""
        return self.path.lower().endswith(VIDEO_EXTENSIONS)