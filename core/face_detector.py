# core/face_detector.py

import cv2
import numpy as np
from typing import List, Tuple, Optional
from dataclasses import dataclass


@dataclass
class Face:
    """Обнаруженное лицо"""
    x: int
    y: int
    width: int
    height: int
    confidence: float = 1.0


class FaceDetector:
    """Детектор лиц на изображениях"""

    def __init__(self):
        """Инициализация детектора с использованием каскада Haar"""
        try:
            # Используем предобученный каскад Хаара из OpenCV
            cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
            self.face_cascade = cv2.CascadeClassifier(cascade_path)

            # Проверяем, что каскад загружен
            if self.face_cascade.empty():
                raise RuntimeError("Failed to load face cascade classifier")
            self.available = True
        except Exception as e:
            print(f"Face detection unavailable: {e}")
            self.available = False

    def detect_faces(self, image_path: str, scale_factor: float = 1.1,
                     min_neighbors: int = 5) -> List[Face]:
        """
        Обнаружение лиц на изображении

        Args:
            image_path: Путь к изображению
            scale_factor: Коэффициент масштабирования для поиска лиц разных размеров
            min_neighbors: Минимальное количество соседей для подтверждения лица

        Returns:
            Список обнаруженных лиц
        """
        if not self.available:
            return []

        try:
            # Загружаем изображение
            img = cv2.imread(image_path)
            if img is None:
                return []

            # Конвертируем в градации серого
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

            # Обнаруживаем лица
            faces_raw = self.face_cascade.detectMultiScale(
                gray,
                scaleFactor=scale_factor,
                minNeighbors=min_neighbors,
                minSize=(30, 30)
            )

            # Конвертируем в список Face объектов
            faces = [
                Face(x=int(x), y=int(y), width=int(w), height=int(h))
                for (x, y, w, h) in faces_raw
            ]

            return faces

        except Exception as e:
            print(f"Error detecting faces in {image_path}: {e}")
            return []

    def count_faces(self, image_path: str) -> int:
        """Подсчитывает количество лиц на изображении"""
        return len(self.detect_faces(image_path))
