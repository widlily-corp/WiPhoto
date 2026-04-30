# core/face_detector.py

import cv2
import os
import math
import logging
import threading
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
    """YuNet DNN face detector with multi-scale support. Singleton."""

    _instance: Optional['FaceDetector'] = None
    # Singleton creation lock
    _class_lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> 'FaceDetector':
        # FIX: double-checked locking to prevent race on singleton init
        if cls._instance is None:
            with cls._class_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def __init__(self):
        self.available = False
        self._detector = None
        # FIX: serialize all detector calls — cv2.FaceDetectorYN is NOT thread-safe:
        # concurrent setInputSize()+detect() calls cause assertion failures and
        # memory corruption inside OpenCV DNN backend.
        self._lock = threading.Lock()
        self._init_detector()

    def _init_detector(self):
        model_path = self._find_model()
        if not model_path:
            logging.warning("Face detection: YuNet model not found")
            return

        try:
            self._detector = cv2.FaceDetectorYN.create(
                model_path, "", (320, 320),
                score_threshold=0.5,
                nms_threshold=0.3,
                top_k=5000
            )
            self.available = True
            logging.info("Face detection: YuNet DNN ready")
        except Exception as e:
            logging.error(f"YuNet init failed: {e}")

    def _find_model(self) -> Optional[str]:
        try:
            from utils import resource_path
            p = resource_path("assets/models/face_detection_yunet_2023mar.onnx")
            if os.path.exists(p):
                return p
        except Exception:
            pass
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
            return self._detect_multiscale(img)
        except Exception as e:
            logging.error(f"Face detection error: {e}")
            return []

    def _detect_multiscale(self, img) -> List[Face]:
        """Multi-scale detection for better accuracy on varied image sizes."""
        h, w = img.shape[:2]
        all_faces = []

        scales = self._get_scales(w, h)

        for scale in scales:
            sw = int(w * scale)
            sh = int(h * scale)
            if sw < 64 or sh < 64:
                continue

            if scale != 1.0:
                scaled = cv2.resize(img, (sw, sh))
            else:
                scaled = img

            # FIX: hold lock for the entire setInputSize+detect sequence so
            # concurrent threads cannot interleave calls on the shared detector.
            with self._lock:
                self._detector.setInputSize((sw, sh))
                _, detections = self._detector.detect(scaled)

            if detections is None:
                continue

            inv_scale = 1.0 / scale
            for d in detections:
                # FIX: guard against inf/nan values returned by the detector
                # for degenerate images — int(math.inf) raises OverflowError
                # which can segfault on some OpenCV builds.
                raw = [float(d[0]), float(d[1]), float(d[2]), float(d[3]), float(d[-1])]
                if any(not math.isfinite(v) for v in raw):
                    continue

                face = Face(
                    x=int(raw[0] * inv_scale),
                    y=int(raw[1] * inv_scale),
                    width=int(raw[2] * inv_scale),
                    height=int(raw[3] * inv_scale),
                    confidence=raw[4]
                )
                if face.width >= 20 and face.height >= 20:
                    all_faces.append(face)

        return self._nms_faces(all_faces)

    def _get_scales(self, w: int, h: int) -> List[float]:
        """Choose scales based on image size."""
        max_dim = max(w, h)

        if max_dim <= 640:
            return [1.0]
        elif max_dim <= 1920:
            return [1.0, 640 / max_dim]
        else:
            return [1.0, 1920 / max_dim, 640 / max_dim]

    def _nms_faces(self, faces: List[Face], iou_thresh: float = 0.4) -> List[Face]:
        """Remove overlapping detections, keep highest confidence."""
        if len(faces) <= 1:
            return faces

        faces.sort(key=lambda f: f.confidence, reverse=True)
        keep = []

        for face in faces:
            is_duplicate = False
            for kept in keep:
                if self._iou(face, kept) > iou_thresh:
                    is_duplicate = True
                    break
            if not is_duplicate:
                keep.append(face)

        return keep

    @staticmethod
    def _iou(a: Face, b: Face) -> float:
        """Intersection over Union"""
        x1 = max(a.x, b.x)
        y1 = max(a.y, b.y)
        x2 = min(a.x + a.width, b.x + b.width)
        y2 = min(a.y + a.height, b.y + b.height)

        inter = max(0, x2 - x1) * max(0, y2 - y1)
        if inter == 0:
            return 0.0

        area_a = a.width * a.height
        area_b = b.width * b.height
        return inter / (area_a + area_b - inter)

    def count_faces(self, image_path: str) -> int:
        return len(self.detect_faces(image_path))
