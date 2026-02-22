# controllers/app_controller.py

from PyQt6.QtWidgets import QFileDialog
from PyQt6.QtCore import QObject

from views.welcome_window import WelcomeWindow
from views.main_window import MainWindow
from controllers.photo_view_controller import MainController as PhotoViewController
from core.metadata_reader import startup_exiftool, cleanup_exiftool

class AppController(QObject):
    def __init__(self):
        super().__init__()
        startup_exiftool()
        self.welcome_window = WelcomeWindow()
        self.main_window = None
        self.photo_view_controller = None
        self._connect_signals()

    def show(self):
        self.welcome_window.show()

    def _connect_signals(self):
        self.welcome_window.select_folder_button.clicked.connect(self.select_and_process_folder)

    def select_and_process_folder(self):
        folder_path = QFileDialog.getExistingDirectory(self.welcome_window, "Выберите папку с фотографиями")
        if folder_path:
            is_recursive = self.welcome_window.recursive_checkbox.isChecked()

            self.welcome_window.select_folder_button.setEnabled(False)
            self.welcome_window.recursive_checkbox.setEnabled(False)
            self.welcome_window.progress_bar.setVisible(True)

            self.main_window = MainWindow()
            self.photo_view_controller = PhotoViewController(self.main_window)

            # Подключаемся к сигналам прогресса и завершения от сканера
            self.photo_view_controller.scanner.progress_updated.connect(self.update_progress)
            self.photo_view_controller.scanner.finished.connect(self.on_scan_finished)

            # Запускаем сканирование через новый метод контроллера
            self.photo_view_controller.start_scan(folder_path, is_recursive)

    def update_progress(self, current, total):
        self.welcome_window.progress_bar.setMaximum(total)
        self.welcome_window.progress_bar.setValue(current)

    def on_scan_finished(self):
        self.main_window.show()
        self.welcome_window.close()

    def cleanup(self):
        if self.photo_view_controller:
            self.photo_view_controller.cleanup()
        cleanup_exiftool()