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
    """YuNet DNN face detector with multi-scale support. Singleton."""

    _instance: Optional['FaceDetector'] = None

    @classmethod
    def get_instance(cls) -> 'FaceDetector':
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self.available = False
        self._detector = None
        self._init_detector()

    def _init_detector(self):
        model_path = self._find_model()
        if not model_path:
            logging.warning("Face detection: YuNet model not found")
            return

        try:
            self._detector = cv2.FaceDetectorYN.create(
                model_path, "", (320, 320),
                score_threshold=0.5,  # lowered from 0.6 — catch more faces
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

        # For very large images, process at multiple scales
        # to catch both large foreground and small background faces
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

            self._detector.setInputSize((sw, sh))
            _, detections = self._detector.detect(scaled)

            if detections is None:
                continue

            inv_scale = 1.0 / scale
            for d in detections:
                face = Face(
                    x=int(d[0] * inv_scale),
                    y=int(d[1] * inv_scale),
                    width=int(d[2] * inv_scale),
                    height=int(d[3] * inv_scale),
                    confidence=float(d[-1])
                )
                # Filter out tiny detections (likely false positives)
                if face.width >= 20 and face.height >= 20:
                    all_faces.append(face)

        # Deduplicate overlapping faces from different scales
        return self._nms_faces(all_faces)

    def _get_scales(self, w: int, h: int) -> List[float]:
        """Choose scales based on image size."""
        max_dim = max(w, h)

        if max_dim <= 640:
            # Small image — process at original size
            return [1.0]
        elif max_dim <= 1920:
            # Medium — original + downscaled
            return [1.0, 640 / max_dim]
        else:
            # Large — 3 scales for comprehensive coverage
            return [1.0, 1920 / max_dim, 640 / max_dim]

    def _nms_faces(self, faces: List[Face], iou_thresh: float = 0.4) -> List[Face]:
        """Remove overlapping detections, keep highest confidence."""
        if len(faces) <= 1:
            return faces

        # Sort by confidence descending
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
