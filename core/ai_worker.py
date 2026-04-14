# core/ai_worker.py
#
# Фоновый AI-проход после сканирования.
# Запускается когда все фото уже показаны в галерее.
# Обрабатывает по одному файлу за раз в отдельном потоке —
# не грузит RAM как ProcessPoolExecutor с YOLO в каждом воркере.

import logging
from PyQt6.QtCore import QObject, QThread, pyqtSignal, QTimer

logger = logging.getLogger(__name__)


class AIWorker(QObject):
    """
    Обрабатывает AI-детекцию (лица, животные) в фоне после сканирования.
    Эмитит ai_result с результатами для каждого файла —
    контроллер обновляет соответствующий ImageInfo и бейдж на миниатюре.
    """
    ai_result   = pyqtSignal(dict)   # {path, faces_count, animals_count, ...}
    progress    = pyqtSignal(int, int)
    finished    = pyqtSignal()

    def __init__(self, image_paths: list[str]):
        super().__init__()
        self._paths = image_paths
        self._stop = False

    def stop(self):
        self._stop = True

    def run(self):
        total = len(self._paths)
        from core.analyzer import process_ai_for_file

        # Загружаем модели один раз перед циклом
        face_detector = None
        animal_detector = None
        try:
            from core.face_detector import FaceDetector
            face_detector = FaceDetector.get_instance()
        except Exception as e:
            logger.warning(f"AIWorker: FaceDetector не загружен: {e}")

        try:
            from core.animal_detector import AnimalDetector
            animal_detector = AnimalDetector.get_instance()
        except Exception as e:
            logger.warning(f"AIWorker: AnimalDetector не загружен: {e}")

        for i, path in enumerate(self._paths):
            if self._stop:
                break
            try:
                result = process_ai_for_file(path)
                self.ai_result.emit(result)
            except Exception as e:
                logger.warning(f"AIWorker error {path}: {e}")

            if (i + 1) % 10 == 0 or (i + 1) == total:
                self.progress.emit(i + 1, total)

        self.finished.emit()


class AIProcessingManager:
    """
    Управляет запуском и остановкой фонового AI-прохода.
    Используется из MainController.
    """

    def __init__(self):
        self._thread: QThread | None = None
        self._worker: AIWorker | None = None

    def start(self, image_paths: list[str],
              on_result,      # callable(dict)
              on_progress,    # callable(int, int)
              on_finished):   # callable()
        """Запускает фоновый AI-проход."""
        self.stop()  # на случай если предыдущий ещё идёт

        if not image_paths:
            return

        self._thread = QThread()
        self._worker = AIWorker(image_paths)
        self._worker.moveToThread(self._thread)

        self._worker.ai_result.connect(on_result)
        self._worker.progress.connect(on_progress)
        self._worker.finished.connect(on_finished)
        self._worker.finished.connect(self._thread.quit)
        self._thread.started.connect(self._worker.run)

        self._thread.start()
        logger.info(f"AIProcessingManager: запущен для {len(image_paths)} файлов")

    def stop(self):
        """Останавливает текущий AI-проход если он идёт."""
        if self._worker:
            self._worker.stop()
        if self._thread and self._thread.isRunning():
            self._thread.quit()
            self._thread.wait(3000)
        self._thread = None
        self._worker = None

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.isRunning()
