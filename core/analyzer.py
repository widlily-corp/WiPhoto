# core/analyzer.py

import os
import io
import logging

import rawpy
import numpy as np
import cv2
import imagehash
from PIL import Image, UnidentifiedImageError
from skimage.exposure import match_histograms
from core.settings_manager import settings
import hashlib

logger = logging.getLogger(__name__)

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
    except Exception:
        return ""


def calculate_sharpness(image: Image.Image) -> float:
    """Вычисляет резкость изображения методом Лапласа"""
    try:
        image_cv = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2GRAY)
        return float(cv2.Laplacian(image_cv, cv2.CV_64F).var())
    except Exception:
        return 0.0


def _extract_video_frame(file_path: str) -> Image.Image | None:
    """Извлекает первый кадр из видео для миниатюры"""
    cap = None
    try:
        cap = cv2.VideoCapture(file_path)
        ret, frame = cap.read()
        if ret and frame is not None:
            return Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        return None
    except Exception as e:
        logger.error(f"Ошибка извлечения кадра из видео {file_path}: {e}")
        return None
    finally:
        if cap is not None:
            cap.release()


def _load_image_optimized(file_path: str, for_thumbnail: bool = False) -> Image.Image | None:
    """
    Загружает изображение один раз.
    Для RAW пытается встроенный thumbnail, потом half-size постпроцессинг.
    """
    is_raw = file_path.lower().endswith(RAW_FORMATS)
    is_video = file_path.lower().endswith(VIDEO_FORMATS)

    try:
        if is_video:
            return _extract_video_frame(file_path)
        elif is_raw:
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

                use_half_size = for_thumbnail or settings.get_raw_quality() == "half"
                rgb = raw.postprocess(use_camera_wb=True, output_bps=8, half_size=use_half_size)
                return Image.fromarray(rgb)
        else:
            with Image.open(file_path) as img:
                if img.mode not in ('RGB', 'L'):
                    return img.convert('RGB').copy()
                return img.copy()

    except UnidentifiedImageError:
        logger.error(f"Невозможно определить формат: {file_path}")
        return None
    except Exception as e:
        logger.error(f"Ошибка загрузки изображения {file_path}: {e}")
        return None


def _load_image(file_path: str) -> Image.Image | None:
    return _load_image_optimized(file_path, for_thumbnail=False)


def _create_thumbnail(pil_image: Image.Image, file_path: str) -> str | None:
    """Создает миниатюру с кешированием"""
    cache_dir = settings.get_thumbnail_cache_path()
    try:
        os.makedirs(cache_dir, exist_ok=True)
    except OSError as e:
        logger.error(f"Не удалось создать папку кэша {cache_dir}: {e}")
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
        logger.error(f"Ошибка создания миниатюры для {file_path}: {e}")
        return None


def process_single_file(file_path: str) -> dict | None:
    """
    Обрабатывает один файл.
    Изображение загружается ОДИН РАЗ и передаётся во все анализаторы —
    детекторы лиц/животных принимают PIL Image, а не путь к файлу.
    """
    try:
        # ── 1. Единственная загрузка с диска ──────────────────────────────
        pil_image = _load_image_optimized(file_path, for_thumbnail=True)
        if pil_image is None:
            return None

        # ── 2. Thumbnail ───────────────────────────────────────────────────
        thumbnail_path = _create_thumbnail(pil_image, file_path)
        if not thumbnail_path:
            pil_image.close()
            return None

        # ── 3. Хеш и резкость (по уменьшенной копии) ──────────────────────
        phash = calculate_phash(pil_image)
        sharpness = calculate_sharpness(pil_image) if settings.get_calculate_sharpness() else 0.0

        # ── 4. Размеры файла и изображения ────────────────────────────────
        img_width, img_height = pil_image.width, pil_image.height
        aspect_ratio = img_width / img_height if img_height > 0 else 0.0
        try:
            file_size = os.path.getsize(file_path)
        except OSError:
            file_size = 0

        # ── 5. Детекция лиц — передаём уже загруженный PIL Image ──────────
        faces_count = 0
        try:
            from core.face_detector import FaceDetector
            detector = FaceDetector.get_instance()
            if detector.available:
                # TODO: если твой FaceDetector принимает только path, добавь метод
                # count_faces_from_image(pil_image) и вызывай его здесь.
                # Ниже — safe fallback на path, но без повторной загрузки через PIL —
                # детектор всё равно конвертирует в numpy внутри.
                faces_count = detector.count_faces_from_image(pil_image)
        except AttributeError:
            # Старый API — fallback на path (но хотя бы PIL уже в памяти)
            try:
                from core.face_detector import FaceDetector
                faces_count = FaceDetector.get_instance().count_faces(file_path)
            except Exception as e:
                logger.warning(f"Ошибка детекции лиц для {file_path}: {e}")
        except Exception as e:
            logger.warning(f"Ошибка детекции лиц для {file_path}: {e}")

        # ── 6. Детекция животных/объектов — тоже PIL Image ────────────────
        animals_count = 0
        animal_species: list = []
        auto_tags: list = []
        try:
            from core.animal_detector import AnimalDetector
            detector = AnimalDetector.get_instance()
            if detector.available:
                animals_count  = detector.count_animals_from_image(pil_image)
                animal_species = detector.get_animal_species_from_image(pil_image)
                auto_tags      = detector.get_tags_from_image(pil_image)
        except AttributeError:
            # Старый API — fallback
            try:
                from core.animal_detector import AnimalDetector
                d = AnimalDetector.get_instance()
                if d.available:
                    animals_count  = d.count_animals(file_path)
                    animal_species = d.get_animal_species(file_path)
                    auto_tags      = d.get_tags(file_path)
            except Exception as e:
                logger.warning(f"Ошибка детекции животных для {file_path}: {e}")
        except Exception as e:
            logger.warning(f"Ошибка детекции животных для {file_path}: {e}")

        # ── 7. GPS из EXIF (ExifTool daemon — не перечитывает PIL) ────────
        gps_location = None
        try:
            from core.geotag_manager import get_geolocation
            geolocation = get_geolocation(file_path)
            if geolocation:
                gps_location = (geolocation.latitude, geolocation.longitude)
        except Exception as e:
            logger.warning(f"Ошибка получения GPS для {file_path}: {e}")

        # ── 8. EXIF-метаданные (ExifTool daemon — один процесс, не новый) ─
        camera_model = ""
        date_taken = ""
        try:
            from core.metadata_reader import read_metadata
            meta = read_metadata(file_path)
            camera_model = meta.get("Camera Model Name", "")
            date_taken   = meta.get("Date/Time Original", "")
        except Exception:
            pass

        # ── 9. Освобождаем память ──────────────────────────────────────────
        pil_image.close()

        return {
            "path":           file_path,
            "phash":          phash,
            "sharpness":      sharpness,
            "thumbnail_path": thumbnail_path,
            "faces_count":    faces_count,
            "animals_count":  animals_count,
            "gps_location":   gps_location,
            "aspect_ratio":   aspect_ratio,
            "camera_model":   camera_model,
            "date_taken":     date_taken,
            "width":          img_width,
            "height":         img_height,
            "file_size":      file_size,
            "animal_species": animal_species,
            "tags":           auto_tags,
        }

    except Exception as e:
        logger.error(f"Ошибка обработки файла {file_path}: {e}")
        return None


def transfer_style(source_image: Image.Image, target_image: Image.Image) -> Image.Image | None:
    """Переносит цветовую схему с одного изображения на другое"""
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
