# core/analyzer.py

import os
import io
import logging
import hashlib

import rawpy
import numpy as np
import cv2
import imagehash
from PIL import Image, UnidentifiedImageError
from skimage.exposure import match_histograms
from core.settings_manager import settings

logger = logging.getLogger(__name__)

try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
except ImportError:
    pass

# --- Константы ---
THUMBNAIL_SIZE = (256, 256)
RAW_FORMATS = frozenset((
    '.arw', '.cr2', '.cr3', '.nef', '.nrw', '.dng', '.raw', '.rw2', '.orf', '.pef',
    '.raf', '.srw', '.x3f', '.3fr', '.ari', '.bay', '.cap', '.iiq', '.eip', '.fff',
    '.mef', '.mos', '.mrw', '.nrw', '.rwl', '.rwz', '.sr2', '.srf', '.sti'
))
VIDEO_FORMATS = frozenset((
    '.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v',
    '.mpg', '.mpeg', '.3gp', '.ogv', '.ts', '.mts', '.m2ts'
))

# ─────────────────────────────────────────────────────────────────────────────
# Состояние воркера — инициализируется ОДИН РАЗ через initializer
# ─────────────────────────────────────────────────────────────────────────────
_worker_cache_dir = None
_worker_calc_sharpness = True
_worker_exiftool_daemon = None


def _worker_initializer():
    """
    Вызывается один раз при старте каждого воркер-процесса.
    Загружает только то что нужно для быстрого сканирования:
    кэш-директорию, настройки и ExifTool daemon.
    AI-модели (YOLO, YuNet) НЕ загружаются здесь — они нужны только
    для фонового AI-прохода после сканирования.
    """
    global _worker_cache_dir, _worker_calc_sharpness, _worker_exiftool_daemon

    try:
        cv2.setLogLevel(0)
    except AttributeError:
        pass

    _worker_cache_dir = settings.get_thumbnail_cache_path()
    os.makedirs(_worker_cache_dir, exist_ok=True)
    _worker_calc_sharpness = settings.get_calculate_sharpness()

    # ExifTool daemon — свой для каждого воркера, поднимается один раз
    try:
        from core.metadata_reader import _ExifToolDaemon, EXIFTOOL_AVAILABLE
        if EXIFTOOL_AVAILABLE:
            _worker_exiftool_daemon = _ExifToolDaemon()
    except Exception as e:
        logger.warning(f"[воркер] ExifTool daemon не запущен: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# Вспомогательные функции
# ─────────────────────────────────────────────────────────────────────────────

def calculate_phash(image: Image.Image) -> str:
    try:
        return str(imagehash.average_hash(image))
    except Exception:
        return ""


def calculate_sharpness(image: Image.Image) -> float:
    try:
        image_cv = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2GRAY)
        return float(cv2.Laplacian(image_cv, cv2.CV_64F).var())
    except Exception:
        return 0.0


def _extract_video_frame(file_path: str) -> Image.Image | None:
    cap = None
    try:
        cap = cv2.VideoCapture(file_path)
        ret, frame = cap.read()
        if ret and frame is not None:
            return Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        return None
    except Exception as e:
        logger.error(f"Ошибка извлечения кадра {file_path}: {e}")
        return None
    finally:
        if cap is not None:
            cap.release()


def _load_image_optimized(file_path: str, for_thumbnail: bool = True) -> Image.Image | None:
    ext = os.path.splitext(file_path)[1].lower()

    try:
        if ext in VIDEO_FORMATS:
            return _extract_video_frame(file_path)
        elif ext in RAW_FORMATS:
            with rawpy.imread(file_path) as raw:
                if for_thumbnail:
                    try:
                        thumb = raw.extract_thumb()
                        if thumb.format == rawpy.ThumbFormat.JPEG:
                            return Image.open(io.BytesIO(thumb.data)).convert('RGB')
                        elif thumb.format == rawpy.ThumbFormat.BITMAP:
                            return Image.fromarray(thumb.data).convert('RGB')
                    except Exception:
                        pass
                use_half = for_thumbnail or settings.get_raw_quality() == "half"
                rgb = raw.postprocess(use_camera_wb=True, output_bps=8, half_size=use_half)
                return Image.fromarray(rgb)
        else:
            with Image.open(file_path) as img:
                if img.mode not in ('RGB', 'L'):
                    return img.convert('RGB').copy()
                return img.copy()
    except UnidentifiedImageError:
        logger.error(f"Неизвестный формат: {file_path}")
        return None
    except Exception as e:
        logger.error(f"Ошибка загрузки {file_path}: {e}")
        return None


