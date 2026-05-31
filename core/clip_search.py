# core/clip_search.py

import os
import urllib.request
import logging
import threading
import numpy as np
import onnxruntime as ort
from PIL import Image

from core.clip_tokenizer import SimpleTokenizer

logger = logging.getLogger(__name__)

# Полностью открытые и стабильные URL из официального репозитория Xenova
VISUAL_URL = "https://huggingface.co/Xenova/clip-vit-base-patch32/resolve/main/onnx/vision_model.onnx"
TEXTUAL_URL = "https://huggingface.co/Xenova/clip-vit-base-patch32/resolve/main/onnx/text_model.onnx"

class ClipSearchEngine:
    _instance = None
    _lock = threading.Lock()  # Блокировка для безопасного создания синглтона в многопоточной среде
    
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
        
        self.visual_path = os.path.join(models_dir, "clip_visual.onnx")
        self.textual_path = os.path.join(models_dir, "clip_textual.onnx")
        
        self._ensure_models()
        self._init_sessions()
        
    def _ensure_models(self):
        for path, url in [(self.visual_path, VISUAL_URL), (self.textual_path, TEXTUAL_URL)]:
            if not os.path.exists(path) or os.path.getsize(path) < 1000:
                logger.info(f"Скачивание модели CLIP: {os.path.basename(path)} (~150MB)...")
                try:
                    urllib.request.urlretrieve(url, path)
                except Exception as e:
                    logger.error(f"Не удалось скачать {path}: {e}")
                    if os.path.exists(path):
                        try:
                            os.remove(path)
                        except Exception:
                            pass
                    
    def _init_sessions(self):
        if os.path.exists(self.visual_path) and os.path.exists(self.textual_path):
            try:
                self.tokenizer = SimpleTokenizer()
                
                # Инициализируем сессии ONNX Runtime
                opts = ort.SessionOptions()
                opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
                
                self.visual_sess = ort.InferenceSession(self.visual_path, opts, providers=["CPUExecutionProvider"])
                self.textual_sess = ort.InferenceSession(self.textual_path, opts, providers=["CPUExecutionProvider"])
                self.available = True
                logger.info("Семантический поиск CLIP (ONNX) успешно инициализирован.")
            except Exception as e:
                logger.error(f"Ошибка инициализации CLIP сессий: {e}")
                
    def get_image_embedding(self, image_path: str) -> np.ndarray | None:
        if not self.available:
            return None
        try:
            with Image.open(image_path) as img:
                img = img.resize((224, 224), Image.Resampling.BICUBIC)
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                arr = np.array(img).astype(np.float32) / 255.0
                
            # Нормализация OpenAI CLIP
            mean = np.array([0.48145466, 0.4578275, 0.40821073], dtype=np.float32)
            std = np.array([0.26862954, 0.26130258, 0.27577711], dtype=np.float32)
            arr = (arr - mean) / std
            arr = np.transpose(arr, (2, 0, 1)) # (3, 224, 224)
            arr = np.expand_dims(arr, axis=0)  # (1, 3, 224, 224)
            
            # Динамически получаем имя входного тензора
            inputs_meta = self.visual_sess.get_inputs()
            input_name = inputs_meta[0].name
            outputs = self.visual_sess.run(None, {input_name: arr})
            
            # Динамически сопоставляем имя выходного тензора
            output_names = [out.name for out in self.visual_sess.get_outputs()]
            if 'image_embeds' in output_names:
                idx = output_names.index('image_embeds')
                return outputs[idx][0]
            return outputs[0][0]
        except Exception as e:
            logger.error(f"Ошибка расчета CLIP вектора для {image_path}: {e}")
            return None
            
    def get_text_embedding(self, query: str) -> np.ndarray | None:
        if not self.available:
            return None
        try:
            tokens = self.tokenizer.encode(query)
            if len(tokens) > 77:
                tokens = tokens[:77]
            else:
                tokens = tokens + [0] * (77 - len(tokens))
                
            tokens_arr = np.array([tokens], dtype=np.int32)
            attn_mask = np.ones_like(tokens_arr)
            
            # Динамически формируем входы для Optimum-формата
            inputs = {}
            for inp in self.textual_sess.get_inputs():
                if inp.name == "input_ids":
                    inputs["input_ids"] = tokens_arr
                elif inp.name == "attention_mask":
                    inputs["attention_mask"] = attn_mask
                    
            outputs = self.textual_sess.run(None, inputs)
            
            # Динамически извлекаем выходной вектор
            output_names = [out.name for out in self.textual_sess.get_outputs()]
            if 'text_embeds' in output_names:
                idx = output_names.index('text_embeds')
                return outputs[idx][0]
            return outputs[0][0]
        except Exception as e:
            logger.error(f"Ошибка токенизации/эмбеддинга текста '{query}': {e}")
            return None