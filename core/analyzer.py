# core/analyzer.py

import os
import io

import rawpy
import numpy as np
import cv2
import imagehash
from PIL import Image, UnidentifiedImageError
from skimage.exposure import match_histograms
from core.settings_manager import settings
import hashlib

try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
except ImportError:
    pass

# --- Константы ---
THUMBNAIL_SIZE = (256, 256)
RAW_FORMATS = ('.arw', '.cr2', '.cr3', '.nef', '.nrw', '.dng', '.raw', '.rw2', '.orf', '.pef',
               '.raf', '.srw', '.x3f', '.3fr', '.ari', '.bay', '.cap', '.iiq', '.eip', '.fff',
               '.mef', '.mos', '.mrw', '.nrw', '.rwl', '.rwz', '.sr2', '.srf', '.sti')
VIDEO_FORMATS = ('.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v',
                 '.mpg', '.mpeg', '.3gp', '.ogv', '.ts', '.mts', '.m2ts')


def calculate_phash(image: Image.Image) -> str:
    """Вычисляет перцептивный хеш изображения"""
    try:
        return str(imagehash.average_hash(image))
    except Exception as e:
        return ""


def calculate_sharpness(image: Image.Image) -> float:
    """Вычисляет резкость изображения методом Лапласа"""
    try:
        image_cv = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2GRAY)
        laplacian_var = cv2.Laplacian(image_cv, cv2.CV_64F).var()
        return float(laplacian_var)
    except Exception as e:
        return 0.0


def _extract_video_frame(file_path: str) -> Image.Image:
    """Извлекает первый кадр из видео для миниатюры"""
    try:
        cap = cv2.VideoCapture(file_path)
        ret, frame = cap.read()
        cap.release()

        if ret and frame is not None:
            # Конвертируем BGR в RGB
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            return Image.fromarray(rgb_frame)
        return None
    except Exception as e:
        print(f"[ERROR] Ошибка извлечения кадра из видео {file_path}: {e}")
        return None


def _load_image_optimized(file_path: str, for_thumbnail: bool = False) -> Image.Image:
    """
    Оптимизированная загрузка изображения.
    Для RAW файлов пытается извлечь встроенное превью, если это нужно только для миниатюры/хеша.
    Для видео извлекает первый кадр.
    """
    is_raw = file_path.lower().endswith(RAW_FORMATS)
    is_video = file_path.lower().endswith(VIDEO_FORMATS)

    try:
        if is_video:
            return _extract_video_frame(file_path)
        elif is_raw:
            with rawpy.imread(file_path) as raw:
                # ОПТИМИЗАЦИЯ: Пытаемся извлечь встроенный thumbnail
                if for_thumbnail:
                    try:
                        thumb = raw.extract_thumb()
                        if thumb.format == rawpy.ThumbFormat.JPEG:
                            return Image.open(io.BytesIO(thumb.data)).convert('RGB')
                        elif thumb.format == rawpy.ThumbFormat.BITMAP:
                            # Для bitmap thumbnail
                            return Image.fromarray(thumb.data).convert('RGB')
                    except Exception:
                        pass  # Если не вышло, падаем в полную обработку ниже

                # Полная обработка (если не вышло извлечь thumb или нужен полный размер)
                use_half_size = settings.get_raw_quality() == "half"
                # Если нужно только для миниатюры, всегда используем half_size для скорости
                if for_thumbnail:
                    use_half_size = True

                rgb = raw.postprocess(use_camera_wb=True, output_bps=8, half_size=use_half_size)
                return Image.fromarray(rgb)
        else:
            with Image.open(file_path) as img:
                if img.mode not in ('RGB', 'L'):
                    return img.convert('RGB').copy()
                else:
                    return img.copy()

    except UnidentifiedImageError:
        print(f"[ERROR] Невозможно определить формат изображения: {file_path}")
        return None
    except Exception as e:
        print(f"[ERROR] Ошибка загрузки изображения {file_path}: {e}")
        return None

def _load_image(file_path: str) -> Image.Image:
    # Редактору нужно полное качество, поэтому for_thumbnail=False
    return _load_image_optimized(file_path, for_thumbnail=False)

