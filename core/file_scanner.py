import os
from concurrent.futures import ProcessPoolExecutor, as_completed
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot
from models.image_model import ImageInfo
from core.analyzer import process_single_file
from core.settings_manager import settings

SUPPORTED_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.bmp', '.gif', '.tiff', '.webp',
                        '.arw', '.cr2', '.nef', '.dng', '.raw')


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
                futures = {self.executor.submit(process_single_file, path): path
                           for path in files_to_process}

                for future in as_completed(futures):
                    if not self.is_running: break
                    file_path = futures[future]
                    try:
                        result_data = future.result(timeout=60) # Увеличим таймаут для больших RAW

                        if result_data and result_data.get("thumbnail_path"):
                            self.image_processed.emit(ImageInfo(**result_data))
                        else:
                            print(f"Пропущен файл (нет результата): {file_path}")
                    except Exception as e:
                        print(f"Ошибка обработки файла {file_path}: {e}")

                    processed_count += 1
                    self.progress_updated.emit(processed_count, total_files)
            finally:
                if self.executor:
                    self.executor.shutdown(wait=True, cancel_futures=not self.is_running)
                    self.executor = None
        except Exception as e:
            print(f"Критическая ошибка в сканере: {type(e).__name__}: {e}")
        finally:
            self.finished.emit()

    def stop(self):
        """Безопасная остановка сканирования"""
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
                            full_path = os.path.join(dirpath, filename)
                            # <<< ИСПРАВЛЕНИЕ: Нормализуем путь
                            files.append(os.path.normpath(full_path))
            else:
                for filename in os.listdir(root_folder):
                    path = os.path.join(root_folder, filename)
                    if os.path.isfile(path) and path.lower().endswith(SUPPORTED_EXTENSIONS):
                        # <<< ИСПРАВЛЕНИЕ: Нормализуем путь
                        files.append(os.path.normpath(path))
        except Exception as e:
            print(f"Ошибка сбора файлов: {e}")
        return files
# --- END OF FILE core/file_scanner.py ---