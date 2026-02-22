# views/progress_dialog.py

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QLabel, QProgressBar,
                             QPushButton, QTextEdit)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QIcon
from utils import resource_path


class ProgressDialog(QDialog):
    """Универсальный диалог прогресса с возможностью отмены"""

    cancelled = pyqtSignal()

    def __init__(self, title="Обработка", parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(500)
        self.setMinimumHeight(200)

        try:
            self.setWindowIcon(QIcon(resource_path("assets/icon.ico")))
        except:
            pass

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        # Заголовок
        self.title_label = QLabel("Пожалуйста, подождите...")
        self.title_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.title_label)

        # Описание текущей операции
        self.status_label = QLabel("Инициализация...")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("color: #888;")
        layout.addWidget(self.status_label)

        # Прогресс-бар
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        layout.addWidget(self.progress_bar)

        # Детальная информация (скрываемая)
        self.details_text = QTextEdit()
        self.details_text.setReadOnly(True)
        self.details_text.setMaximumHeight(150)
        self.details_text.setVisible(False)
        layout.addWidget(self.details_text)

        # Кнопка показа деталей
        self.toggle_details_btn = QPushButton("▼ Показать детали")
        self.toggle_details_btn.clicked.connect(self._toggle_details)
        layout.addWidget(self.toggle_details_btn)

        # Кнопка отмены
        self.cancel_btn = QPushButton("Отменить")
        self.cancel_btn.clicked.connect(self._on_cancel)
        layout.addWidget(self.cancel_btn)

        layout.addStretch()

    def set_title(self, text: str):
        """Устанавливает заголовок"""
        self.title_label.setText(text)

    def set_status(self, text: str):
        """Устанавливает текст статуса"""
        self.status_label.setText(text)

    def set_progress(self, current: int, maximum: int = 100):
        """Устанавливает прогресс"""
        self.progress_bar.setMaximum(maximum)
        self.progress_bar.setValue(current)

    def set_indeterminate(self, enabled: bool = True):
        """Включает/выключает неопределенный режим"""
        if enabled:
            self.progress_bar.setMinimum(0)
            self.progress_bar.setMaximum(0)
        else:
            self.progress_bar.setMinimum(0)
            self.progress_bar.setMaximum(100)

    def add_log(self, text: str):
        """Добавляет запись в лог"""
        self.details_text.append(text)
        # Автоматически прокручиваем вниз
        scrollbar = self.details_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _toggle_details(self):
        """Показывает/скрывает детали"""
        is_visible = self.details_text.isVisible()
        self.details_text.setVisible(not is_visible)

        if is_visible:
            self.toggle_details_btn.setText("▼ Показать детали")
            self.setMinimumHeight(200)
        else:
            self.toggle_details_btn.setText("▲ Скрыть детали")
            self.setMinimumHeight(400)

    def _on_cancel(self):
        """Обработка нажатия кнопки отмены"""
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.setText("Отмена...")
        self.cancelled.emit()

    def complete(self, message: str = "Готово!"):
        """Завершает операцию"""
        self.set_status(message)
        self.set_progress(100, 100)
        self.cancel_btn.setText("Закрыть")
        self.cancel_btn.setEnabled(True)
        self.cancel_btn.clicked.disconnect()
        self.cancel_btn.clicked.connect(self.accept)


class DuplicateSearchDialog(ProgressDialog):
    """Специализированный диалог для поиска дубликатов"""

    def __init__(self, parent=None):
        super().__init__("Поиск дубликатов", parent)
        self.set_title("🔍 Поиск дубликатов")
        self.current_method = ""
        self.found_groups = 0

    def set_method(self, method_name: str):
        """Устанавливает название метода"""
        self.current_method = method_name
        self.set_status(f"Метод: {method_name}")
        self.add_log(f"[INFO] Запуск метода: {method_name}")

    def update_progress(self, current: int, total: int):
        """Обновляет прогресс сканирования"""
        self.set_progress(current, total)
        self.set_status(f"Обработано: {current}/{total} изображений")

    def set_groups_found(self, count: int):
        """Устанавливает количество найденных групп"""
        self.found_groups = count
        self.add_log(f"[RESULT] Найдено групп дубликатов: {count}")

    def show_statistics(self, stats: dict):
        """Показывает статистику"""
        self.add_log("\n=== Статистика ===")
        self.add_log(f"Групп дубликатов: {stats.get('total_groups', 0)}")
        self.add_log(f"Всего дубликатов: {stats.get('total_duplicates', 0)}")
        self.add_log(f"Потенциальная экономия: {stats.get('potential_savings_mb', 0):.2f} МБ")
        self.add_log(f"Средний размер группы: {stats.get('average_group_size', 0):.1f}")


class ScanProgressDialog(ProgressDialog):
    """Специализированный диалог для сканирования файлов"""

    def __init__(self, parent=None):
        super().__init__("Сканирование файлов", parent)
        self.set_title("📁 Сканирование файлов")
        self.total_files = 0
        self.processed_files = 0

    def set_total_files(self, count: int):
        """Устанавливает общее количество файлов"""
        self.total_files = count
        self.set_status(f"Найдено файлов: {count}")
        self.add_log(f"[INFO] Начало обработки {count} файлов")

    def update_file_progress(self, current: int, file_name: str = ""):
        """Обновляет прогресс обработки файлов"""
        self.processed_files = current
        self.set_progress(current, self.total_files)

        if file_name:
            self.set_status(f"Обработка: {file_name}")
            if current % 10 == 0:  # Логируем каждый 10-й файл
                self.add_log(f"[{current}/{self.total_files}] {file_name}")

    def show_completion_stats(self, successful: int, failed: int):
        """Показывает статистику завершения"""
        self.add_log("\n=== Результат сканирования ===")
        self.add_log(f"Успешно обработано: {successful}")
        self.add_log(f"Ошибок: {failed}")
        self.add_log(f"Процент успеха: {(successful / self.total_files * 100):.1f}%")