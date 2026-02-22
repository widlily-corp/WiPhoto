# core/animal_detector.py

import cv2
from typing import List, Optional
from dataclasses import dataclass


@dataclass
class Animal:
    """Обнаруженное животное"""
    species: str  # 'cat', 'dog', 'unknown'
    x: int
    y: int
    width: int
    height: int
    confidence: float = 0.0


class AnimalDetector:
    """Детектор животных на изображениях"""

    def __init__(self):
        """Инициализация детектора"""
        self.available = False
        try:
            # Пытаемся загрузить каскады для кошек и собак
            cascade_base = cv2.data.haarcascades
            self.cat_cascade = None
            self.dog_cascade = None

            # Проверяем доступность каскадов
            try:
                cat_path = cascade_base + 'haarcascade_frontalcatface.xml'
                self.cat_cascade = cv2.CascadeClassifier(cat_path)
                if not self.cat_cascade.empty():
                    self.available = True
            except:
                pass

            try:
                cat_extended_path = cascade_base + 'haarcascade_frontalcatface_extended.xml'
                cat_ext_cascade = cv2.CascadeClassifier(cat_extended_path)
                if not cat_ext_cascade.empty():
                    self.cat_cascade = cat_ext_cascade
                    self.available = True
            except:
                pass

        except Exception as e:
            print(f"Animal detection unavailable: {e}")

    def detect_animals(self, image_path: str) -> List[Animal]:
        """
        Обнаружение животных на изображении

        Args:
            image_path: Путь к изображению

        Returns:
            Список обнаруженных животных
        """
        if not self.available:
            return []

        animals = []

        try:
            img = cv2.imread(image_path)
            if img is None:
                return []

            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

            # Обнаружение кошек
            if self.cat_cascade and not self.cat_cascade.empty():
                cats = self.cat_cascade.detectMultiScale(
                    gray,
                    scaleFactor=1.1,
                    minNeighbors=5,
                    minSize=(50, 50)
                )
                for (x, y, w, h) in cats:
                    animals.append(Animal(
                        species='cat',
                        x=int(x), y=int(y),
                        width=int(w), height=int(h),
                        confidence=0.8
                    ))

            return animals

        except Exception as e:
            print(f"Error detecting animals in {image_path}: {e}")
            return []

    def count_animals(self, image_path: str) -> int:
        """Подсчитывает количество животных на изображении"""
        return len(self.detect_animals(image_path))
