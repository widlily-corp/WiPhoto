# core/settings_manager.py

import multiprocessing
from PyQt6.QtCore import QSettings, QDir


KEY_WORKER_COUNT = "performance/worker_count"
KEY_RAW_QUALITY = "performance/raw_quality"
KEY_CALC_SHARPNESS = "performance/calculate_sharpness"
KEY_HAMMING_THRESHOLD = "general/hamming_threshold"
KEY_THUMBNAIL_CACHE_PATH = "cache/thumbnail_path"
KEY_CLIPDROP_API_KEY = "api/clipdrop_key"
class SettingsManager:
    def __init__(self):

        self.settings = QSettings("WiPhoto", "Widlily Corporation")
        self._set_defaults()

    def _set_defaults(self):
        """Устанавливает значения по умолчанию, если они еще не заданы."""
        # --- Производительность ---
        if not self.settings.contains(KEY_WORKER_COUNT):
            # По умолчанию используем все ядра минус одно, но не меньше одного
            cpu_count = multiprocessing.cpu_count()
            default_workers = max(1, cpu_count - 1)
            self.settings.setValue(KEY_WORKER_COUNT, default_workers)
        if not self.settings.contains(KEY_RAW_QUALITY):
            self.settings.setValue(KEY_RAW_QUALITY, "half") # 'full' or 'half'
        if not self.settings.contains(KEY_CALC_SHARPNESS):
            self.settings.setValue(KEY_CALC_SHARPNESS, True)

        # --- Общие ---
        if not self.settings.contains(KEY_HAMMING_THRESHOLD):
            self.settings.setValue(KEY_HAMMING_THRESHOLD, 5)

        # --- Кэш ---
        if not self.settings.contains(KEY_THUMBNAIL_CACHE_PATH):
            cache_path = QDir(QDir.homePath()).filePath(".wiphoto/cache/thumbnails")
            QDir().mkpath(cache_path) # Создаем директорию, если ее нет
            self.settings.setValue(KEY_THUMBNAIL_CACHE_PATH, cache_path)
        if not self.settings.contains(KEY_CLIPDROP_API_KEY):
            self.settings.setValue(KEY_CLIPDROP_API_KEY, "")
    def get_worker_count(self) -> int:
        return self.settings.value(KEY_WORKER_COUNT, type=int)

    def set_worker_count(self, value: int):
        self.settings.setValue(KEY_WORKER_COUNT, value)

    def get_raw_quality(self) -> str:
        return self.settings.value(KEY_RAW_QUALITY, type=str)

    def set_raw_quality(self, value: str):
        self.settings.setValue(KEY_RAW_QUALITY, value)

    def get_calculate_sharpness(self) -> bool:
        return self.settings.value(KEY_CALC_SHARPNESS, type=bool)

    def set_calculate_sharpness(self, value: bool):
        self.settings.setValue(KEY_CALC_SHARPNESS, value)

    def get_hamming_threshold(self) -> int:
        return self.settings.value(KEY_HAMMING_THRESHOLD, type=int)

    def set_hamming_threshold(self, value: int):
        self.settings.setValue(KEY_HAMMING_THRESHOLD, value)

    def get_thumbnail_cache_path(self) -> str:
        return self.settings.value(KEY_THUMBNAIL_CACHE_PATH, type=str)

    def get_clipdrop_key(self) -> str:
        # Принудительно возвращаем строку и удаляем пробелы (strip)
        val = self.settings.value(KEY_CLIPDROP_API_KEY, "", type=str)
        return str(val).strip() if val else ""

    def set_clipdrop_key(self, value: str):
        # Удаляем пробелы перед сохранением
        clean_value = str(value).strip()
        self.settings.setValue(KEY_CLIPDROP_API_KEY, clean_value)
        # Принудительно синхронизируем настройки с диском/реестром
        self.settings.sync()

# Глобальный экземпляр, чтобы все части приложения работали с одними настройками
settings = SettingsManager()