# core/face_detector.py

import cv2
import os
import logging
from typing import List, Optional
from dataclasses import dataclass


@dataclass
class Face:
    x: int
    y: int
    width: int
    height: int
    confidence: float = 0.0


class FaceDetector:
    """Детектор лиц: YuNet DNN (приоритет) с Haar fallback. Singleton."""

    _instance: Optional['FaceDetector'] = None

    @classmethod
    def get_instance(cls) -> 'FaceDetector':
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self.available = False
        self._use_dnn = False
        self._detector = None
        self._haar_cascade = None
        self._init_detector()

    def _init_detector(self):
        # YuNet DNN
        model_path = self._find_model()
        if model_path:
            try:
                self._detector = cv2.FaceDetectorYN.create(
                    model_path, "", (320, 320),
                    score_threshold=0.6,
                    nms_threshold=0.3,
                    top_k=5000
                )
                self._use_dnn = True
                self.available = True
                logging.info("Face detection: YuNet DNN")
                return
            except Exception as e:
                logging.warning(f"YuNet init failed: {e}")

        # Haar fallback
        try:
            cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
            self._haar_cascade = cv2.CascadeClassifier(cascade_path)
            if not self._haar_cascade.empty():
                self.available = True
                logging.info("Face detection: Haar cascade (fallback)")
        except Exception as e:
            logging.error(f"Face detection unavailable: {e}")

    def _find_model(self) -> Optional[str]:
        try:
            from utils import resource_path
            p = resource_path("assets/models/face_detection_yunet_2023mar.onnx")
            if os.path.exists(p):
                return p
        except Exception:
            pass
        # Dev fallback
        p = os.path.join(os.path.dirname(__file__), "..", "assets", "models",
                         "face_detection_yunet_2023mar.onnx")
        if os.path.exists(p):
            return os.path.abspath(p)
        return None

    def detect_faces(self, image_path: str) -> List[Face]:
        if not self.available:
            return []
        try:
            img = cv2.imread(image_path)
            if img is None:
                return []
            if self._use_dnn:
                return self._detect_yunet(img)
            return self._detect_haar(img)
        except Exception as e:
            logging.error(f"Face detection error: {e}")
            return []

    def _detect_yunet(self, img) -> List[Face]:
        h, w = img.shape[:2]
        self._detector.setInputSize((w, h))
        _, detections = self._detector.detect(img)
        if detections is None:
            return []
        return [
            Face(x=int(d[0]), y=int(d[1]), width=int(d[2]), height=int(d[3]),
                 confidence=float(d[-1]))
            for d in detections
        ]

    def _detect_haar(self, img) -> List[Face]:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        rects = self._haar_cascade.detectMultiScale(gray, 1.1, 5, minSize=(30, 30))
        return [Face(x=int(x), y=int(y), width=int(w), height=int(h))
                for (x, y, w, h) in rects]

    def count_faces(self, image_path: str) -> int:
        return len(self.detect_faces(image_path))