def _create_thumbnail(pil_image: Image.Image, file_path: str,
                      cache_dir: str) -> str | None:
    try:
        mtime = os.path.getmtime(file_path)
        hash_key = f"{file_path}{mtime}".encode('utf-8')
        cache_filename = hashlib.sha1(hash_key).hexdigest() + ".jpg"
        cached_path = os.path.join(cache_dir, cache_filename)

        if os.path.exists(cached_path):
            return cached_path

        thumb = pil_image.copy()
        thumb.thumbnail(THUMBNAIL_SIZE, Image.Resampling.LANCZOS)
        if thumb.mode != 'RGB':
            thumb = thumb.convert('RGB')
        thumb.save(cached_path, "JPEG", quality=85, optimize=False)
        return cached_path
    except Exception as e:
        logger.error(f"Ошибка миниатюры {file_path}: {e}")
        return None


def _read_exif_in_worker(file_path: str) -> dict:
    """Читает EXIF через daemon воркера (уже запущен в _worker_initializer)."""
    global _worker_exiftool_daemon
    if _worker_exiftool_daemon is None:
        return {}
    try:
        stdout = _worker_exiftool_daemon.execute(os.path.normpath(file_path))
        if not stdout.strip():
            return {}
        meta = {}
        for line in stdout.splitlines():
            if ':' in line:
                k, _, v = line.partition(':')
                meta[k.strip()] = v.strip()
        return meta
    except Exception:
        return {}


def _parse_gps_coord(coord_str: str, ref: str) -> float | None:
    try:
        import re
        parts = re.findall(r"[\d.]+", coord_str)
        if len(parts) >= 3:
            deg, m, s = float(parts[0]), float(parts[1]), float(parts[2])
        elif len(parts) == 2:
            deg, m, s = float(parts[0]), float(parts[1]), 0.0
        elif len(parts) == 1:
            deg, m, s = float(parts[0]), 0.0, 0.0
        else:
            return None
        result = deg + m / 60 + s / 3600
        if ref in ('S', 'W'):
            result = -result
        return result
    except Exception:
        return None


# ─────────────────────────────────────────────────────────────────────────────
# БЫСТРОЕ сканирование — только thumbnail + hash + EXIF (без AI)
# ─────────────────────────────────────────────────────────────────────────────

