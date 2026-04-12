import os
import logging
from concurrent.futures import ProcessPoolExecutor, as_completed
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot
from models.image_model import ImageInfo
from core.analyzer import process_single_file, _worker_initializer
from core.settings_manager import settings

logger = logging.getLogger(__name__)

SUPPORTED_IMAGE_EXTENSIONS = frozenset((
    '.jpg', '.jpeg', '.jpe', '.jfif', '.png', '.bmp', '.gif', '.tiff', '.tif', '.webp',
    '.ico', '.ppm', '.pgm', '.pbm', '.pnm',
    '.heic', '.heif', '.avif', '.jp2', '.j2k', '.jpx', '.jpm',
    '.arw', '.cr2', '.cr3', '.nef', '.nrw', '.dng', '.raw', '.rw2', '.orf', '.pef',
    '.raf', '.srw', '.x3f', '.3fr', '.ari', '.bay', '.cap', '.iiq', '.eip', '.fff',
    '.mef', '.mos', '.mrw', '.nrw', '.rwl', '.rwz', '.sr2', '.srf', '.sti'
))

SUPPORTED_VIDEO_EXTENSIONS = frozenset((
    '.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v',
    '.mpg', '.mpeg', '.3gp', '.ogv', '.ts', '.mts', '.m2ts'
))

SUPPORTED_EXTENSIONS = SUPPORTED_IMAGE_EXTENSIONS | SUPPORTED_VIDEO_EXTENSIONS

_PROGRESS_STEP = 5
_CHUNK_SIZE = 200
_RAM_PER_WORKER_MB = 200  # Без AI моделей воркеры лёгкие


def _get_safe_worker_count(requested: int) -> int:
    try:
        import psutil
        available_mb = psutil.virtual_memory().available // (1024 * 1024)
        usable_mb = int(available_mb * 0.8)
        ram_limit = max(1, usable_mb // _RAM_PER_WORKER_MB)
        safe = min(requested, ram_limit)
        if safe < requested:
            logger.info(f"Воркеров ограничено до {safe} (RAM: {available_mb} МБ)")
        return safe
    except ImportError:
        return min(requested, os.cpu_count() or 2)


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

            worker_count = _get_safe_worker_count(settings.get_worker_count())

            # initializer загружает кэш + ExifTool daemon один раз на воркер.
            # AI-модели НЕ загружаются — сканирование теперь чисто быстрое.
            self.executor = ProcessPoolExecutor(
                max_workers=worker_count,
                initializer=_worker_initializer,
            )

            try:
                for chunk_start in range(0, total_files, _CHUNK_SIZE):
                    if not self.is_running:
                        break

                    chunk = files_to_process[chunk_start: chunk_start + _CHUNK_SIZE]
                    futures = {
                        self.executor.submit(process_single_file, path): path
                        for path in chunk
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
                                logger.debug(f"Пропущен: {file_path}")
                        except Exception as e:
                            logger.warning(f"Ошибка {file_path}: {e}")

                        processed_count += 1
                        if processed_count % _PROGRESS_STEP == 0 or processed_count == total_files:
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

    def _collect_files(self, root_folder: str, is_recursive: bool) -> list[str]:
        files: list[str] = []
        try:
            if is_recursive:
                self._scandir_recursive(root_folder, files)
            else:
                self._scandir_flat(root_folder, files)
        except Exception as e:
            logger.error(f"Ошибка сбора файлов: {e}")
        return files

    def _scandir_flat(self, folder: str, files: list[str]) -> None:
        with os.scandir(folder) as it:
            for entry in it:
                if entry.is_file(follow_symlinks=False):
                    ext = os.path.splitext(entry.name)[1].lower()
                    if ext in SUPPORTED_EXTENSIONS:
                        files.append(os.path.normpath(entry.path))

    def _scandir_recursive(self, folder: str, files: list[str]) -> None:
        stack = [folder]
        while stack:
            current = stack.pop()
            try:
                with os.scandir(current) as it:
                    for entry in it:
                        if entry.is_dir(follow_symlinks=False):
                            stack.append(entry.path)
                        elif entry.is_file(follow_symlinks=False):
                            ext = os.path.splitext(entry.name)[1].lower()
                            if ext in SUPPORTED_EXTENSIONS:
                                files.append(os.path.normpath(entry.path))
            except PermissionError as e:
                logger.warning(f"Нет доступа: {current}: {e}")
# --- END OF FILE core/file_scanner.py ---
