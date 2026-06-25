# core/face_recognizer.py

import os
import cv2
import urllib.request
import logging
import threading
import numpy as np
import onnxruntime as ort

logger = logging.getLogger(__name__)

# Стабильная, полностью открытая ArcFace модель без ограничений авторизации
ARCFACE_URL = "https://huggingface.co/biometric-ai-lab/Face_Recognition/resolve/main/arcface.onnx"

class FaceRecognizer:
    _instance = None
    _lock = threading.Lock()  # Блокировка для защиты от одновременных скачиваний/инициализации
    
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance
        
    def __init__(self):
        self.available = False
        models_dir = os.path.join(os.path.dirname(__file__), "..", "assets", "models")
        os.makedirs(models_dir, exist_ok=True)
        self.model_path = os.path.join(models_dir, "arcface.onnx")
        
        self._ensure_model()
        self._init_session()
        
    def _ensure_model(self):
        if not os.path.exists(self.model_path) or os.path.getsize(self.model_path) < 1000:
            logger.info("Скачивание ArcFace ONNX модели (~100MB)...")
            try:
                urllib.request.urlretrieve(ARCFACE_URL, self.model_path)
            except Exception as e:
                logger.error(f"Не удалось скачать ArcFace ONNX: {e}")
                if os.path.exists(self.model_path):
                    try:
                        os.remove(self.model_path)
                    except Exception:
                        pass
                
    def _init_session(self):
        if os.path.exists(self.model_path):
            try:
                opts = ort.SessionOptions()
                self.sess = ort.InferenceSession(self.model_path, opts, providers=["CPUExecutionProvider"])
                self.available = True
                logger.info("Распознавание лиц ArcFace (ONNX) успешно запущено.")
            except Exception as e:
                logger.error(f"Ошибка запуска ArcFace: {e}")
                # Если файл поврежден, удаляем его, чтобы при следующем запуске скачать заново
                if "INVALID_PROTOBUF" in str(e) or "failed" in str(e):
                    try:
                        os.remove(self.model_path)
                        logger.warning(f"Удален поврежденный файл модели: {self.model_path}")
                    except Exception:
                        pass
                
    def get_face_embedding(self, face_chip: np.ndarray) -> np.ndarray | None:
        """Извлечение 512-мерного вектора из вырезанной области лица"""
        if not self.available or face_chip is None or face_chip.size == 0:
            return None
        try:
            # Препроцессинг ArcFace: 112x112, RGB, нормализация
            img = cv2.resize(face_chip, (112, 112))
            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            img = (img.astype(np.float32) - 127.5) / 128.0
            img = np.transpose(img, (2, 0, 1)) # (3, 112, 112)
            img = np.expand_dims(img, axis=0)  # (1, 3, 112, 112)
            
            input_name = self.sess.get_inputs()[0].name
            outputs = self.sess.run(None, {input_name: img})
            return outputs[0][0]
        except Exception as e:
            logger.error(f"Ошибка расчета вектора лица: {e}")
            return None

def dbscan_numpy(embeddings: np.ndarray, eps: float = 0.55, min_samples: int = 2) -> np.ndarray:
    """
    Высокопроизводительный алгоритм кластеризации DBSCAN на базе NumPy.
    Исключает необходимость тащить тяжелую scikit-learn в сборку.
    """
    n = len(embeddings)
    if n == 0:
        return np.array([], dtype=int)
        
    # Косинусное расстояние = 1.0 - Косинусное сходство
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norm_embeddings = embeddings / (norms + 1e-8)
    sim_matrix = np.dot(norm_embeddings, norm_embeddings.T)
    dist_matrix = 1.0 - sim_matrix
    
    labels = -np.ones(n, dtype=int) # -1 = неклассифицирован / шум
    cluster_id = 0
    
    for i in range(n):
        if labels[i] != -1:
            continue
            
        neighbors = np.where(dist_matrix[i] <= eps)[0]
        if len(neighbors) < min_samples:
            continue
            
        labels[i] = cluster_id
        queue = list(neighbors)
        for q in queue:
            if q == i:
                continue
            if labels[q] == -1:
                labels[q] = cluster_id
                q_neighbors = np.where(dist_matrix[q] <= eps)[0]
                if len(q_neighbors) >= min_samples:
                    for qn in q_neighbors:
                        if qn not in queue:
                            queue.append(qn)
        cluster_id += 1
    return labels