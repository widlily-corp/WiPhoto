# core/database.py

import sqlite3
import numpy as np
import json
import os
import logging

logger = logging.getLogger(__name__)

class DatabaseManager:
    _instance = None
    
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
        
    def __init__(self):
        db_dir = os.path.join(os.path.expanduser("~"), ".wiphoto")
        os.makedirs(db_dir, exist_ok=True)
        self.db_path = os.path.join(db_dir, "wiphoto.db")
        self._init_db()
        
    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
        
    def _init_db(self):
        try:
            with self._get_connection() as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS images (
                        path TEXT PRIMARY KEY,
                        clip_embedding BLOB
                    )
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS faces (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        image_path TEXT,
                        bbox TEXT, -- Хранение [x, y, w, h] в формате JSON
                        embedding BLOB,
                        name TEXT,
                        FOREIGN KEY(image_path) REFERENCES images(path) ON DELETE CASCADE
                    )
                """)
                conn.commit()
        except Exception as e:
            logger.error(f"Ошибка инициализации БД: {e}")
            
    def save_image_embedding(self, path, embedding):
        if embedding is None:
            return
        try:
            emb_bytes = np.array(embedding, dtype=np.float32).tobytes()
            with self._get_connection() as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO images (path, clip_embedding) VALUES (?, ?)",
                    (path, emb_bytes)
                )
                conn.commit()
        except Exception as e:
            logger.error(f"Ошибка сохранения вектора изображения {path}: {e}")
            
    def get_image_embedding(self, path):
        try:
            with self._get_connection() as conn:
                row = conn.execute("SELECT clip_embedding FROM images WHERE path = ?", (path,)).fetchone()
                if row and row['clip_embedding']:
                    return np.frombuffer(row['clip_embedding'], dtype=np.float32)
        except Exception as e:
            logger.error(f"Ошибка получения вектора {path}: {e}")
        return None
        
    def save_face(self, image_path, bbox, embedding, name=None):
        try:
            emb_bytes = np.array(embedding, dtype=np.float32).tobytes()
            bbox_str = json.dumps(list(bbox))
            with self._get_connection() as conn:
                conn.execute(
                    "INSERT INTO faces (image_path, bbox, embedding, name) VALUES (?, ?, ?, ?)",
                    (image_path, bbox_str, emb_bytes, name)
                )
                conn.commit()
        except Exception as e:
            logger.error(f"Ошибка сохранения лица для {image_path}: {e}")
            
    def get_all_faces(self):
        try:
            with self._get_connection() as conn:
                rows = conn.execute("SELECT id, image_path, bbox, embedding, name FROM faces").fetchall()
                faces = []
                for r in rows:
                    faces.append({
                        "id": r["id"],
                        "image_path": r["image_path"],
                        "bbox": json.loads(r["bbox"]),
                        "embedding": np.frombuffer(r["embedding"], dtype=np.float32),
                        "name": r["name"]
                    })
                return faces
        except Exception as e:
            logger.error(f"Ошибка получения лиц из БД: {e}")
            return []
            
    def update_faces_by_ids(self, face_ids, name):
        try:
            with self._get_connection() as conn:
                placeholders = ",".join("?" for _ in face_ids)
                conn.execute(f"UPDATE faces SET name = ? WHERE id IN ({placeholders})", (name, *face_ids))
                conn.commit()
        except Exception as e:
            logger.error(f"Ошибка обновления имен группы лиц: {e}")
            
    def get_all_embeddings(self):
        try:
            with self._get_connection() as conn:
                rows = conn.execute("SELECT path, clip_embedding FROM images").fetchall()
                return {r['path']: np.frombuffer(r['clip_embedding'], dtype=np.float32) for r in rows if r['clip_embedding']}
        except Exception as e:
            logger.error(f"Ошибка чтения всех векторов: {e}")
            return {}