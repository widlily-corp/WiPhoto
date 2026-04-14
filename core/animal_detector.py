# core/animal_detector.py

import cv2
import os
import logging
import urllib.request
from typing import List, Optional, Dict
from dataclasses import dataclass


MODELS_DIR = os.path.join(os.path.dirname(__file__), "..", "assets", "models")

# COCO class IDs → names for animals + person
ANIMAL_CLASSES = {
    0: "person",
    14: "bird",
    15: "cat",
    16: "dog",
    17: "horse",
    18: "sheep",
    19: "cow",
    20: "elephant",
    21: "bear",
    22: "zebra",
    23: "giraffe",
}

# Only actual animals (not person)
ANIMAL_ONLY_IDS = {14, 15, 16, 17, 18, 19, 20, 21, 22, 23}

YOLO_WEIGHTS_URL = "https://github.com/AlexeyAB/darknet/releases/download/yolov4/yolov4-tiny.weights"
YOLO_CFG_URL = "https://raw.githubusercontent.com/AlexeyAB/darknet/master/cfg/yolov4-tiny.cfg"
COCO_NAMES_URL = "https://raw.githubusercontent.com/AlexeyAB/darknet/master/data/coco.names"


@dataclass
class Animal:
    species: str  # 'cat', 'dog', 'bird', 'horse', etc.
    x: int
    y: int
    width: int
    height: int
    confidence: float = 0.0


@dataclass
class DetectedObject:
    """Generic detected object (person, vehicle, animal, etc.)"""
    label: str
    x: int
    y: int
    width: int
    height: int
    confidence: float = 0.0


