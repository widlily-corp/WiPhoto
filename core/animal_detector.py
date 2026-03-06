# core/animal_detector.py

import cv2
import logging
from typing import List, Optional
from dataclasses import dataclass


@dataclass
class Animal:
    species: str  # 'cat'
    x: int
    y: int
    width: int
    height: int
    confidence: float = 0.0


class AnimalDetector:
    """Детектор животных (кошки) через Haar cascade. Singleton."""

    _instance: Optional['AnimalDetector'] = None

    @classmethod
    def get_instance(cls) -> 'AnimalDetector':
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self.available = False
        self._cat_cascade = None

        try:
            cascade_base = cv2.data.haarcascades
            # Prefer extended cascade
            for name in ('haarcascade_frontalcatface_extended.xml',
                         'haarcascade_frontalcatface.xml'):
                path = cascade_base + name
                cascade = cv2.CascadeClassifier(path)
                if not cascade.empty():
                    self._cat_cascade = cascade
                    self.available = True
                    logging.info(f"Animal detection: {name}")
                    break
        except Exception as e:
            logging.error(f"Animal detection unavailable: {e}")

    def detect_animals(self, image_path: str) -> List[Animal]:
        if not self.available:
            return []
        try:
            img = cv2.imread(image_path)
            if img is None:
                return []
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            cats = self._cat_cascade.detectMultiScale(gray, 1.1, 5, minSize=(50, 50))
            return [
                Animal(species='cat', x=int(x), y=int(y),
                       width=int(w), height=int(h), confidence=0.8)
                for (x, y, w, h) in cats
            ]
        except Exception as e:
            logging.error(f"Animal detection error: {e}")
            return []

    def count_animals(self, image_path: str) -> int:
        return len(self.detect_animals(image_path))
