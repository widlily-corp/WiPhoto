# main.py

import sys
import os
import threading

# ─────────────────────────────────────────────────────────────────────────────
# OS-LEVEL stderr filter — ДОЛЖЕН быть первым, до любых импортов.
#
# Проблема: libtiff / OpenCV / Qt пишут шум напрямую в fd=2, минуя sys.stderr.
# Python-уровневый wrapper (sys.stderr = ...) этот поток не перехватывает.
# Решение: перенаправляем fd=2 в pipe, читаем в фоновом потоке, фильтруем.
# ─────────────────────────────────────────────────────────────────────────────
_STDERR_NOISE: tuple[bytes, ...] = (
    b"TIFF_Warning", b"TIFF_Error", b"grfmt_tiff",
    b"TIFFRead", b"TIFFRGBAImage", b"_TIFFVSetField",
    b"PhotometricInterpretation", b"Bad value",
    b"qt.qpa.wayland", b"zwp_text_input",
    b"This plugin supports",
    b"[ WARN:", b"[ERROR:",   # OpenCV C-level WARN / ERROR метки
)


def _install_stderr_pipe_filter() -> threading.Thread:
    """
    Создаёт pipe, перенаправляет fd=2 в его write-end,
    в фоновом потоке читает построчно и пропускает только не-шумовые строки.
    Работает для любых C-библиотек, не только Python-кода.
    """
    r_fd, w_fd = os.pipe()
    real_fd = os.dup(2)       # сохраняем настоящий stderr (терминал / journald)
    os.dup2(w_fd, 2)          # fd=2 → write-end пайпа
    os.close(w_fd)            # write-end теперь только fd=2

    def _loop() -> None:
        with os.fdopen(r_fd, "rb", 0) as src, os.fdopen(real_fd, "wb", 0) as dst:
            while True:
                line = src.readline()
                if not line:          # EOF: write-end закрыт (выход процесса)
                    break
                if not any(marker in line for marker in _STDERR_NOISE):
                    dst.write(line)
                    dst.flush()

    t = threading.Thread(target=_loop, daemon=True, name="stderr-filter")
    t.start()
    return t


_stderr_filter_thread = _install_stderr_pipe_filter()
# ─────────────────────────────────────────────────────────────────────────────

import signal
import multiprocessing
import traceback
import logging
from datetime import datetime
from pathlib import Path

from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPalette, QColor

from controllers.app_controller import AppController
from utils import resource_path


def setup_logging():
    log_dir = os.path.join(os.path.expanduser("~"), ".wiphoto", "logs")
    try:
        os.makedirs(log_dir, exist_ok=True)
        log_filename = datetime.now().strftime("wiphoto_%Y%m%d_%H%M%S.log")
        log_path = os.path.join(log_dir, log_filename)
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(levelname)s - %(message)s",
            handlers=[
                logging.FileHandler(log_path, encoding="utf-8"),
                logging.StreamHandler(sys.stdout),
            ],
        )
        logging.info("=" * 50)
        logging.info("WiPhoto запущен")
        logging.info("=" * 50)
        return log_path
    except Exception as e:
        print(f"Не удалось настроить логирование: {e}")
        return None


def log_system_info():
    import platform

    logging.info("Информация о системе:")
    logging.info(f"  Python: {sys.version}")
    logging.info(f"  Платформа: {platform.system()} {platform.release()}")
    logging.info(f"  Архитектура: {platform.machine()}")
    logging.info(f"  Процессор: {platform.processor()}")

    dependencies = {
        "PyQt6": "PyQt6.QtCore",
        "Pillow": "PIL",
        "OpenCV": "cv2",
        "ImageHash": "imagehash",
        "RawPy": "rawpy",
        "Scikit-Image": "skimage",
        "NumPy": "numpy",
    }
    logging.info("\nУстановленные зависимости:")
    for name, module in dependencies.items():
        try:
            mod = __import__(module)
            version = getattr(mod, "__version__", "неизвестна")
            logging.info(f"  [OK] {name}: {version}")
        except ImportError:
            logging.error(f"  [FAIL] {name}: НЕ УСТАНОВЛЕН!")