class AnimalDetector:
    """YOLO v4-tiny animal/object detector via OpenCV DNN. Singleton."""

    _instance: Optional['AnimalDetector'] = None

    @classmethod
    def get_instance(cls) -> 'AnimalDetector':
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self.available = False
        self._net = None
        self._output_layers = None
        self._class_names: List[str] = []
        self._conf_threshold = 0.4
        self._nms_threshold = 0.4
        self._input_size = (416, 416)
        self._init_detector()

    def _get_model_path(self, filename: str) -> str:
        """Get path to model file in assets/models/"""
        try:
            from utils import resource_path
            p = resource_path(f"assets/models/{filename}")
            if os.path.exists(p):
                return p
        except Exception:
            pass
        return os.path.abspath(os.path.join(MODELS_DIR, filename))

    def _download_file(self, url: str, dest: str) -> bool:
        """Download file with progress logging"""
        try:
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            logging.info(f"Downloading model: {os.path.basename(dest)} ...")
            urllib.request.urlretrieve(url, dest)
            logging.info(f"Downloaded: {os.path.basename(dest)} ({os.path.getsize(dest) // 1024}KB)")
            return True
        except Exception as e:
            logging.error(f"Download failed {url}: {e}")
            if os.path.exists(dest):
                os.remove(dest)
            return False

    def _ensure_models(self) -> bool:
        """Download YOLO models if not present. Returns True if all files ready."""
        weights_path = self._get_model_path("yolov4-tiny.weights")
        cfg_path = self._get_model_path("yolov4-tiny.cfg")
        names_path = self._get_model_path("coco.names")

        files = [
            (weights_path, YOLO_WEIGHTS_URL),
            (cfg_path, YOLO_CFG_URL),
            (names_path, COCO_NAMES_URL),
        ]

        for path, url in files:
            if not os.path.exists(path) or os.path.getsize(path) < 100:
                if not self._download_file(url, path):
                    return False
        return True

    def _init_detector(self):
        """Initialize YOLO v4-tiny via OpenCV DNN"""
        if not self._ensure_models():
            logging.warning("Animal detection: models not available, skipping")
            return

        weights_path = self._get_model_path("yolov4-tiny.weights")
        cfg_path = self._get_model_path("yolov4-tiny.cfg")
        names_path = self._get_model_path("coco.names")

        try:
            # Load class names
            with open(names_path, 'r') as f:
                self._class_names = [line.strip() for line in f.readlines()]

            # Load network
            self._net = cv2.dnn.readNetFromDarknet(cfg_path, weights_path)
            self._net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
            self._net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)

            # Get output layer names
            layer_names = self._net.getLayerNames()
            out_indices = self._net.getUnconnectedOutLayers()
            self._output_layers = [layer_names[i - 1] for i in out_indices.flatten()]

            self.available = True
            logging.info(f"Animal detection: YOLOv4-tiny ({len(self._class_names)} classes)")

        except Exception as e:
            logging.error(f"YOLO init failed: {e}")
            self.available = False

    def _run_inference(self, img) -> List[DetectedObject]:
        """Run YOLO inference and return all detections"""
        h, w = img.shape[:2]

        # Prepare input blob
        blob = cv2.dnn.blobFromImage(img, 1/255.0, self._input_size, swapRB=True, crop=False)
        self._net.setInput(blob)
        outputs = self._net.forward(self._output_layers)

        # Parse detections
        boxes = []
        confidences = []
        class_ids = []

        for output in outputs:
            for detection in output:
                scores = detection[5:]
                class_id = int(scores.argmax())
                confidence = float(scores[class_id])

                if confidence < self._conf_threshold:
                    continue

                # YOLO returns center_x, center_y, width, height (normalized)
                cx = int(detection[0] * w)
                cy = int(detection[1] * h)
                bw = int(detection[2] * w)
                bh = int(detection[3] * h)
                x = cx - bw // 2
                y = cy - bh // 2

                boxes.append([x, y, bw, bh])
                confidences.append(confidence)
                class_ids.append(class_id)

        # Apply NMS
        if not boxes:
            return []

        indices = cv2.dnn.NMSBoxes(boxes, confidences, self._conf_threshold, self._nms_threshold)
        if indices is None or len(indices) == 0:
            return []

        results = []
        for i in indices.flatten():
            label = self._class_names[class_ids[i]] if class_ids[i] < len(self._class_names) else f"class_{class_ids[i]}"
            results.append(DetectedObject(
                label=label,
                x=max(0, boxes[i][0]),
                y=max(0, boxes[i][1]),
                width=boxes[i][2],
                height=boxes[i][3],
                confidence=confidences[i]
            ))

        return results

    def detect_all(self, image_path: str) -> List[DetectedObject]:
        """Detect all objects in image (animals, people, etc.)"""
        if not self.available:
            return []
        try:
            img = cv2.imread(image_path)
            if img is None:
                return []

            # Limit image size for speed
            h, w = img.shape[:2]
            max_dim = 1024
            if max(h, w) > max_dim:
                scale = max_dim / max(h, w)
                img = cv2.resize(img, (int(w * scale), int(h * scale)))
                # Scale factor for converting coords back
                inv_scale = 1.0 / scale
            else:
                inv_scale = 1.0

            detections = self._run_inference(img)

            # Scale coordinates back to original size
            if inv_scale != 1.0:
                for d in detections:
                    d.x = int(d.x * inv_scale)
                    d.y = int(d.y * inv_scale)
                    d.width = int(d.width * inv_scale)
                    d.height = int(d.height * inv_scale)

            return detections

        except Exception as e:
            logging.error(f"Detection error {image_path}: {e}")
            return []

    def detect_animals(self, image_path: str) -> List[Animal]:
        """Detect only animals in image"""
        all_objects = self.detect_all(image_path)
        animals = []
        for obj in all_objects:
            # Check if it's an animal class
            if obj.label in ('cat', 'dog', 'bird', 'horse', 'sheep', 'cow',
                             'elephant', 'bear', 'zebra', 'giraffe'):
                animals.append(Animal(
                    species=obj.label,
                    x=obj.x, y=obj.y,
                    width=obj.width, height=obj.height,
                    confidence=obj.confidence
                ))
        return animals

    def count_animals(self, image_path: str) -> int:
        return len(self.detect_animals(image_path))

    def count_people(self, image_path: str) -> int:
        """Count people detected by YOLO (can supplement face detection)"""
        all_objects = self.detect_all(image_path)
        return sum(1 for obj in all_objects if obj.label == 'person')

    def get_tags(self, image_path: str) -> List[str]:
        """Get unique object labels found in image — useful for auto-tagging"""
        all_objects = self.detect_all(image_path)
        return list(set(obj.label for obj in all_objects))

    def get_animal_species(self, image_path: str) -> List[str]:
        """Get list of unique animal species in image"""
        animals = self.detect_animals(image_path)
        return list(set(a.species for a in animals))
