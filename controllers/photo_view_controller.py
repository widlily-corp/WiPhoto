# controllers/photo_view_controller.py

import os
import shutil
import logging
from collections import defaultdict

from PIL import Image
from PyQt6.QtCore import QThread, QObject, pyqtSignal, QTimer, Qt
from PyQt6.QtGui import QPixmap, QImage
from PyQt6.QtWidgets import (
    QMessageBox, QFileDialog, QDialog, QVBoxLayout, QLabel, 
    QPushButton, QWidget, QProgressDialog, QApplication, 
    QRadioButton, QButtonGroup, QDialogButtonBox
)
from views.progress_dialog import DuplicateSearchDialog, ScanProgressDialog
from core.analyzer import transfer_style, _load_image_optimized, RAW_FORMATS
from core.file_scanner import Scanner
from core.metadata_reader import read_exif
from core.advanced_duplicate_finder import AdvancedDuplicateFinder
from models.image_model import ImageInfo
from views.style_preview_dialog import StylePreviewDialog
from core.settings_manager import settings
from core.ai_worker import AIProcessingManager

class MainController(QObject):
    start_scanning_signal = pyqtSignal(str, bool)
    request_editor_display = pyqtSignal(ImageInfo)
    ai_analysis_started = pyqtSignal()
    ai_analysis_finished = pyqtSignal()

    def __init__(self, main_window):
        super().__init__()
        self.view = main_window
        self.image_data =[]
        self.groups = defaultdict(list)
        self.is_in_style_mode = False
        self.style_target_info = None
        self._current_collection_id = None

        self.duplicate_finder = AdvancedDuplicateFinder()
        self._ai_manager = AIProcessingManager()

        self.scanner_thread = QThread()
        self.scanner = Scanner()
        self.scanner.moveToThread(self.scanner_thread)

        self.scanner.image_processed.connect(self._on_image_processed)
        self.scanner.finished.connect(self._on_scan_finished_logic)
        self.start_scanning_signal.connect(self.scanner.start_scanning)

        self._connect_view_signals()

        self.thumbnail_buffer =[]
        self.add_thumbnail_timer = QTimer()
        self.add_thumbnail_timer.setInterval(50)
        self.add_thumbnail_timer.timeout.connect(self._process_thumbnail_buffer)

        self.scanner_thread.start()
        logging.info("Контроллер вида: готов к работе, поток сканера запущен.")

    def start_scan(self, folder_path, is_recursive):
        self.image_data.clear()
        self.groups.clear()
        self.view.clear_thumbnails()
        self.thumbnail_buffer.clear()
        self.add_thumbnail_timer.start()

        if hasattr(self.view, 'folder_tree'):
            self.view.folder_tree.set_root(folder_path)
        self._scan_root_folder = folder_path

        self.start_scanning_signal.emit(folder_path, is_recursive)

    def _connect_view_signals(self):
        gallery = self.view.gallery_widget
        main_win = self.view

        gallery.thumbnail_view.itemClicked.connect(self._on_thumbnail_selected)
        gallery.thumbnail_view.itemDoubleClicked.connect(self._on_thumbnail_double_clicked)
        gallery.edit_requested.connect(self._on_edit_requested)

        main_win.delete_requested.connect(self.handle_delete)
        main_win.copy_requested.connect(self.handle_copy)
        main_win.move_requested.connect(self.handle_move)
        main_win.keep_best_requested.connect(self.handle_keep_best)
        main_win.style_copy_requested.connect(self.handle_style_request)
        main_win.filter_changed.connect(self.apply_filter)
        main_win.thumbnail_size_changed.connect(self.view.set_thumbnail_size)
        main_win.files_dropped.connect(self.handle_dropped_files)
        main_win.compare_requested.connect(self.handle_compare)

        if hasattr(main_win, 'export_requested'):
            main_win.export_requested.connect(self.handle_export)
        if hasattr(main_win, 'refresh_requested'):
            main_win.refresh_requested.connect(self._handle_refresh)
        if hasattr(main_win, 'batch_rename_requested'):
            main_win.batch_rename_requested.connect(self._handle_batch_rename)
        if hasattr(main_win, 'delete_rejected_requested'):
            main_win.delete_rejected_requested.connect(self._handle_delete_rejected)

        if hasattr(gallery, 'find_similar_requested'):
            gallery.find_similar_requested.connect(self._handle_find_similar)

        self.request_editor_display.connect(main_win.switch_to_editor)

        if hasattr(main_win, 'editor_widget'):
            main_win.editor_widget.back_to_gallery.connect(main_win.switch_to_gallery)

        if hasattr(main_win, 'smart_collections'):
            main_win.smart_collections.collection_selected.connect(self._on_collection_filter_applied)
            main_win.smart_collections.collection_changed.connect(self._on_collection_changed)
            main_win.smart_collections.delete_all_from_trash_requested.connect(self._on_delete_all_from_trash)
            main_win.smart_collections.restore_all_from_trash_requested.connect(self._on_restore_all_from_trash)

        if hasattr(main_win, 'sort_changed'):
            main_win.sort_changed.connect(self._apply_sort)
        if hasattr(main_win, 'search_changed'):
            main_win.search_changed.connect(self._apply_search)

        if hasattr(main_win, 'folder_filter_requested'):
            main_win.folder_filter_requested.connect(self._on_folder_filter)

        if hasattr(gallery, 'thumbnail_view'):
            gallery.thumbnail_view.rating_changed.connect(self._on_rating_changed)
            gallery.thumbnail_view.color_label_changed.connect(self._on_color_label_changed)
            gallery.thumbnail_view.video_play_requested.connect(self._on_video_play_requested)
            gallery.thumbnail_view.preview_requested.connect(self._on_preview_requested)
            gallery.thumbnail_view.restore_from_trash_requested.connect(self._on_restore_from_trash)
            gallery.thumbnail_view.delete_forever_requested.connect(self._on_delete_forever)

        if hasattr(main_win, 'map_widget'):
            main_win.map_widget.image_selected.connect(self._on_map_image_selected)

        if hasattr(main_win, 'timeline_widget'):
            main_win.timeline_widget.image_selected.connect(self._on_map_image_selected)

    def _update_collections(self):
        """Обновляет умные коллекции и прочие виджеты при изменении данных"""
        if hasattr(self.view, 'smart_collections'):
            self.view.smart_collections.set_images(self.image_data)
            if self._current_collection_id:
                filtered = self.view.smart_collections._filter_by_collection(self._current_collection_id)
                self.view.gallery_widget.set_all_items(filtered)
        if hasattr(self.view, 'map_widget'):
            self.view.map_widget.set_images(self.image_data)
        if hasattr(self.view, 'timeline_widget'):
            self.view.timeline_widget.set_images(self.image_data)
        if hasattr(self.view, 'update_thumbnail_styles'):
            self.view.update_thumbnail_styles()

    def _on_map_image_selected(self, info: ImageInfo):
        try:
            self.view.show_preview(info.path)
            self.view.update_ai_info(info)
        except Exception as e:
            logging.error(f"Ошибка: {e}")

    def _on_folder_filter(self, folder_path: str):
        try:
            root = getattr(self, '_scan_root_folder', '')
            norm_folder = os.path.normpath(folder_path)
            norm_root = os.path.normpath(root)

            if norm_folder == norm_root:
                filtered = self.image_data
            else:
                filtered =[img for img in self.image_data
                            if os.path.normpath(img.path).startswith(norm_folder + os.sep)
                            or os.path.normpath(os.path.dirname(img.path)) == norm_folder]

            self.view.gallery_widget.set_all_items(filtered)
            self.view.statusBar().showMessage(f"Папка: {os.path.basename(folder_path)} — {len(filtered)} файлов")
            self.view.switch_to_gallery()
        except Exception as e:
            logging.error(f"Ошибка фильтрации по папке: {e}")

    def _on_collection_filter_applied(self, filtered_images: list):
        try:
            self.view.gallery_widget.set_all_items(filtered_images)
            self.view.statusBar().showMessage(f"Показано: {len(filtered_images)} из {len(self.image_data)}")
            self.view.switch_to_gallery()
        except Exception as e:
            logging.error(f"Ошибка фильтрации коллекции: {e}")

    def _on_thumbnail_double_clicked(self, item):
        try:
            info = item.data(Qt.ItemDataRole.UserRole)
            if isinstance(info, ImageInfo):
                self._open_fullscreen_viewer(info)
        except Exception as e:
            logging.error(f"Ошибка: {e}")

    def _open_fullscreen_viewer(self, info: ImageInfo):
        try:
            from views.fullscreen_viewer import FullscreenViewer
            view = self.view.gallery_widget.thumbnail_view
            images =[]
            start_idx = 0
            for i in range(view.count()):
                item = view.item(i)
                img = item.data(Qt.ItemDataRole.UserRole)
                if isinstance(img, ImageInfo):
                    if img.path == info.path:
                        start_idx = len(images)
                    images.append(img)

            self._fullscreen_viewer = FullscreenViewer(images, start_idx)
            self._fullscreen_viewer.showFullScreen()
        except Exception as e:
            logging.error(f"Ошибка полноэкранного просмотра: {e}")

    def handle_dropped_files(self, file_paths: list):
        logging.info(f"Обработка {len(file_paths)} перетащенных файлов...")
        try:
            dialog = QDialog(self.view)
            dialog.setWindowTitle("Что сделать с файлами?")
            dialog.setMinimumWidth(350)
            layout = QVBoxLayout(dialog)

            info_label = QLabel(f"Перетащено файлов: {len(file_paths)}")
            info_label.setStyleSheet("font-weight: bold; margin-bottom: 10px;")
            layout.addWidget(info_label)

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

            button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
            button_box.accepted.connect(dialog.accept)
            button_box.rejected.connect(dialog.reject)
            layout.addWidget(button_box)

            if dialog.exec():
                action = button_group.checkedId()
                if action == 1:
                    self._add_files_to_collection(file_paths)
                elif action == 2:
                    self._replace_collection_with_files(file_paths)
                elif action == 3:
                    self._analyze_only_these_files(file_paths)
            else:
                self.view.statusBar().showMessage("Операция отменена")
        except Exception as e:
            QMessageBox.critical(self.view, "Ошибка", f"Не удалось обработать файлы:\n{e}")

    def _add_files_to_collection(self, file_paths: list):
        from core.analyzer import process_single_file
        self.view.statusBar().showMessage(f"Обработка {len(file_paths)} файлов...")

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
                    logging.error(f"Ошибка добавления файла: {e}")
            self._update_collections()
            self.view.statusBar().showMessage(f"Добавлено: {added_count} из {len(file_paths)}")
        else:
            self.view.statusBar().showMessage("Много файлов - запуск сканирования...")
            self._scan_file_list(file_paths)

    def _replace_collection_with_files(self, file_paths: list):
        reply = QMessageBox.question(
            self.view, "Подтверждение",
            "Вы уверены, что хотите заменить текущую коллекцию?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.image_data.clear()
            self.groups.clear()
            self.view.clear_thumbnails()
            self._scan_file_list(file_paths)

    def _analyze_only_these_files(self, file_paths: list):
        self.image_data.clear()
        self.groups.clear()
        self.view.clear_thumbnails()
        self.view.statusBar().showMessage(f"Анализ {len(file_paths)} файлов...")
        self._scan_file_list(file_paths)

    def _scan_file_list(self, file_paths: list):
        from concurrent.futures import ProcessPoolExecutor, as_completed
        from core.analyzer import process_single_file

        self.thumbnail_buffer.clear()
        self.add_thumbnail_timer.start()
        total = len(file_paths)
        self.view.statusBar().showMessage(f"Обработка {total} файлов...")

        class FileListWorker(QObject):
            image_processed = pyqtSignal(object)
            progress = pyqtSignal(int, int)
            finished = pyqtSignal()

            def __init__(self, paths, worker_count):
                super().__init__()
                self._paths = paths
                self._worker_count = worker_count

            def run(self):
                try:
                    with ProcessPoolExecutor(max_workers=self._worker_count) as executor:
                        futures = {executor.submit(process_single_file, p): p for p in self._paths}
                        done = 0
                        for future in as_completed(futures):
                            try:
                                result = future.result(timeout=60)
                                if result and result.get("thumbnail_path"):
                                    self.image_processed.emit(result)
                            except Exception as e:
                                logging.error(f"Ошибка обработки файла: {e}")
                            done += 1
                            if done % 5 == 0:
                                self.progress.emit(done, len(self._paths))
                except Exception as e:
                    logging.error(f"Ошибка сканирования: {e}")
                finally:
                    self.finished.emit()

        self._file_list_thread = QThread()
        self._file_list_worker = FileListWorker(file_paths, settings.get_worker_count())
        self._file_list_worker.moveToThread(self._file_list_thread)

        def on_result(result_data):
            info = ImageInfo(**result_data)
            self.image_data.append(info)
            self.thumbnail_buffer.append(info)

        def on_progress(done, total):
            self.view.statusBar().showMessage(f"Обработано: {done}/{total}")

        def on_finished():
            self.add_thumbnail_timer.stop()
            self._process_thumbnail_buffer()
            self._show_duplicate_finder_dialog()
            self._update_collections()
            self.view.statusBar().showMessage(f"Готово! Обработано: {len(self.image_data)} файлов")
            self._file_list_thread.quit()

        self._file_list_worker.image_processed.connect(on_result)
        self._file_list_worker.progress.connect(on_progress)
        self._file_list_worker.finished.connect(on_finished)
        self._file_list_thread.started.connect(self._file_list_worker.run)
        self._file_list_thread.start()

    def handle_compare(self, image_infos: list):
        if len(image_infos) == 2:
            self.view.comparison_view.load_images(image_infos)
            logging.info(f"Сравнение: {image_infos[0].path} vs {image_infos[1].path}")

    def _on_collection_changed(self, collection_id: str):
        self._current_collection_id = collection_id
        logging.info(f"Коллекция: {collection_id}")

    def _on_image_processed(self, info: ImageInfo):
        try:
            if info and info.thumbnail_path:
                self.image_data.append(info)
                self.thumbnail_buffer.append(info)
        except Exception as e:
            logging.error(f"Ошибка: {e}")

    def _process_thumbnail_buffer(self):
        if not self.thumbnail_buffer:
            return
        try:
            batch = self.thumbnail_buffer[:100]
            self.thumbnail_buffer = self.thumbnail_buffer[100:]
            self.view.add_thumbnails_batch(batch)
        except Exception as e:
            logging.error(f"Ошибка: {e}")

    def _on_scan_finished_logic(self):
        try:
            self.add_thumbnail_timer.stop()
            self._process_thumbnail_buffer()
            logging.info(f"Контроллер вида: Анализ завершен. Найдено изображений: {len(self.image_data)}")

            self._show_duplicate_finder_dialog()
            self._update_collections()
            self._start_ai_processing()

        except Exception as e:
            import traceback
            traceback.print_exc()

    def _start_ai_processing(self):
        if not self.image_data:
            return
        paths = [info.path for info in self.image_data]
        self.ai_analysis_started.emit()  # Signal UI to show blocking overlay
        self._ai_manager.start(
            image_paths=paths,
            on_result=self._on_ai_result,
            on_progress=self._on_ai_progress,
            on_finished=self._on_ai_finished,
            batch_size=8,  # Process 8 images in parallel for better speed
        )
        self.view.statusBar().showMessage(f"Анализ ИИ: запущен для {len(paths)} фото...")

    def _on_ai_result(self, result: dict):
        path = result.get("path")
        if not path: return
        for info in self.image_data:
            if info.path == path:
                info.faces_count   = result.get("faces_count", 0)
                info.animals_count = result.get("animals_count", 0)
                info.animal_species = result.get("animal_species", [])
                info.tags          = result.get("tags",[])
                break
        try:
            self.view.update_thumbnail_badge(path, result)
        except Exception:
            pass

    def _on_ai_progress(self, done: int, total: int):
        self.view.statusBar().showMessage(f"ИИ анализ: {done}/{total} фото обработано...")

    def _on_ai_finished(self):
        logging.info("AIProcessingManager: анализ завершён")
        self.view.statusBar().showMessage(f"ИИ анализ завершён. Обработано: {len(self.image_data)} фото.")
        self.ai_analysis_finished.emit()  # Signal UI to hide blocking overlay
        self._update_collections()

    def _show_duplicate_finder_dialog(self):
        dialog = QDialog(self.view)
        dialog.setWindowTitle("Поиск дубликатов")
        dialog.setMinimumWidth(400)
        layout = QVBoxLayout(dialog)

        label = QLabel("Выберите метод поиска дубликатов:")
        label.setStyleSheet("font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(label)

        button_group = QButtonGroup(dialog)

        methods_info =[
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
            if method == "phash": radio.setChecked(True)
            button_group.addButton(radio)
            radio.toggled.connect(lambda checked, m=method: selected_method.__setitem__(0, m) if checked else None)

            desc_label = QLabel(desc)
            desc_label.setStyleSheet("color: #888; font-size: 11px; margin-left: 25px;")

            container_layout.addWidget(radio)
            container_layout.addWidget(desc_label)
            layout.addWidget(container)

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)

        if dialog.exec():
            self._run_advanced_duplicate_search_with_progress(selected_method[0])
        else:
            logging.info("Поиск дубликатов пропущен")
            self.view.update_thumbnail_styles()

    def _run_advanced_duplicate_search_with_progress(self, method: str):
        progress_dialog = DuplicateSearchDialog(self.view)
        progress_dialog.set_method(method)
        progress_dialog.set_status(f"Анализ {len(self.image_data)} изображений методом: {method}")
        progress_dialog.set_indeterminate(True)
        progress_dialog.setMinimumSize(500, 250)

        class DuplicateSearchWorker(QObject):
            progress = pyqtSignal(int, int)
            finished = pyqtSignal(dict, dict)
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
                    if self.method == "combined":
                        groups = self.finder.find_duplicates_combined(
                            self.images, methods=["phash", "dhash"], threshold=self.threshold)
                    else:
                        groups = self.finder.find_duplicates_single_method(
                            self.images, method=self.method, threshold=self.threshold,
                            progress_callback=self.progress.emit)

                    if self.should_stop: return
                    stats = self.finder.get_statistics(groups)
                    self.finished.emit(groups, stats)
                except Exception as e:
                    self.error.emit(str(e))

            def stop(self):
                self.should_stop = True

        self._dup_thread = QThread()
        self._dup_worker = DuplicateSearchWorker(
            self.duplicate_finder, self.image_data, method, settings.get_hamming_threshold()
        )
        self._dup_worker.moveToThread(self._dup_thread)
        self._dup_thread.started.connect(self._dup_worker.run)
        
        thread = self._dup_thread
        worker = self._dup_worker

        def on_finished(groups, stats):
            progress_dialog.set_indeterminate(False)
            progress_dialog.set_groups_found(len(groups))
            progress_dialog.show_statistics(stats)
            progress_dialog.complete(f"Найдено групп: {len(groups)}")

            self.duplicate_finder.apply_groups_to_images(groups, mark_best=True)
            self.groups = groups
            self._update_collections()

            msg = (f"Найдено групп дубликатов: {stats['total_groups']}\n"
                   f"Всего дубликатов: {stats['total_duplicates']}\n"
                   f"Потенциальная экономия: {stats['potential_savings_mb']:.2f} МБ")
            self.view.statusBar().showMessage(msg)

            thread.quit()
            thread.wait()
            thread.deleteLater()
            worker.deleteLater()

        def on_error(error_msg):
            progress_dialog.add_log(f"[ERROR] {error_msg}")
            progress_dialog.complete("Ошибка!")
            QMessageBox.critical(self.view, "Ошибка", f"Ошибка при поиске дубликатов:\n{error_msg}")
            thread.quit()
            thread.wait()
            thread.deleteLater()
            worker.deleteLater()

        def on_cancelled():
            worker.stop()
            thread.quit()
            thread.wait()
            thread.deleteLater()
            worker.deleteLater()
            progress_dialog.add_log("[INFO] Операция отменена пользователем")

        worker.finished.connect(on_finished)
        worker.error.connect(on_error)
        worker.progress.connect(progress_dialog.update_progress)
        progress_dialog.cancelled.connect(on_cancelled)

        progress_dialog.show()
        QApplication.processEvents()
        thread.start()

    def _on_rating_changed(self, info: ImageInfo, rating: int):
        info.rating = rating
        logging.info(f"Rating set: {os.path.basename(info.path)} → {rating}")
        self._save_sidecar(info)
        self._update_collections()

    def _on_color_label_changed(self, info: ImageInfo, color: str):
        info.color_label = color
        logging.info(f"Color label: {os.path.basename(info.path)} → {color or 'none'}")
        self._save_sidecar(info)
        self._update_collections()

    def _on_video_play_requested(self, path: str):
        """Запуск видео плеера"""
        try:
            from views.video_player_widget import VideoPlayerWidget
            player = VideoPlayerWidget(path)
            player.show()
        except Exception as e:
            logging.error(f"Ошибка запуска видео плеера: {e}")
            QMessageBox.warning(self.view, "Ошибка", f"Не удалось открыть видео: {e}")

    def _on_preview_requested(self, path: str):
        """Открытие preview фото"""
        try:
            self.view.show_preview(path)
        except Exception as e:
            logging.error(f"Ошибка открытия preview: {e}")

    def _on_restore_from_trash(self, infos: list[ImageInfo]):
        """Восстановление файлов из корзины"""
        try:
            restored = []
            for info in infos:
                # Для простоты восстанавливаем в текущую рабочую директорию
                # В будущем можно хранить оригинальный путь в метаданных
                basename = os.path.basename(info.path)
                current_dir = os.getcwd()
                dest_path = os.path.join(current_dir, basename)
                
                # Если файл уже существует, добавляем индекс
                counter = 1
                name, ext = os.path.splitext(basename)
                while os.path.exists(dest_path):
                    dest_path = os.path.join(current_dir, f"{name}_{counter}{ext}")
                    counter += 1
                
                try:
                    shutil.move(info.path, dest_path)
                    # Создаем новый ImageInfo для восстановленного файла
                    new_info = ImageInfo(path=dest_path, thumbnail_path=dest_path)
                    restored.append(new_info)
                    logging.info(f"Восстановлен из корзины: {basename} → {dest_path}")
                except Exception as e:
                    logging.error(f"Ошибка восстановления {info.path}: {e}")
            
            if restored:
                self.image_data.extend(restored)
                self._update_collections()
                QMessageBox.information(self.view, "Восстановление", 
                                      f"Восстановлено {len(restored)} файл(ов)")
        except Exception as e:
            logging.error(f"Ошибка восстановления из корзины: {e}")
            QMessageBox.warning(self.view, "Ошибка", f"Не удалось восстановить файлы: {e}")

    def _on_delete_forever(self, infos: list[ImageInfo]):
        """Полное удаление файлов из корзины"""
        try:
            count = len(infos)
            reply = QMessageBox.question(
                self.view, "Подтверждение удаления",
                f"Удалить навсегда {count} файл(ов)? Это действие нельзя отменить.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                deleted = []
                for info in infos:
                    try:
                        os.remove(info.path)
                        deleted.append(info)
                        logging.info(f"Удален навсегда: {info.path}")
                    except Exception as e:
                        logging.error(f"Ошибка удаления {info.path}: {e}")
                
                if deleted:
                    self.view.remove_thumbnails(deleted)
                    deleted_set = set(id(i) for i in deleted)
                    self.image_data = [info for info in self.image_data if id(info) not in deleted_set]
                    self._update_collections()
                    QMessageBox.information(self.view, "Удаление", 
                                          f"Удалено {len(deleted)} файл(ов)")
        except Exception as e:
            logging.error(f"Ошибка полного удаления: {e}")
            QMessageBox.warning(self.view, "Ошибка", f"Не удалось удалить файлы: {e}")

    def _on_delete_all_from_trash(self):
        """Удалить все файлы из корзины"""
        try:
            trash_items = self.view.smart_collections._filter_by_collection("trash")
            if not trash_items:
                QMessageBox.information(self.view, "Корзина пуста", "В корзине нет файлов для удаления.")
                return
            
            count = len(trash_items)
            reply = QMessageBox.question(
                self.view, "Подтверждение удаления",
                f"Удалить навсегда все {count} файл(ов) из корзины? Это действие нельзя отменить.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                deleted = []
                for info in trash_items:
                    try:
                        os.remove(info.path)
                        deleted.append(info)
                        logging.info(f"Удален навсегда из корзины: {info.path}")
                    except Exception as e:
                        logging.error(f"Ошибка удаления {info.path}: {e}")
                
                if deleted:
                    self.view.remove_thumbnails(deleted)
                    deleted_set = set(id(i) for i in deleted)
                    self.image_data = [info for info in self.image_data if id(info) not in deleted_set]
                    self._update_collections()
                    QMessageBox.information(self.view, "Удаление", 
                                          f"Удалено {len(deleted)} файл(ов) из корзины")
        except Exception as e:
            logging.error(f"Ошибка удаления всех из корзины: {e}")
            QMessageBox.warning(self.view, "Ошибка", f"Не удалось очистить корзину: {e}")

    def _on_restore_all_from_trash(self):
        """Восстановить все файлы из корзины"""
        try:
            trash_items = self.view.smart_collections._filter_by_collection("trash")
            if not trash_items:
                QMessageBox.information(self.view, "Корзина пуста", "В корзине нет файлов для восстановления.")
                return
            
            restored = []
            current_dir = os.getcwd()
            
            for info in trash_items:
                basename = os.path.basename(info.path)
                dest_path = os.path.join(current_dir, basename)
                
                # Если файл уже существует, добавляем индекс
                counter = 1
                name, ext = os.path.splitext(basename)
                while os.path.exists(dest_path):
                    dest_path = os.path.join(current_dir, f"{name}_{counter}{ext}")
                    counter += 1
                
                try:
                    shutil.move(info.path, dest_path)
                    new_info = ImageInfo(path=dest_path, thumbnail_path=dest_path)
                    restored.append(new_info)
                    logging.info(f"Восстановлен из корзины: {basename} → {dest_path}")
                except Exception as e:
                    logging.error(f"Ошибка восстановления {info.path}: {e}")
            
            if restored:
                self.image_data.extend(restored)
                self._update_collections()
                QMessageBox.information(self.view, "Восстановление", 
                                      f"Восстановлено {len(restored)} файл(ов) из корзины")
        except Exception as e:
            logging.error(f"Ошибка восстановления всех из корзины: {e}")
            QMessageBox.warning(self.view, "Ошибка", f"Не удалось восстановить файлы: {e}")

    def _save_sidecar(self, info: ImageInfo):
        try:
            base, _ = os.path.splitext(info.path)
            xmp_path = base + ".xmp"
            lines =[
                '<?xml version="1.0" encoding="UTF-8"?>',
                '<x:xmpmeta xmlns:x="adobe:ns:meta/">',
                '<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">',
                '<rdf:Description',
                ' xmlns:xmp="http://ns.adobe.com/xap/1.0/"',
                ' xmlns:xmpRights="http://ns.adobe.com/xap/1.0/rights/">',
                f' <xmp:Rating>{info.rating}</xmp:Rating>',
                f' <xmp:Label>{info.color_label}</xmp:Label>',
            ]
            if info.flag_status:
                lines.append(f' <xmp:Flag>{info.flag_status}</xmp:Flag>')
            lines +=[
                '</rdf:Description>',
                '</rdf:RDF>',
                '</x:xmpmeta>',
            ]
            with open(xmp_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(lines))
        except Exception as e:
            logging.error(f"XMP sidecar write error: {e}")

    def _apply_sort(self, sort_key: str):
        try:
            view = self.view.gallery_widget.thumbnail_view
            items_data =[]
            for i in range(view.count()):
                item = view.item(i)
                info = item.data(Qt.ItemDataRole.UserRole)
                items_data.append(info)

            if sort_key == "name":
                items_data.sort(key=lambda x: os.path.basename(x.path).lower())
            elif sort_key == "date":
                items_data.sort(key=lambda x: x.date_taken or "", reverse=True)
            elif sort_key == "size":
                items_data.sort(key=lambda x: x.file_size, reverse=True)
            elif sort_key == "camera":
                items_data.sort(key=lambda x: x.camera_model or "")
            elif sort_key == "rating":
                items_data.sort(key=lambda x: x.rating, reverse=True)

            self.view.clear_thumbnails()
            self.view.add_thumbnails_batch(items_data)
            self.view.statusBar().showMessage(f"Отсортировано: {sort_key}")
        except Exception as e:
            logging.error(f"Sort error: {e}")

    def _apply_search(self, text: str):
        try:
            text = text.lower().strip()
            view = self.view.gallery_widget.thumbnail_view
            visible = 0
            for i in range(view.count()):
                item = view.item(i)
                info = item.data(Qt.ItemDataRole.UserRole)
                if isinstance(info, ImageInfo):
                    match = not text or text in os.path.basename(info.path).lower()
                    item.setHidden(not match)
                    if match:
                        visible += 1
            self.view.statusBar().showMessage(f"Показано: {visible} из {view.count()}")
        except Exception as e:
            logging.error(f"Search error: {e}")

    def apply_filter(self, filter_mode: str):
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
                elif filter_mode == "picked":
                    is_visible = info.flag_status == "picked"
                elif filter_mode == "rejected":
                    is_visible = info.flag_status == "rejected"

                if is_visible:
                    total_visible += 1

                item.setHidden(not is_visible)

            self.view.status_bar.showMessage(f"Показано: {total_visible} из {len(self.image_data)}")

        except Exception as e:
            logging.error(f"Ошибка: {e}")

    def _on_edit_requested(self, info: ImageInfo):
        try:
            logging.info(f"Контроллер: Получен запрос на редактирование файла {info.path}")
            if info.is_video():
                from views.video_player_widget import VideoPlayerWidget
                logging.info(f"Открытие видео: {info.path}")
                self.video_player = VideoPlayerWidget(info.path)
                self.video_player.setWindowTitle(f"Видео - {os.path.basename(info.path)}")
                self.video_player.resize(1280, 720)
                self.video_player.show()
            else:
                self.request_editor_display.emit(info)
        except Exception as e:
            logging.error(f"Ошибка открытия файла: {e}")

    def _on_thumbnail_selected(self, item):
        try:
            info = item.data(Qt.ItemDataRole.UserRole)
            if not isinstance(info, ImageInfo):
                return

            if self.is_in_style_mode:
                self.apply_style(source_info=info)
            else:
                self.view.show_preview(info.path)
                metadata = read_exif(info.path)

                from core.geotag_manager import get_geolocation
                geolocation = get_geolocation(info.path)
                if geolocation:
                    metadata['GPS'] = f"{geolocation.latitude:.6f}, {geolocation.longitude:.6f}"
                    if geolocation.altitude:
                        metadata['Высота'] = f"{geolocation.altitude:.2f} м"

                self.view.update_metadata(metadata)
                self.view.update_ai_info(info)
        except Exception as e:
            logging.error(f"Ошибка: {e}")

    def handle_style_request(self):
        try:
            selected_items = self.view.gallery_widget.thumbnail_view.selectedItems()
            if len(selected_items) != 1:
                QMessageBox.warning(self.view, "Ошибка", "Пожалуйста, выберите одно фото, к которому нужно применить стиль.")
                return

            self.is_in_style_mode = True
            self.style_target_info = selected_items[0].data(Qt.ItemDataRole.UserRole)
            self.view.enter_style_copy_mode(True)
            self.view.status_bar.showMessage("Режим 'Пипетка': выберите фото-источник для копирования стиля.")

        except Exception as e:
            logging.error(f"Ошибка при запросе копирования стиля: {e}")
            self.is_in_style_mode = False
            self.style_target_info = None
            self.view.enter_style_copy_mode(False)

    def apply_style(self, source_info: ImageInfo):
        logging.info(f"Применяем стиль с '{source_info.path}' на '{self.style_target_info.path}'")
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
        try:
            original_path = self.style_target_info.path
            path_without_ext, _ = os.path.splitext(original_path)
            new_path = f"{path_without_ext}_stylized.jpg"
            pil_image.save(new_path, "JPEG", quality=95, optimize=True)
            QMessageBox.information(self.view, "Успех", f"Стилизованный файл сохранен как:\n{new_path}")
        except Exception as e:
            QMessageBox.critical(self.view, "Ошибка", f"Не удалось сохранить файл: {e}")

    def handle_keep_best(self, best_info: ImageInfo):
        try:
            if not best_info.group_id:
                QMessageBox.information(self.view, "Информация", "Это уникальное фото, в группе нет других файлов.")
                return

            infos_to_delete =[
                info for info in self.groups.get(best_info.group_id, [])
                if info.path != best_info.path
            ]
            if infos_to_delete:
                self.handle_delete(infos_to_delete)
        except Exception as e:
            QMessageBox.critical(self.view, "Ошибка", f"Произошла ошибка: {e}")

    TRASH_DIR = os.path.join(os.path.expanduser("~"), ".wiphoto", "trash")

    def _move_to_trash(self, file_path: str) -> bool:
        """Перемещает файл в локальную корзину WiPhoto"""
        os.makedirs(self.TRASH_DIR, exist_ok=True)
        basename = os.path.basename(file_path)
        dest = os.path.join(self.TRASH_DIR, basename)
        # Если файл с таким именем уже есть в корзине, добавляем индекс
        if os.path.exists(dest):
            name, ext = os.path.splitext(basename)
            counter = 1
            while os.path.exists(dest):
                dest = os.path.join(self.TRASH_DIR, f"{name}_{counter}{ext}")
                counter += 1
        shutil.move(file_path, dest)
        return True

    def handle_delete(self, infos_to_delete: list[ImageInfo]):
        """Удаляет выбранные файлы в корзину с обновлением коллекций"""
        try:
            count = len(infos_to_delete)
            reply = QMessageBox.question(
                self.view, "Подтверждение удаления",
                f"Переместить {count} файл(ов) в корзину?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )

            if reply == QMessageBox.StandardButton.Yes:
                failed_files = []
                succeeded =[]

                for info in infos_to_delete:
                    try:
                        self._move_to_trash(info.path)
                        xmp_path = os.path.splitext(info.path)[0] + ".xmp"
                        if os.path.exists(xmp_path):
                            try:
                                self._move_to_trash(xmp_path)
                            except Exception:
                                pass
                        succeeded.append(info)
                    except Exception as e:
                        logging.error(f"Не удалось удалить {info.path}: {e}")
                        failed_files.append(info.path)

                if succeeded:
                    self.view.remove_thumbnails(succeeded)
                    succeeded_set = set(id(i) for i in succeeded)
                    self.image_data =[info for info in self.image_data if id(info) not in succeeded_set]
                    self._update_collections()
                    if self.groups:
                        self._run_advanced_duplicate_search()

                if failed_files:
                    QMessageBox.warning(
                        self.view, "Предупреждение",
                        f"Не удалось удалить {len(failed_files)} файл(ов):\n" +
                        "\n".join(os.path.basename(f) for f in failed_files[:5])
                    )
        except Exception as e:
            QMessageBox.critical(self.view, "Ошибка", f"Произошла ошибка: {e}")

    def handle_copy(self, infos_to_copy: list[ImageInfo]):
        try:
            dest_dir = QFileDialog.getExistingDirectory(self.view, "Выберите папку для копирования")
            if dest_dir:
                failed_files =[]
                succeeded = 0

                for info in infos_to_copy:
                    dest_path = os.path.join(dest_dir, os.path.basename(info.path))
                    if os.path.abspath(dest_path) == os.path.abspath(info.path):
                        continue
                        
                    if os.path.exists(dest_path):
                        reply = QMessageBox.question(
                            self.view, "Конфликт имён",
                            f"Файл '{os.path.basename(info.path)}' уже существует в целевой папке.\nЗаменить его?",
                            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel
                        )
                        if reply == QMessageBox.StandardButton.Cancel:
                            break
                        if reply == QMessageBox.StandardButton.No:
                            continue

                    try:
                        shutil.copy2(info.path, dest_path)
                        succeeded += 1
                    except Exception as e:
                        logging.error(f"Не удалось скопировать {info.path}: {e}")
                        failed_files.append(info.path)

                if failed_files:
                    QMessageBox.warning(self.view, "Предупреждение", f"Не удалось скопировать {len(failed_files)} файл(ов).")
                elif succeeded > 0:
                    QMessageBox.information(self.view, "Готово", f"{succeeded} файл(ов) скопировано.")
        except Exception as e:
            QMessageBox.critical(self.view, "Ошибка", f"Произошла ошибка: {e}")

    def handle_move(self, infos_to_move: list[ImageInfo]):
        try:
            dest_dir = QFileDialog.getExistingDirectory(self.view, "Выберите папку для перемещения")
            if dest_dir:
                failed_files = []
                succeeded =[]

                for info in infos_to_move:
                    dest_path = os.path.join(dest_dir, os.path.basename(info.path))
                    
                    if os.path.abspath(dest_path) == os.path.abspath(info.path):
                        continue
                        
                    if os.path.exists(dest_path):
                        reply = QMessageBox.question(
                            self.view, "Конфликт имён",
                            f"Файл '{os.path.basename(info.path)}' уже существует в целевой папке.\nЗаменить его?",
                            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel
                        )
                        if reply == QMessageBox.StandardButton.Cancel:
                            break
                        if reply == QMessageBox.StandardButton.No:
                            continue
                    try:
                        shutil.move(info.path, dest_path)
                        succeeded.append(info)
                    except Exception as e:
                        logging.error(f"Не удалось переместить {info.path}: {e}")
                        failed_files.append(info.path)

                if succeeded:
                    self.view.remove_thumbnails(succeeded)
                    succeeded_set = set(id(i) for i in succeeded)
                    self.image_data =[info for info in self.image_data if id(info) not in succeeded_set]
                    self._update_collections()
                    if self.groups:
                        self._run_advanced_duplicate_search()

                if failed_files:
                    QMessageBox.warning(self.view, "Предупреждение", f"Не удалось переместить {len(failed_files)} файл(ов).")
                elif succeeded:
                    QMessageBox.information(self.view, "Готово", f"{len(succeeded)} файл(ов) перемещено.")
        except Exception as e:
            QMessageBox.critical(self.view, "Ошибка", f"Произошла ошибка: {e}")

    def handle_export(self, infos_to_export: list[ImageInfo]):
        """Экспорт выбранных файлов с автоматической конвертацией RAW/DNG в JPEG"""
        try:
            dest_dir = QFileDialog.getExistingDirectory(self.view, "Выберите папку для экспорта")
            if not dest_dir:
                return

            failed_files =[]
            succeeded = 0
            
            progress = QProgressDialog("Экспорт файлов...", "Отмена", 0, len(infos_to_export), self.view)
            progress.setWindowTitle("Экспорт")
            progress.setWindowModality(Qt.WindowModality.WindowModal)
            progress.setMinimumDuration(0)
            progress.setValue(0)
            
            for i, info in enumerate(infos_to_export):
                QApplication.processEvents()
                if progress.wasCanceled():
                    break
                    
                ext = os.path.splitext(info.path)[1].lower()
                is_raw = ext in RAW_FORMATS
                
                if is_raw:
                    base = os.path.basename(info.path)
                    name, _ = os.path.splitext(base)
                    dest_path = os.path.join(dest_dir, f"{name}_exported.jpg")
                else:
                    dest_path = os.path.join(dest_dir, os.path.basename(info.path))
                
                if os.path.abspath(dest_path) == os.path.abspath(info.path):
                    progress.setValue(i + 1)
                    continue

                if os.path.exists(dest_path):
                    reply = QMessageBox.question(
                        self.view, "Конфликт имён",
                        f"Файл '{os.path.basename(dest_path)}' уже существует.\nЗаменить его?",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel
                    )
                    if reply == QMessageBox.StandardButton.Cancel:
                        break
                    if reply == QMessageBox.StandardButton.No:
                        progress.setValue(i + 1)
                        continue
                        
                try:
                    if is_raw:
                        img = _load_image_optimized(info.path, for_thumbnail=False)
                        if img:
                            img.save(dest_path, "JPEG", quality=95)
                            succeeded += 1
                        else:
                            failed_files.append(info.path)
                    else:
                        shutil.copy2(info.path, dest_path)
                        succeeded += 1
                except Exception as e:
                    logging.error(f"Export error {info.path}: {e}")
                    failed_files.append(info.path)
                    
                progress.setValue(i + 1)

            if failed_files:
                QMessageBox.warning(self.view, "Предупреждение", f"Не удалось экспортировать {len(failed_files)} файлов.")
            elif succeeded > 0:
                QMessageBox.information(self.view, "Готово", f"Успешно экспортировано {succeeded} файлов.")
        except Exception as e:
            QMessageBox.critical(self.view, "Ошибка", f"Произошла ошибка: {e}")

    def _handle_batch_rename(self, image_infos: list):
        try:
            from views.batch_rename_dialog import BatchRenameDialog
            dialog = BatchRenameDialog(image_infos, self.view)
            if dialog.exec():
                rename_map = dialog.get_rename_map()
                renamed = 0
                errors =[]
                for old_path, new_path in rename_map.items():
                    if old_path == new_path: continue
                    try:
                        os.rename(old_path, new_path)
                        for info in self.image_data:
                            if info.path == old_path:
                                info.path = new_path
                                break
                        renamed += 1
                    except Exception as e:
                        errors.append(f"{os.path.basename(old_path)}: {e}")

                if errors:
                    QMessageBox.warning(self.view, "Ошибки", f"Не удалось переименовать:\n" + "\n".join(errors[:10]))

                self.view.statusBar().showMessage(f"Переименовано: {renamed} файлов")
                self._update_collections()
        except Exception as e:
            logging.error(f"Batch rename error: {e}")

    def _handle_delete_rejected(self):
        rejected =[info for info in self.image_data if info.flag_status == "rejected"]
        if not rejected:
            self.view.statusBar().showMessage("Нет отклонённых файлов")
            return
        self.handle_delete(rejected)

    def _handle_find_similar(self, target_info: ImageInfo):
        try:
            if not target_info.phash:
                self.view.statusBar().showMessage("Нет хеша для сравнения")
                return

            import imagehash
            target_hash = imagehash.hex_to_hash(target_info.phash)
            threshold = 15

            similar =[]
            for info in self.image_data:
                if info.path == target_info.path: continue
                if info.phash:
                    try:
                        h = imagehash.hex_to_hash(info.phash)
                        dist = target_hash - h
                        if dist <= threshold:
                            similar.append((dist, info))
                    except Exception:
                        pass

            similar.sort(key=lambda x: x[0])
            result = [info for _, info in similar[:50]]

            if result:
                self.view.clear_thumbnails()
                self.view.add_thumbnails_batch(result)
                self.view.statusBar().showMessage(f"Найдено {len(result)} похожих на {os.path.basename(target_info.path)}")
            else:
                self.view.statusBar().showMessage("Похожих изображений не найдено")
        except Exception as e:
            logging.error(f"Find similar error: {e}")
            self.view.statusBar().showMessage(f"Ошибка поиска: {e}")

    def _handle_refresh(self):
        if self.image_data:
            folder = os.path.dirname(self.image_data[0].path)
            self.start_scan(folder, True)

    def _run_advanced_duplicate_search(self, method: str = "phash"):
        try:
            threshold = settings.get_hamming_threshold()
            if method == "combined":
                groups = self.duplicate_finder.find_duplicates_combined(
                    self.image_data, methods=["phash", "dhash"], threshold=threshold)
            else:
                groups = self.duplicate_finder.find_duplicates_single_method(
                    self.image_data, method=method, threshold=threshold)
            self.duplicate_finder.apply_groups_to_images(groups, mark_best=True)
            self.groups = groups
            self.view.update_thumbnail_styles()
        except Exception as e:
            logging.error(f"Ошибка пересчёта дубликатов: {e}")

    def cleanup(self):
        logging.info("Контроллер: Остановка сканера и выход из потока...")
        try:
            if hasattr(self, '_ai_manager'):
                self._ai_manager.stop()
            if self.scanner:
                self.scanner.stop()

            self.scanner_thread.quit()
            if not self.scanner_thread.wait(5000):
                logging.warning("Контроллер: Принудительное завершение потока сканера...")
                self.scanner_thread.terminate()
                self.scanner_thread.wait()

            logging.info("Контроллер: Поток сканера завершен.")
        except Exception as e:
            logging.error(f"Ошибка при остановке сканера: {e}")