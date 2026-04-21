# core/ai_worker.py

import logging
from PyQt6.QtCore import QObject, QThread, pyqtSignal

logger = logging.getLogger(__name__)


class AIWorker(QObject):
    ai_result = pyqtSignal(dict)
    progress  = pyqtSignal(int, int)
    finished  = pyqtSignal()

    def __init__(self, image_paths: list[str]):
        super().__init__()
        self._paths = image_paths
        self._stop = False

    def stop(self):
        self._stop = True

    def run(self):
        total = len(self._paths)
        from core.analyzer import process_ai_for_file

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

    def __init__(self):
        self._thread: QThread | None = None
        self._worker: AIWorker | None = None

    def start(self, image_paths: list[str],
              on_result,
              on_progress,
              on_finished):
        self.stop()

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
        """Останавливает текущий AI-проход."""
        if self._worker:
            self._worker.stop()

        if self._thread and self._thread.isRunning():
            self._thread.quit()
            if not self._thread.wait(3000):
                # Поток не успел остановиться за 3 сек (например, тяжёлая AI-инференция).
                # terminate() — принудительное завершение; безопасно только потому что
                # AIWorker не держит мьютексов и не пишет в разделяемые структуры.
                logger.warning("AIWorker не остановился за 3 с — принудительное завершение")
                self._thread.terminate()
                self._thread.wait(1000)

        self._thread = None
        self._worker = None

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.isRunning()
