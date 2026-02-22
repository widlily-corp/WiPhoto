# controllers/photo_view_controller.py

import os
import shutil
from collections import defaultdict

from PIL import Image
from PyQt6.QtCore import QThread, QObject, pyqtSignal, QTimer, Qt
from PyQt6.QtGui import QPixmap, QImage
from PyQt6.QtWidgets import QMessageBox, QFileDialog, QDialog, QVBoxLayout, QLabel, QPushButton, QWidget
from views.progress_dialog import DuplicateSearchDialog, ScanProgressDialog
from core.analyzer import transfer_style
from core.file_scanner import Scanner
from core.metadata_reader import read_exif
from core.advanced_duplicate_finder import AdvancedDuplicateFinder
from models.image_model import ImageInfo
from views.style_preview_dialog import StylePreviewDialog
from core.settings_manager import settings


class MainController(QObject):
    start_scanning_signal = pyqtSignal(str, bool)
    request_editor_display = pyqtSignal(ImageInfo)

    def __init__(self, main_window):
        super().__init__()
        self.view = main_window
        self.image_data = []
        self.groups = defaultdict(list)
        self.is_in_style_mode = False
        self.style_target_info = None

        # Новый продвинутый поисковик дубликатов
        self.duplicate_finder = AdvancedDuplicateFinder()

        self.scanner_thread = QThread()
        self.scanner = Scanner()
        self.scanner.moveToThread(self.scanner_thread)

        # Подключаем сигналы
        self.scanner.image_processed.connect(self._on_image_processed)
        self.scanner.finished.connect(self._on_scan_finished_logic)
        self.start_scanning_signal.connect(self.scanner.start_scanning)

        self._connect_view_signals()

        # Буферизация миниатюр для плавного добавления
        self.thumbnail_buffer = []
        self.add_thumbnail_timer = QTimer()
        self.add_thumbnail_timer.setInterval(50)
        self.add_thumbnail_timer.timeout.connect(self._process_thumbnail_buffer)

        self.scanner_thread.start()
        print("Контроллер вида: готов к работе, поток сканера запущен.")

    def start_scan(self, folder_path, is_recursive):
        """Начинает сканирование папки С ПРОГРЕСС-БАРОМ"""
        self.image_data.clear()
        self.groups.clear()
        self.view.clear_thumbnails()
        self.thumbnail_buffer.clear()
        self.add_thumbnail_timer.start()

        # Создаем диалог прогресса для сканирования
        # (Он уже показывается в welcome_window через progress_bar)
        # Но можно добавить более детальный:

        self.start_scanning_signal.emit(folder_path, is_recursive)

    def _connect_view_signals(self):
        """Подключает сигналы от представления"""
        gallery = self.view.gallery_widget
        main_win = self.view

        # Сигналы от GalleryWidget
        gallery.thumbnail_view.itemClicked.connect(self._on_thumbnail_selected)
        gallery.edit_requested.connect(self._on_edit_requested)

        # Сигналы от MainWindow
        main_win.delete_requested.connect(self.handle_delete)
        main_win.copy_requested.connect(self.handle_copy)
        main_win.move_requested.connect(self.handle_move)
        main_win.keep_best_requested.connect(self.handle_keep_best)
        main_win.style_copy_requested.connect(self.handle_style_request)
        main_win.filter_changed.connect(self.apply_filter)
        main_win.thumbnail_size_changed.connect(self.view.set_thumbnail_size)
        main_win.files_dropped.connect(self.handle_dropped_files)
        main_win.compare_requested.connect(self.handle_compare)

        # Сигнал от контроллера к MainWindow
        self.request_editor_display.connect(main_win.switch_to_editor)

        # ===== ДОБАВЬТЕ ЭТИ СТРОКИ =====
        # Подключаем умные коллекции
        if hasattr(main_win, 'smart_collections'):
            main_win.smart_collections.collection_changed.connect(self._on_collection_changed)
            main_win.smart_collections.image_selected.connect(self._on_smart_collection_image_selected)
        # ================================

    # И ДОБАВЬТЕ НОВЫЙ МЕТОД:

    def _on_smart_collection_image_selected(self, info: ImageInfo):
        """Обработка выбора изображения из умной коллекции"""
        try:
            print(f"Открытие изображения из умной коллекции: {info.path}")
            self.request_editor_display.emit(info)
        except Exception as e:

    def handle_dropped_files(self, file_paths: list):
        """Обработка перетащенных файлов - ПОЛНАЯ РЕАЛИЗАЦИЯ"""
        print(f"Обработка {len(file_paths)} перетащенных файлов...")

        try:
            from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QButtonGroup, QRadioButton

            # Диалог выбора действия
            dialog = QDialog(self.view)
            dialog.setWindowTitle("Что сделать с файлами?")
            dialog.setMinimumWidth(350)

            layout = QVBoxLayout(dialog)

            info_label = QLabel(f"Перетащено файлов: {len(file_paths)}")
            info_label.setStyleSheet("font-weight: bold; margin-bottom: 10px;")
            layout.addWidget(info_label)

            # Группа кнопок выбора действия
            button_group = QButtonGroup(dialog)

            add_radio = QRadioButton("➕ Добавить к текущей коллекции")
            add_radio.setChecked(True)
            button_group.addButton(add_radio, 1)
            layout.addWidget(add_radio)

            replace_radio = QRadioButton("🔄 Заменить текущую коллекцию")
            button_group.addButton(replace_radio, 2)
            layout.addWidget(replace_radio)

            analyze_radio = QRadioButton("🔍 Анализировать только эти файлы")
            button_group.addButton(analyze_radio, 3)
            layout.addWidget(analyze_radio)

            # Кнопки OK/Cancel
            from PyQt6.QtWidgets import QDialogButtonBox
            button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
            button_box.accepted.connect(dialog.accept)
            button_box.rejected.connect(dialog.reject)
            layout.addWidget(button_box)

            if dialog.exec():
                action = button_group.checkedId()

                if action == 1:
                    # Добавить к текущей коллекции
                    self._add_files_to_collection(file_paths)
                elif action == 2:
                    # Заменить коллекцию
                    self._replace_collection_with_files(file_paths)
                elif action == 3:
                    # Анализировать только эти файлы
                    self._analyze_only_these_files(file_paths)
            else:
                self.view.statusBar().showMessage("Операция отменена")

        except Exception as e:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(self.view, "Ошибка", f"Не удалось обработать файлы:\n{e}")

    def _add_files_to_collection(self, file_paths: list):
        """Добавляет файлы к текущей коллекции"""
        from PyQt6.QtCore import QThread
        from core.analyzer import process_single_file
        from models.image_model import ImageInfo

        self.view.statusBar().showMessage(f"Обработка {len(file_paths)} файлов...")

        # Простая синхронная обработка (для малого количества файлов)
        if len(file_paths) <= 10:
            added_count = 0
            for file_path in file_paths:
                try:
                    result = process_single_file(file_path)
                    if result and result.get("thumbnail_path"):
                        info = ImageInfo(**result)
                        self.image_data.append(info)
                        self.view.add_thumbnails_batch([info])
                        added_count += 1
                except Exception as e:

            self.view.statusBar().showMessage(f"Добавлено: {added_count} из {len(file_paths)}")

            # Пересчитываем дубликаты
            if added_count > 0:
                self._run_advanced_duplicate_search("phash")
        else:
            # Для большого количества - используем полное сканирование
            self.view.statusBar().showMessage("Много файлов - запуск полного сканирования...")
            # Создаем временную папку или сканируем напрямую
            self._scan_file_list(file_paths)

    def _replace_collection_with_files(self, file_paths: list):
        """Заменяет текущую коллекцию новыми файлами"""
        from PyQt6.QtWidgets import QMessageBox

        reply = QMessageBox.question(
            self.view,
            "Подтверждение",
            "Вы уверены, что хотите заменить текущую коллекцию?\nВсе текущие изображения будут удалены из просмотра.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            # Очищаем текущую коллекцию
            self.image_data.clear()
            self.groups.clear()
            self.view.clear_thumbnails()

            # Сканируем новые файлы
            self._scan_file_list(file_paths)

    def _analyze_only_these_files(self, file_paths: list):
        """Анализирует только указанные файлы (новая сессия)"""
        # То же что и replace, но с другим сообщением
        self.image_data.clear()
        self.groups.clear()
        self.view.clear_thumbnails()
        self.view.statusBar().showMessage(f"Анализ {len(file_paths)} файлов...")
        self._scan_file_list(file_paths)

    def _scan_file_list(self, file_paths: list):
        """Сканирует конкретный список файлов"""
        # Используем существующий Scanner, но передаем список файлов
        # Для этого нужно модифицировать Scanner или создать временный метод

        # Простое решение: обрабатываем синхронно
        from core.analyzer import process_single_file
        from models.image_model import ImageInfo

        self.thumbnail_buffer.clear()
        self.add_thumbnail_timer.start()

        total = len(file_paths)
        for idx, file_path in enumerate(file_paths):
            try:
                result = process_single_file(file_path)
                if result and result.get("thumbnail_path"):
                    info = ImageInfo(**result)
                    self.image_data.append(info)
                    self.thumbnail_buffer.append(info)

                # Обновляем прогресс
                if (idx + 1) % 10 == 0:
                    self.view.statusBar().showMessage(f"Обработано: {idx + 1}/{total}")
            except Exception as e:

        self.add_thumbnail_timer.stop()
        self._process_thumbnail_buffer()

        # Запускаем поиск дубликатов
        self._show_duplicate_finder_dialog()

        self.view.statusBar().showMessage(f"Готово! Обработано: {len(self.image_data)} файлов")

    # ДОБАВЬТЕ ЭТИ МЕТОДЫ В КЛАСС MainController в photo_view_controller.py

    def handle_compare(self, image_infos: list):
        """Обработка запроса сравнения"""
        if len(image_infos) == 2:
            self.view.comparison_view.load_images(image_infos)
            print(f"Сравнение: {image_infos[0].path} vs {image_infos[1].path}")

    def _on_collection_changed(self, collection_name: str):
        """Обработка смены умной коллекции"""
        print(f"Выбрана коллекция: {collection_name}")
        # Обновляем данные в умных коллекциях


    def _on_image_processed(self, info: ImageInfo):
        """Обрабатывает сигнал о готовности изображения"""
        try:
            if info and info.thumbnail_path:
                self.image_data.append(info)
                self.thumbnail_buffer.append(info)
        except Exception as e:

    def _process_thumbnail_buffer(self):
        """Обрабатывает буфер миниатюр пакетами"""
        if not self.thumbnail_buffer:
            return

        try:
            batch = self.thumbnail_buffer[:100]
            self.thumbnail_buffer = self.thumbnail_buffer[100:]
            self.view.add_thumbnails_batch(batch)
        except Exception as e:

    def _on_scan_finished_logic(self):
        """Вызывается при завершении сканирования"""
        try:
            self.add_thumbnail_timer.stop()
            self._process_thumbnail_buffer()

            print(f"Контроллер вида: Анализ завершен. Найдено изображений: {len(self.image_data)}")

            # Показываем диалог выбора метода поиска дубликатов
            self._show_duplicate_finder_dialog()

            # Обновляем умные коллекции
            if hasattr(self.view, 'smart_collections'):
                self.view.smart_collections.set_images(self.image_data)

        except Exception as e:
            import traceback
            traceback.print_exc()

    def _show_duplicate_finder_dialog(self):
        """Показывает диалог выбора метода поиска дубликатов"""
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QButtonGroup, QRadioButton

        dialog = QDialog(self.view)
        dialog.setWindowTitle("Поиск дубликатов")
        dialog.setMinimumWidth(400)

        layout = QVBoxLayout(dialog)

        label = QLabel("Выберите метод поиска дубликатов:")
        label.setStyleSheet("font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(label)

        # Группа радио-кнопок
        button_group = QButtonGroup(dialog)

        methods_info = [
            ("phash", "⚡ Perceptual Hash (рекомендуется)", "Баланс скорости и точности"),
            ("average", "🚀 Average Hash (быстрый)", "Быстро, но менее точно"),
            ("dhash", "🎯 Difference Hash", "Устойчив к изменениям яркости"),
            ("whash", "🔬 Wavelet Hash (точный)", "Медленнее, но очень точный"),
            ("combined", "🎖️ Комбинированный (phash+dhash)", "Максимальная точность")
        ]

        selected_method = ["phash"]

        for method, name, desc in methods_info:
            container = QWidget()
            container_layout = QVBoxLayout(container)
            container_layout.setContentsMargins(10, 5, 10, 5)

            radio = QRadioButton(name)
            if method == "phash":
                radio.setChecked(True)

            button_group.addButton(radio)
            radio.toggled.connect(lambda checked, m=method: selected_method.__setitem__(0, m) if checked else None)

            desc_label = QLabel(desc)
            desc_label.setStyleSheet("color: #888; font-size: 11px; margin-left: 25px;")

            container_layout.addWidget(radio)
            container_layout.addWidget(desc_label)
            layout.addWidget(container)

        # Кнопки
        from PyQt6.QtWidgets import QDialogButtonBox
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)

        if dialog.exec():
            self._run_advanced_duplicate_search_with_progress(selected_method[0])
        else:
            print("Поиск дубликатов пропущен")
            self.view.update_thumbnail_styles()

    def _run_advanced_duplicate_search_with_progress(self, method: str):
        """Запускает продвинутый поиск дубликатов с прогресс-баром"""
        from PyQt6.QtCore import QThread, QObject, pyqtSignal

        # Создаем диалог прогресса
        progress_dialog = DuplicateSearchDialog(self.view)
        progress_dialog.set_method(method)
        progress_dialog.set_indeterminate(True)

        # Создаем worker для фонового поиска
        class DuplicateSearchWorker(QObject):
            progress = pyqtSignal(int, int)
            finished = pyqtSignal(dict, dict)  # groups, stats
            error = pyqtSignal(str)

            def __init__(self, finder, images, method, threshold):
                super().__init__()
                self.finder = finder
                self.images = images
                self.method = method
                self.threshold = threshold
                self.should_stop = False

            def run(self):
                try:
                    # Поиск дубликатов
                    if self.method == "combined":
                        groups = self.finder.find_duplicates_combined(
                            self.images,
                            methods=["phash", "dhash"],
                            threshold=self.threshold
                        )
                    else:
                        groups = self.finder.find_duplicates_single_method(
                            self.images,
                            method=self.method,
                            threshold=self.threshold
                        )

                    if self.should_stop:
                        return

                    # Применяем результаты
                    self.finder.apply_groups_to_images(groups, mark_best=True)

                    # Получаем статистику
                    stats = self.finder.get_statistics(groups)

                    self.finished.emit(groups, stats)

                except Exception as e:
                    self.error.emit(str(e))

            def stop(self):
                self.should_stop = True

        # Создаем поток и worker
        thread = QThread()
        worker = DuplicateSearchWorker(
            self.duplicate_finder,
            self.image_data,
            method,
            settings.get_hamming_threshold()
        )
        worker.moveToThread(thread)

        # Подключаем сигналы
        thread.started.connect(worker.run)

        def on_finished(groups, stats):
            progress_dialog.set_indeterminate(False)
            progress_dialog.set_groups_found(len(groups))
            progress_dialog.show_statistics(stats)
            progress_dialog.complete(f"Найдено групп: {len(groups)}")

            self.groups = groups
            self.view.update_thumbnail_styles()

            # Показываем сообщение
            msg = (f"Найдено групп дубликатов: {stats['total_groups']}\n"
                   f"Всего дубликатов: {stats['total_duplicates']}\n"
                   f"Потенциальная экономия: {stats['potential_savings_mb']:.2f} МБ")
            self.view.statusBar().showMessage(msg)

            thread.quit()

        def on_error(error_msg):
            progress_dialog.add_log(f"[ERROR] {error_msg}")
            progress_dialog.complete("Ошибка!")
            thread.quit()

            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(self.view, "Ошибка", f"Ошибка при поиске дубликатов:\n{error_msg}")

        def on_cancelled():
            worker.stop()
            thread.quit()
            progress_dialog.add_log("[INFO] Операция отменена пользователем")

        worker.finished.connect(on_finished)
        worker.error.connect(on_error)
        progress_dialog.cancelled.connect(on_cancelled)

        # Запускаем поток
        thread.start()
        progress_dialog.show()

    def apply_filter(self, filter_mode: str):
        """Применяет фильтр отображения"""
        try:
            total_visible = 0
            thumbnail_view = self.view.gallery_widget.thumbnail_view

            for i in range(thumbnail_view.count()):
                item = thumbnail_view.item(i)
                info = item.data(Qt.ItemDataRole.UserRole)

                is_visible = False
                if filter_mode == "all":
                    is_visible = True
                elif filter_mode == "best":
                    is_visible = info.is_best_in_group
                elif filter_mode == "duplicates":
                    is_visible = info.group_id is not None

                if is_visible:
                    total_visible += 1

                item.setHidden(not is_visible)

            self.view.status_bar.showMessage(f"Показано: {total_visible} из {len(self.image_data)}")

        except Exception as e:

    def _on_edit_requested(self, info: ImageInfo):
        """Обрабатывает запрос на редактирование"""
        try:
            print(f"Контроллер: Получен запрос на редактирование файла {info.path}")
            self.request_editor_display.emit(info)
        except Exception as e:

    def _on_thumbnail_selected(self, item):
        """Обрабатывает выбор миниатюры"""
        try:
            info = item.data(Qt.ItemDataRole.UserRole)

            if not isinstance(info, ImageInfo):
                return

            if self.is_in_style_mode:
                self.apply_style(source_info=info)
            else:
                self.view.show_preview(info.path)
                metadata = read_exif(info.path)
                self.view.update_metadata(metadata)

        except Exception as e:

    def handle_style_request(self):
        """Обрабатывает запрос на копирование стиля"""
        try:
            selected_items = self.view.gallery_widget.thumbnail_view.selectedItems()

            if len(selected_items) != 1:
                QMessageBox.warning(
                    self.view, "Ошибка",
                    "Пожалуйста, выберите одно фото, к которому нужно применить стиль."
                )
                return

            self.is_in_style_mode = True
            self.style_target_info = selected_items[0].data(Qt.ItemDataRole.UserRole)
            self.view.enter_style_copy_mode(True)
            self.view.status_bar.showMessage(
                "Режим 'Пипетка': выберите фото-источник для копирования стиля."
            )

        except Exception as e:
            self.is_in_style_mode = False
            self.style_target_info = None
            self.view.enter_style_copy_mode(False)

    def apply_style(self, source_info: ImageInfo):
        """Применяет стиль с одного изображения на другое"""
        print(f"Применяем стиль с '{source_info.path}' на '{self.style_target_info.path}'")

        try:
            with Image.open(source_info.path).convert("RGB") as source_img, \
                    Image.open(self.style_target_info.path).convert("RGB") as target_img:

                stylized_img = transfer_style(source_img, target_img)

            if stylized_img:
                q_image_after = QImage(
                    stylized_img.tobytes(),
                    stylized_img.width,
                    stylized_img.height,
                    stylized_img.width * 3,
                    QImage.Format.Format_RGB888
                )
                pixmap_after = QPixmap.fromImage(q_image_after)
                target_thumbnail = QPixmap(self.style_target_info.thumbnail_path)

                dialog = StylePreviewDialog(target_thumbnail, pixmap_after, self.view)

                if dialog.exec():
                    self.save_stylized_image(stylized_img)
            else:
                QMessageBox.warning(self.view, "Ошибка", "Не удалось применить стиль.")

        except Exception as e:
            QMessageBox.critical(self.view, "Ошибка", f"Не удалось применить стиль: {e}")
        finally:
            self.is_in_style_mode = False
            self.style_target_info = None
            self.view.enter_style_copy_mode(False)
            self.view.status_bar.showMessage("Готово")

    def save_stylized_image(self, pil_image: Image.Image):
        """Сохраняет стилизованное изображение"""
        try:
            original_path = self.style_target_info.path
            path_without_ext, _ = os.path.splitext(original_path)
            new_path = f"{path_without_ext}_stylized.jpg"

            pil_image.save(new_path, "JPEG", quality=95, optimize=True)

            QMessageBox.information(
                self.view, "Успех",
                f"Стилизованный файл сохранен как:\n{new_path}"
            )

        except Exception as e:
            QMessageBox.critical(self.view, "Ошибка", f"Не удалось сохранить файл: {e}")

    def handle_keep_best(self, best_info: ImageInfo):
        """Оставляет лучшее фото из группы, удаляя остальные"""
        try:
            if not best_info.group_id:
                QMessageBox.information(
                    self.view, "Информация",
                    "Это уникальное фото, в группе нет других файлов."
                )
                return

            infos_to_delete = [
                info for info in self.groups.get(best_info.group_id, [])
                if info.path != best_info.path
            ]

            if not infos_to_delete:
                return

            self.handle_delete(infos_to_delete)

        except Exception as e:
            QMessageBox.critical(self.view, "Ошибка", f"Произошла ошибка: {e}")

    def handle_delete(self, infos_to_delete: list[ImageInfo]):
        """Удаляет выбранные файлы"""
        try:
            count = len(infos_to_delete)
            reply = QMessageBox.question(
                self.view, "Подтверждение удаления",
                f"Вы уверены, что хотите удалить {count} файл(ов)?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )

            if reply == QMessageBox.StandardButton.Yes:
                failed_files = []

                for info in infos_to_delete:
                    try:
                        os.remove(info.path)
                    except Exception as e:
                        failed_files.append(info.path)

                # Обновляем интерфейс
                self.view.remove_thumbnails(infos_to_delete)
                self.image_data = [info for info in self.image_data if info not in infos_to_delete]

                # Пересчитываем группы
                self._run_advanced_duplicate_search("phash")

                if failed_files:
                    QMessageBox.warning(
                        self.view, "Предупреждение",
                        f"Не удалось удалить {len(failed_files)} файл(ов)."
                    )

        except Exception as e:
            QMessageBox.critical(self.view, "Ошибка", f"Произошла ошибка: {e}")

    def handle_copy(self, infos_to_copy: list[ImageInfo]):
        """Копирует выбранные файлы"""
        try:
            dest_dir = QFileDialog.getExistingDirectory(
                self.view, "Выберите папку для копирования"
            )

            if dest_dir:
                failed_files = []

                for info in infos_to_copy:
                    try:
                        shutil.copy(info.path, dest_dir)
                    except Exception as e:
                        failed_files.append(info.path)

                if failed_files:
                    QMessageBox.warning(
                        self.view, "Предупреждение",
                        f"Не удалось скопировать {len(failed_files)} файл(ов)."
                    )
                else:
                    QMessageBox.information(
                        self.view, "Готово",
                        f"{len(infos_to_copy)} файл(ов) скопировано."
                    )

        except Exception as e:
            QMessageBox.critical(self.view, "Ошибка", f"Произошла ошибка: {e}")

    def handle_move(self, infos_to_move: list[ImageInfo]):
        """Перемещает выбранные файлы"""
        try:
            dest_dir = QFileDialog.getExistingDirectory(
                self.view, "Выберите папку для перемещения"
            )

            if dest_dir:
                failed_files = []

                for info in infos_to_move:
                    try:
                        shutil.move(info.path, dest_dir)
                    except Exception as e:
                        failed_files.append(info.path)

                # Обновляем интерфейс
                self.view.remove_thumbnails(infos_to_move)
                self.image_data = [info for info in self.image_data if info not in infos_to_move]
                self._run_advanced_duplicate_search("phash")

                if failed_files:
                    QMessageBox.warning(
                        self.view, "Предупреждение",
                        f"Не удалось переместить {len(failed_files)} файл(ов)."
                    )
                else:
                    QMessageBox.information(
                        self.view, "Готово",
                        f"{len(infos_to_move)} файл(ов) перемещено."
                    )

        except Exception as e:
            QMessageBox.critical(self.view, "Ошибка", f"Произошла ошибка: {e}")

    def cleanup(self):
        """Корректное завершение работы контроллера"""
        print("Контроллер: Остановка сканера и выход из потока...")

        try:
            if self.scanner:
                self.scanner.stop()

            # Даем время на завершение текущих операций
            self.scanner_thread.quit()

            if not self.scanner_thread.wait(5000):  # Таймаут 5 секунд
                print("Контроллер: Принудительное завершение потока сканера...")
                self.scanner_thread.terminate()
                self.scanner_thread.wait()

            print("Контроллер: Поток сканера завершен.")

        except Exception as e: