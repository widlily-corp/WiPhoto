import os
import logging
from concurrent.futures import ProcessPoolExecutor, as_completed
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot
from models.image_model import ImageInfo
from core.analyzer import process_single_file
from core.settings_manager import settings

logger = logging.getLogger(__name__)

SUPPORTED_IMAGE_EXTENSIONS = (
    '.jpg', '.jpeg', '.jpe', '.jfif', '.png', '.bmp', '.gif', '.tiff', '.tif', '.webp',
    '.ico', '.ppm', '.pgm', '.pbm', '.pnm',
    '.heic', '.heif', '.avif', '.jp2', '.j2k', '.jpx', '.jpm',
    '.arw', '.cr2', '.cr3', '.nef', '.nrw', '.dng', '.raw', '.rw2', '.orf', '.pef',
    '.raf', '.srw', '.x3f', '.3fr', '.ari', '.bay', '.cap', '.iiq', '.eip', '.fff',
    '.mef', '.mos', '.mrw', '.nrw', '.rwl', '.rwz', '.sr2', '.srf', '.sti'
)

SUPPORTED_VIDEO_EXTENSIONS = (
    '.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v',
    '.mpg', '.mpeg', '.3gp', '.ogv', '.ts', '.mts', '.m2ts'
)

SUPPORTED_EXTENSIONS = SUPPORTED_IMAGE_EXTENSIONS + SUPPORTED_VIDEO_EXTENSIONS

# Приблизительный объём памяти одного воркера с YOLO + PIL + NumPy буферами.
# Если твои детекторы весят больше — подними это число.
_RAM_PER_WORKER_MB = 400


def _get_safe_worker_count(requested: int) -> int:
    """
    Ограничивает число воркеров исходя из доступной RAM.
    Без psutil просто берёт min(requested, cpu_count).
    """
    try:
        import psutil
        available_mb = psutil.virtual_memory().available // (1024 * 1024)
        # Оставляем 20% RAM для системы и основного процесса
        usable_mb = int(available_mb * 0.8)
        ram_limit = max(1, usable_mb // _RAM_PER_WORKER_MB)
        safe = min(requested, ram_limit)
        if safe < requested:
            logger.info(
                f"Воркеров ограничено до {safe} (RAM: {available_mb} МБ доступно, "
                f"~{_RAM_PER_WORKER_MB} МБ на воркер)"
            )
        return safe
    except ImportError:
        import os
        cpu_count = os.cpu_count() or 2
        return min(requested, cpu_count)


class Scanner(QObject):
    image_processed = pyqtSignal(ImageInfo)
    progress_updated = pyqtSignal(int, int)
    finished = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.is_running = True
        self.executor = None

    @pyqtSlot(str, bool)
    def start_scanning(self, root_folder: str, is_recursive: bool):
        self.is_running = True

        try:
            files_to_process = self._collect_files(root_folder, is_recursive)
            total_files = len(files_to_process)

            if total_files == 0:
                self.finished.emit()
                return

            self.progress_updated.emit(0, total_files)
            processed_count = 0

            requested_workers = settings.get_worker_count()
            worker_count = _get_safe_worker_count(requested_workers)

            self.executor = ProcessPoolExecutor(max_workers=worker_count)
            try:
                futures = {
                    self.executor.submit(process_single_file, path): path
                    for path in files_to_process
                }

                for future in as_completed(futures):
                    if not self.is_running:
                        break
                    file_path = futures[future]
                    try:
                        result_data = future.result(timeout=60)
                        if result_data and result_data.get("thumbnail_path"):
                            self.image_processed.emit(ImageInfo(**result_data))
                        else:
                            logger.debug(f"Пропущен файл (нет результата): {file_path}")
                    except Exception as e:
                        logger.warning(f"Ошибка обработки файла {file_path}: {e}")

                    processed_count += 1
                    self.progress_updated.emit(processed_count, total_files)
            finally:
                if self.executor:
                    self.executor.shutdown(wait=True, cancel_futures=not self.is_running)
                    self.executor = None
        except Exception as e:
            logger.error(f"Критическая ошибка в сканере: {type(e).__name__}: {e}")
        finally:
            self.finished.emit()

    def stop(self):
        self.is_running = False
        if self.executor:
            self.executor.shutdown(wait=False, cancel_futures=True)

    def _collect_files(self, root_folder, is_recursive):
        """Собирает список файлов для обработки с нормализацией путей."""
        files = []
        try:
            if is_recursive:
                for dirpath, _, filenames in os.walk(root_folder):
                    for filename in filenames:
                        if filename.lower().endswith(SUPPORTED_EXTENSIONS):
                            files.append(os.path.normpath(os.path.join(dirpath, filename)))
            else:
                for filename in os.listdir(root_folder):
                    path = os.path.join(root_folder, filename)
                    if os.path.isfile(path) and path.lower().endswith(SUPPORTED_EXTENSIONS):
                        files.append(os.path.normpath(path))
        except Exception as e:
            logger.error(f"Ошибка сбора файлов: {e}")
        return files
# --- END OF FILE core/file_scanner.py ---
