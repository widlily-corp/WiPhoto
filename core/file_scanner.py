import os
import logging
from concurrent.futures import ProcessPoolExecutor, as_completed
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot
from models.image_model import ImageInfo
from core.analyzer import process_single_file
from core.settings_manager import settings

logger = logging.getLogger(__name__)

SUPPORTED_IMAGE_EXTENSIONS = frozenset((
    # Common raster formats
    '.jpg', '.jpeg', '.jpe', '.jfif', '.png', '.bmp', '.gif', '.tiff', '.tif', '.webp',
    '.ico', '.ppm', '.pgm', '.pbm', '.pnm',
    # Additional formats
    '.heic', '.heif', '.avif', '.jp2', '.j2k', '.jpx', '.jpm',
    # RAW formats
    '.arw', '.cr2', '.cr3', '.nef', '.nrw', '.dng', '.raw', '.rw2', '.orf', '.pef',
    '.raf', '.srw', '.x3f', '.3fr', '.ari', '.bay', '.cap', '.iiq', '.eip', '.fff',
    '.mef', '.mos', '.mrw', '.nrw', '.rwl', '.rwz', '.sr2', '.srf', '.sti'
))

SUPPORTED_VIDEO_EXTENSIONS = frozenset((
    '.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v',
    '.mpg', '.mpeg', '.3gp', '.ogv', '.ts', '.mts', '.m2ts'
))

SUPPORTED_EXTENSIONS = SUPPORTED_IMAGE_EXTENSIONS | SUPPORTED_VIDEO_EXTENSIONS

# Сколько файлов сабмитить в executor за один раз.
# Защищает от OOM при огромных папках (10k+ файлов).
_CHUNK_SIZE = 256

# Как часто обновлять прогресс (каждые N файлов).
# Снижает нагрузку на UI-поток при большом объёме.
_PROGRESS_STEP = 10


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
            worker_count = settings.get_worker_count()

            self.executor = ProcessPoolExecutor(max_workers=worker_count)
            try:
                # Обрабатываем чанками — не сабмитим всё сразу в память
                for chunk_start in range(0, total_files, _CHUNK_SIZE):
                    if not self.is_running:
                        break

                    chunk = files_to_process[chunk_start: chunk_start + _CHUNK_SIZE]
                    futures = {self.executor.submit(process_single_file, path): path
                               for path in chunk}

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
                        # Обновляем UI не на каждый файл, а раз в N штук
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
        """Безопасная остановка сканирования"""
        self.is_running = False
        if self.executor:
            self.executor.shutdown(wait=False, cancel_futures=True)

    def _collect_files(self, root_folder: str, is_recursive: bool) -> list[str]:
        """
        Собирает список файлов с использованием os.scandir — быстрее os.walk/listdir,
        так как не делает лишний stat() на каждую запись.
        Расширения проверяются через frozenset (O(1) lookup вместо O(n) endswith tuple).
        """
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
        """Итеративный обход без рекурсии — не роняет стек на глубоких деревьях."""
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
                logger.warning(f"Нет доступа к папке {current}: {e}")