def _create_thumbnail(pil_image: Image.Image, file_path: str) -> str:
    """Создает миниатюру с кешированием"""
    cache_dir = settings.get_thumbnail_cache_path()
    try:
        os.makedirs(cache_dir, exist_ok=True)
    except OSError as e:
        print(f"КРИТИЧЕСКАЯ ОШИБКА: не удалось создать папку кэша {cache_dir}: {e}")
        return None

    try:
        mtime = os.path.getmtime(file_path)
        hash_key = f"{file_path}{mtime}".encode('utf-8')
        cache_filename = hashlib.sha1(hash_key).hexdigest() + ".jpg"
        cached_thumb_path = os.path.join(cache_dir, cache_filename)

        if os.path.exists(cached_thumb_path):
            return cached_thumb_path

        thumb_img = pil_image.copy()
        thumb_img.thumbnail(THUMBNAIL_SIZE, Image.Resampling.LANCZOS)

        if thumb_img.mode != 'RGB':
            thumb_img = thumb_img.convert('RGB')

        thumb_img.save(cached_thumb_path, "JPEG", quality=90, optimize=True)
        return cached_thumb_path
    except Exception as e:
        print(f"[ERROR] Ошибка создания миниатюры для {file_path}: {e}")
        return None


def process_single_file(file_path: str) -> dict:
    """
    Обрабатывает один файл с оптимизациями и автоматическим анализом.
    """
    try:
        # 1. Загружаем изображение (оптимизировано для анализа)
        pil_image = _load_image_optimized(file_path, for_thumbnail=True)

        if not pil_image:
            return None

        # 2. Создаем миниатюру
        thumbnail_path = _create_thumbnail(pil_image, file_path)

        # 3. Считаем хеш (по уменьшенному изображению это быстрее)
        phash = calculate_phash(pil_image)

        # 4. Считаем резкость
        sharpness = 0.0
        if settings.get_calculate_sharpness():
            sharpness = calculate_sharpness(pil_image)

        # 5. АВТОАНАЛИЗ: Определяем лица
        faces_count = 0
        try:
            from core.face_detector import FaceDetector
            detector = FaceDetector.get_instance()
            if detector.available:
                faces_count = detector.count_faces(file_path)
        except Exception as e:
            print(f"[WARN] Ошибка детекции лиц для {file_path}: {e}")

        # 6. АВТОАНАЛИЗ: Определяем животных
        animals_count = 0
        try:
            from core.animal_detector import AnimalDetector
            detector = AnimalDetector.get_instance()
            if detector.available:
                animals_count = detector.count_animals(file_path)
        except Exception as e:
            print(f"[WARN] Ошибка детекции животных для {file_path}: {e}")

        # 7. АВТОАНАЛИЗ: Получаем GPS координаты
        gps_location = None
        try:
            from core.geotag_manager import get_geolocation
            geolocation = get_geolocation(file_path)
            if geolocation:
                gps_location = (geolocation.latitude, geolocation.longitude)
        except Exception as e:
            print(f"[WARN] Ошибка получения GPS для {file_path}: {e}")

        # 8. АВТОАНАЛИЗ: Вычисляем aspect ratio
        aspect_ratio = 0.0
        if pil_image.width > 0 and pil_image.height > 0:
            aspect_ratio = pil_image.width / pil_image.height

        # 9. АВТОАНАЛИЗ: Камера и дата из EXIF
        camera_model = ""
        date_taken = ""
        try:
            from core.metadata_reader import read_metadata
            meta = read_metadata(file_path)
            camera_model = meta.get("Camera Model Name", "")
            date_taken = meta.get("Date/Time Original", "")
        except Exception:
            pass

        pil_image.close()

        if not thumbnail_path:
            return None

        return {
            "path": file_path,
            "phash": phash,
            "sharpness": sharpness,
            "thumbnail_path": thumbnail_path,
            "faces_count": faces_count,
            "animals_count": animals_count,
            "gps_location": gps_location,
            "aspect_ratio": aspect_ratio,
            "camera_model": camera_model,
            "date_taken": date_taken,
        }
    except Exception as e:
        print(f"[ERROR] Ошибка обработки файла {file_path}: {e}")
        return None


def transfer_style(source_image: Image.Image, target_image: Image.Image) -> Image.Image:
    """Переносит цветовую схему с одного изображения на другое"""
    try:
        source_np = np.array(source_image)
        target_np = np.array(target_image)

        if source_np.ndim != 3 or target_np.ndim != 3:
            return None

        matched_np = match_histograms(target_np, source_np, channel_axis=-1)
        return Image.fromarray(matched_np.astype('uint8'), 'RGB')
    except Exception as e:
        print(f"[ERROR] Ошибка переноса стиля: {e}")
        return None
# --- END OF FILE core/analyzer.py ---