def process_single_file(file_path: str) -> dict | None:
    """
    Быстрая обработка файла при сканировании.
    НЕ запускает детекцию лиц и животных — это делается отдельно
    в фоновом AI-проходе после того как все фото показаны в галерее.
    """
    global _worker_cache_dir, _worker_calc_sharpness

    cache_dir = _worker_cache_dir
    if cache_dir is None:
        cache_dir = settings.get_thumbnail_cache_path()
        os.makedirs(cache_dir, exist_ok=True)

    try:
        # ── 1. Загрузка (один раз) ────────────────────────────────────────
        pil_image = _load_image_optimized(file_path, for_thumbnail=True)
        if pil_image is None:
            return None

        # ── 2. Thumbnail ──────────────────────────────────────────────────
        thumbnail_path = _create_thumbnail(pil_image, file_path, cache_dir)
        if not thumbnail_path:
            pil_image.close()
            return None

        # ── 3. Хеш и резкость ────────────────────────────────────────────
        phash = calculate_phash(pil_image)
        sharpness = calculate_sharpness(pil_image) if _worker_calc_sharpness else 0.0

        # ── 4. Размеры ────────────────────────────────────────────────────
        img_width, img_height = pil_image.width, pil_image.height
        aspect_ratio = img_width / img_height if img_height > 0 else 0.0
        try:
            file_size = os.path.getsize(file_path)
        except OSError:
            file_size = 0

        pil_image.close()

        # ── 5. EXIF через daemon (без нового subprocess) ──────────────────
        meta = _read_exif_in_worker(file_path)
        camera_model = meta.get("Camera Model Name", "")
        date_taken = meta.get("Date/Time Original", "")

        gps_location = None
        try:
            lat_str = meta.get("GPS Latitude", "")
            lon_str = meta.get("GPS Longitude", "")
            if lat_str and lon_str:
                lat = _parse_gps_coord(lat_str, meta.get("GPS Latitude Ref", "N"))
                lon = _parse_gps_coord(lon_str, meta.get("GPS Longitude Ref", "E"))
                if lat is not None and lon is not None:
                    gps_location = (lat, lon)
        except Exception:
            pass

        return {
            "path":           file_path,
            "phash":          phash,
            "sharpness":      sharpness,
            "thumbnail_path": thumbnail_path,
            "faces_count":    0,       # заполнится в AI-проходе
            "animals_count":  0,       # заполнится в AI-проходе
            "gps_location":   gps_location,
            "aspect_ratio":   aspect_ratio,
            "camera_model":   camera_model,
            "date_taken":     date_taken,
            "width":          img_width,
            "height":         img_height,
            "file_size":      file_size,
            "animal_species": [],      # заполнится в AI-проходе
            "tags":           [],      # заполнится в AI-проходе
        }

    except Exception as e:
        logger.error(f"Ошибка обработки {file_path}: {e}")
        return None


# ─────────────────────────────────────────────────────────────────────────────
# AI-обработка — только детекция лиц и животных, для уже показанных фото
# ─────────────────────────────────────────────────────────────────────────────

def process_ai_for_file(file_path: str) -> dict:
    """
    Запускается в фоне ПОСЛЕ сканирования.
    Возвращает только AI-поля: faces_count, animals_count, animal_species, tags.
    Вызывается из AIWorker по одному файлу за раз в отдельном потоке.
    """
    result = {
        "path": file_path,
        "faces_count": 0,
        "animals_count": 0,
        "animal_species": [],
        "tags": [],
    }

    try:
        pil_image = _load_image_optimized(file_path, for_thumbnail=True)
        if pil_image is None:
            return result

        # Face detection
        try:
            from core.face_detector import FaceDetector
            fd = FaceDetector.get_instance()
            if fd.available:
                if hasattr(fd, 'count_faces_from_image'):
                    result["faces_count"] = fd.count_faces_from_image(pil_image)
                else:
                    result["faces_count"] = fd.count_faces(file_path)
        except Exception as e:
            logger.warning(f"FaceDetector error {file_path}: {e}")

        # Animal detection
        try:
            from core.animal_detector import AnimalDetector
            ad = AnimalDetector.get_instance()
            if ad.available:
                if hasattr(ad, 'count_animals_from_image'):
                    result["animals_count"]  = ad.count_animals_from_image(pil_image)
                    result["animal_species"] = ad.get_animal_species_from_image(pil_image)
                    result["tags"]           = ad.get_tags_from_image(pil_image)
                else:
                    result["animals_count"]  = ad.count_animals(file_path)
                    result["animal_species"] = ad.get_animal_species(file_path)
                    result["tags"]           = ad.get_tags(file_path)
        except Exception as e:
            logger.warning(f"AnimalDetector error {file_path}: {e}")

        pil_image.close()

    except Exception as e:
        logger.error(f"AI error {file_path}: {e}")

    return result


def transfer_style(source_image: Image.Image, target_image: Image.Image) -> Image.Image | None:
    try:
        source_np = np.array(source_image)
        target_np = np.array(target_image)
        if source_np.ndim != 3 or target_np.ndim != 3:
            return None
        matched_np = match_histograms(target_np, source_np, channel_axis=-1)
        return Image.fromarray(matched_np.astype('uint8'), 'RGB')
    except Exception as e:
        logger.error(f"Ошибка переноса стиля: {e}")
        return None
# --- END OF FILE core/analyzer.py ---
