# ═══════════════════════════════════════════════════════════════════════════
# ПАТЧ для controllers/photo_view_controller.py
# Добавить фоновый AI-проход после сканирования.
# Менять нужно только 3 места — остальной код не трогать.
# ═══════════════════════════════════════════════════════════════════════════

# ── МЕСТО 1: В __init__ добавить после self.duplicate_finder = ... ──────────

        from core.ai_worker import AIProcessingManager
        self._ai_manager = AIProcessingManager()

# ── МЕСТО 2: Метод _on_scan_finished_logic — добавить запуск AI в конце ────
# Найди метод _on_scan_finished_logic и добавь в самый конец перед except:

            # Запускаем фоновый AI-проход после того как галерея показана
            self._start_ai_processing()

# ── МЕСТО 3: Добавить новые методы в класс MainController ──────────────────
# Вставить после метода _on_scan_finished_logic:

    def _start_ai_processing(self):
        """Запускает фоновую AI-детекцию лиц и животных."""
        if not self.image_data:
            return

        # Сначала файлы с людьми (по имени — эвристика) идут первыми,
        # чтобы лица появлялись быстрее. Остальные — в порядке сканирования.
        paths = [info.path for info in self.image_data]

        self._ai_manager.start(
            image_paths=paths,
            on_result=self._on_ai_result,
            on_progress=self._on_ai_progress,
            on_finished=self._on_ai_finished,
        )
        self.view.statusBar().showMessage(
            f"Анализ ИИ: запущен для {len(paths)} фото..."
        )

    def _on_ai_result(self, result: dict):
        """Обновляет ImageInfo когда AI обработал файл."""
        path = result.get("path")
        if not path:
            return

        # Находим соответствующий ImageInfo
        for info in self.image_data:
            if info.path == path:
                info.faces_count   = result.get("faces_count", 0)
                info.animals_count = result.get("animals_count", 0)
                info.animal_species = result.get("animal_species", [])
                info.tags          = result.get("tags", [])
                break

        # Обновляем бейдж на миниатюре если он есть
        try:
            self.view.update_thumbnail_badge(path, result)
        except Exception:
            pass  # Метод может отсутствовать в старых версиях view

        # Обновляем умные коллекции периодически
        # (не на каждый файл — дорого)

    def _on_ai_progress(self, done: int, total: int):
        """Обновляет статус-бар с прогрессом AI."""
        self.view.statusBar().showMessage(
            f"ИИ анализ: {done}/{total} фото обработано..."
        )

    def _on_ai_finished(self):
        """Вызывается когда AI-проход завершён."""
        logging.info("AIProcessingManager: анализ завершён")
        self.view.statusBar().showMessage(
            f"ИИ анализ завершён. Обработано: {len(self.image_data)} фото."
        )
        # Обновляем умные коллекции с AI-данными
        if hasattr(self.view, 'smart_collections'):
            self.view.smart_collections.set_images(self.image_data)
        # Обновляем стили миниатюр (бейджи лиц/животных)
        self.view.update_thumbnail_styles()

# ── МЕСТО 4: В методе cleanup() добавить остановку AI ──────────────────────
# Найди метод cleanup() и добавь в начало перед if self.scanner:

        if hasattr(self, '_ai_manager'):
            self._ai_manager.stop()