def exception_hook(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    logging.error("\n" + "=" * 50)
    logging.error("КРИТИЧЕСКАЯ ОШИБКА ПРИЛОЖЕНИЯ")
    logging.error("=" * 50)
    logging.error(
        "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    )
    logging.error("=" * 50 + "\n")
    try:
        error_msg = f"{exc_type.__name__}: {exc_value}"
        QMessageBox.critical(
            None,
            "Критическая ошибка",
            f"Произошла непредвиденная ошибка:\n\n{error_msg}\n\n"
            f"Подробности сохранены в лог-файле.",
        )
    except Exception as e:
        logging.error(f"Ошибка показа диалога: {e}")


def check_critical_files():
    critical_files = ["assets/icon.ico", "pro_dark.qss"]
    missing_files = []
    for file in critical_files:
        path = resource_path(file)
        if not os.path.exists(path):
            missing_files.append(file)
            logging.warning(f"Отсутствует файл: {file}")
    return missing_files


def set_dark_palette(app):
    try:
        app.setStyle("Fusion")
        palette = QPalette()
        color_window = QColor(30, 35, 45)
        color_window_text = QColor(224, 224, 224)
        color_base = QColor(37, 41, 53)
        color_alternate = QColor(45, 50, 65)
        color_text = QColor(224, 224, 224)
        color_button = QColor(58, 64, 80)
        color_button_text = QColor(224, 224, 224)
        color_highlight = QColor(61, 142, 201)
        color_highlight_text = QColor(255, 255, 255)

        palette.setColor(QPalette.ColorRole.Window, color_window)
        palette.setColor(QPalette.ColorRole.WindowText, color_window_text)
        palette.setColor(QPalette.ColorRole.Base, color_base)
        palette.setColor(QPalette.ColorRole.AlternateBase, color_alternate)
        palette.setColor(QPalette.ColorRole.ToolTipBase, color_window)
        palette.setColor(QPalette.ColorRole.ToolTipText, color_window_text)
        palette.setColor(QPalette.ColorRole.Text, color_text)
        palette.setColor(QPalette.ColorRole.Button, color_button)
        palette.setColor(QPalette.ColorRole.ButtonText, color_button_text)
        palette.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.red)
        palette.setColor(QPalette.ColorRole.Link, QColor(42, 130, 218))
        palette.setColor(QPalette.ColorRole.Highlight, color_highlight)
        palette.setColor(QPalette.ColorRole.HighlightedText, color_highlight_text)
        palette.setColor(
            QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor(128, 128, 128)
        )
        palette.setColor(
            QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText, QColor(128, 128, 128)
        )
        palette.setColor(
            QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, QColor(128, 128, 128)
        )
        palette.setColor(
            QPalette.ColorGroup.Disabled, QPalette.ColorRole.Base, QColor(30, 35, 45)
        )
        palette.setColor(
            QPalette.ColorGroup.Disabled, QPalette.ColorRole.Window, QColor(30, 35, 45)
        )
        app.setPalette(palette)
    except Exception as e:
        logging.error(f"Ошибка установки палитры: {e}")


def load_stylesheet(app):
    try:
        stylesheet_path = resource_path("pro_dark.qss")
        if not os.path.exists(stylesheet_path):
            logging.warning(f"Файл стилей не найден: {stylesheet_path}")
            return False
        with open(stylesheet_path, "r", encoding="utf-8") as f:
            stylesheet_template = f.read()
        assets_path = resource_path("assets")
        assets_uri = Path(assets_path).as_uri()
        final_stylesheet = stylesheet_template.replace("{ASSETS_PATH}", assets_uri)
        app.setStyleSheet(final_stylesheet)
        logging.info("Стили успешно загружены")
        return True
    except Exception as e:
        logging.error(f"Ошибка загрузки стилей: {e}\n{traceback.format_exc()}")
        return False


def main():
    multiprocessing.freeze_support()

    if sys.platform.startswith("win"):
        multiprocessing.set_start_method("spawn", force=True)

    log_path = setup_logging()
    log_system_info()

    logging.info("\nПроверка ExifTool...")
    try:
        from core.metadata_reader import EXIFTOOL_AVAILABLE, EXIFTOOL_PATH

        if EXIFTOOL_AVAILABLE:
            logging.info(f"ExifTool доступен: {EXIFTOOL_PATH}")
        else:
            logging.warning("ExifTool не найден — метаданные EXIF будут недоступны")
            if not sys.platform.startswith("win"):
                logging.warning("Установите: sudo apt install libimage-exiftool-perl")
    except Exception as e:
        logging.error(f"Ошибка проверки ExifTool: {e}")

    sys.excepthook = exception_hook

    check_critical_files()

    try:
        QApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
        )
        app = QApplication(sys.argv)
        app.setApplicationName("WiPhoto")
        app.setApplicationVersion("2.4.1")
        app.setOrganizationName("Widlily Corporation")
        logging.info("QApplication создан успешно")
    except Exception as e:
        logging.critical(f"Не удалось создать QApplication: {e}")
        logging.critical(traceback.format_exc())
        return 1

    # ── SIGINT (Ctrl+C) → штатный выход через Qt event loop ─────────────────
    # Без этого: Python raises KeyboardInterrupt в main thread → Qt не успевает
    # остановить фоновые потоки → "QThread: Destroyed while thread is still running"
    def _handle_sigint(_sig, _frame):
        logging.info("Получен SIGINT — завершение...")
        app.quit()

    signal.signal(signal.SIGINT, _handle_sigint)
    # Qt не доставляет Python-сигналы пока крутит event loop;
    # таймер каждые 200 мс "будит" интерпретатор — сигнал обрабатывается.
    _sigint_timer = QTimer()
    _sigint_timer.start(200)
    _sigint_timer.timeout.connect(lambda: None)
    # ─────────────────────────────────────────────────────────────────────────

    set_dark_palette(app)
    load_stylesheet(app)

    try:
        app_controller = AppController()
        logging.info("AppController создан успешно")
        app.aboutToQuit.connect(app_controller.cleanup)
        app_controller.show()
        logging.info("Интерфейс отображён")
    except Exception as e:
        logging.critical(f"Не удалось создать AppController: {e}")
        logging.critical(traceback.format_exc())
        QMessageBox.critical(
            None,
            "Ошибка запуска",
            f"Не удалось запустить приложение:\n\n{e}\n\n"
            f"Проверьте лог-файл для подробностей.",
        )
        return 1

    try:
        logging.info("Запуск главного цикла приложения")
        exit_code = app.exec()
        logging.info(f"Приложение завершено с кодом: {exit_code}")
        logging.info("=" * 50)
        return exit_code
    except Exception as e:
        logging.critical(f"Критическая ошибка в главном цикле: {e}")
        logging.critical(traceback.format_exc())
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
