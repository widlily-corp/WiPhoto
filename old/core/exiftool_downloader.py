# core/exiftool_downloader.py

import os
import sys
import urllib.request
import zipfile
import tarfile
import shutil
import platform
from pathlib import Path


class ExifToolDownloader:
    """Автоматическое скачивание и установка ExifTool"""

    # URL для скачивания
    WINDOWS_URL = "https://exiftool.org/exiftool-12.70.zip"
    LINUX_URL = "https://exiftool.org/Image-ExifTool-12.70.tar.gz"
    MACOS_URL = "https://exiftool.org/ExifTool-12.70.dmg"

    def __init__(self):
        """Инициализация downloader"""
        self.base_dir = self._get_base_dir()
        self.exiftool_dir = os.path.join(self.base_dir, 'exiftool_files')
        self.system = platform.system().lower()

    def _get_base_dir(self):
        """Получить базовую директорию приложения"""
        if getattr(sys, 'frozen', False):
            # Скомпилированное приложение
            if hasattr(sys, '_MEIPASS'):
                # PyInstaller temporary folder - нельзя писать сюда
                # Используем директорию рядом с exe
                return os.path.dirname(sys.executable)
            else:
                return os.path.dirname(sys.executable)
        else:
            # Запуск из исходников
            return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def is_exiftool_available(self):
        """Проверяет наличие ExifTool"""
        if self.system == 'windows':
            exiftool_path = os.path.join(self.exiftool_dir, 'exiftool.exe')
            if os.path.exists(exiftool_path):
                return True
            # Проверяем также старую версию в корне
            old_path = os.path.join(self.base_dir, 'exiftool.exe')
            if os.path.exists(old_path):
                return True
        else:
            # Linux/Mac - проверяем системный
            exiftool_path = shutil.which('exiftool')
            if exiftool_path:
                return True
            # Проверяем локальную версию
            local_path = os.path.join(self.exiftool_dir, 'exiftool')
            if os.path.exists(local_path):
                return True

        return False

    def download_exiftool(self, callback=None):
        """
        Скачивает и устанавливает ExifTool

        Args:
            callback: Функция для отображения прогресса (принимает процент 0-100)

        Returns:
            bool: True если успешно, False иначе
        """
        try:
            # Создаём директорию если нет
            os.makedirs(self.exiftool_dir, exist_ok=True)

            if self.system == 'windows':
                return self._download_windows(callback)
            elif self.system == 'linux':
                return self._download_linux(callback)
            elif self.system == 'darwin':
                # macOS - используем системный package manager
                print("На macOS рекомендуется установить ExifTool через Homebrew:")
                print("  brew install exiftool")
                return False
            else:
                print(f"Неподдерживаемая система: {self.system}")
                return False

        except Exception as e:
            print(f"Ошибка при скачивании ExifTool: {e}")
            return False

    def _download_windows(self, callback=None):
        """Скачивание для Windows"""
        print("Скачивание ExifTool для Windows...")

        # Скачиваем архив
        zip_path = os.path.join(self.exiftool_dir, 'exiftool.zip')

        def report_hook(block_num, block_size, total_size):
            if callback and total_size > 0:
                percent = min(100, int(block_num * block_size * 100 / total_size))
                callback(percent)

        try:
            urllib.request.urlretrieve(self.WINDOWS_URL, zip_path, report_hook)
        except Exception as e:
            print(f"Ошибка скачивания: {e}")
            return False

        # Распаковываем
        print("Распаковка ExifTool...")
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(self.exiftool_dir)

            # Переименовываем exiftool(-k).exe в exiftool.exe
            for file in os.listdir(self.exiftool_dir):
                if file.startswith('exiftool') and file.endswith('.exe'):
                    old_path = os.path.join(self.exiftool_dir, file)
                    new_path = os.path.join(self.exiftool_dir, 'exiftool.exe')
                    if old_path != new_path:
                        shutil.move(old_path, new_path)
                    break

            # Удаляем архив
            os.remove(zip_path)

            print("ExifTool успешно установлен!")
            return True

        except Exception as e:
            print(f"Ошибка распаковки: {e}")
            return False

    def _download_linux(self, callback=None):
        """Скачивание для Linux"""
        print("Скачивание ExifTool для Linux...")

        # Скачиваем tar.gz
        tar_path = os.path.join(self.exiftool_dir, 'exiftool.tar.gz')

        def report_hook(block_num, block_size, total_size):
            if callback and total_size > 0:
                percent = min(100, int(block_num * block_size * 100 / total_size))
                callback(percent)

        try:
            urllib.request.urlretrieve(self.LINUX_URL, tar_path, report_hook)
        except Exception as e:
            print(f"Ошибка скачивания: {e}")
            return False

        # Распаковываем
        print("Распаковка ExifTool...")
        try:
            with tarfile.open(tar_path, 'r:gz') as tar_ref:
                tar_ref.extractall(self.exiftool_dir)

            # Находим распакованную папку
            extracted_dir = None
            for item in os.listdir(self.exiftool_dir):
                if item.startswith('Image-ExifTool-'):
                    extracted_dir = os.path.join(self.exiftool_dir, item)
                    break

            if extracted_dir:
                # Перемещаем exiftool в корень exiftool_files
                exiftool_src = os.path.join(extracted_dir, 'exiftool')
                exiftool_dst = os.path.join(self.exiftool_dir, 'exiftool')
                shutil.copy2(exiftool_src, exiftool_dst)

                # Делаем исполняемым
                os.chmod(exiftool_dst, 0o755)

                # Копируем lib папку
                lib_src = os.path.join(extracted_dir, 'lib')
                lib_dst = os.path.join(self.exiftool_dir, 'lib')
                if os.path.exists(lib_src):
                    if os.path.exists(lib_dst):
                        shutil.rmtree(lib_dst)
                    shutil.copytree(lib_src, lib_dst)

                # Удаляем временные файлы
                shutil.rmtree(extracted_dir)

            # Удаляем архив
            os.remove(tar_path)

            print("ExifTool успешно установлен!")
            return True

        except Exception as e:
            print(f"Ошибка распаковки: {e}")
            return False

    def get_exiftool_path(self):
        """Возвращает путь к ExifTool после установки"""
        if self.system == 'windows':
            return os.path.join(self.exiftool_dir, 'exiftool.exe')
        else:
            local_path = os.path.join(self.exiftool_dir, 'exiftool')
            if os.path.exists(local_path):
                return local_path
            # Fallback на системный
            return shutil.which('exiftool') or 'exiftool'


def ensure_exiftool_available(show_ui=True):
    """
    Убеждается что ExifTool доступен, скачивает если нужно

    Args:
        show_ui: Показывать ли GUI прогресс (для будущей интеграции)

    Returns:
        bool: True если ExifTool доступен
    """
    downloader = ExifToolDownloader()

    if downloader.is_exiftool_available():
        return True

    print("\n" + "="*50)
    print("ExifTool не найден!")
    print("="*50)
    print("ExifTool необходим для чтения метаданных фотографий.")
    print("Начинаю автоматическое скачивание...\n")

    success = downloader.download_exiftool()

    if success:
        print("\n" + "="*50)
        print("ExifTool успешно установлен!")
        print("="*50 + "\n")
        return True
    else:
        print("\n" + "="*50)
        print("ОШИБКА: Не удалось установить ExifTool")
        print("="*50)
        print("\nПожалуйста, установите вручную:")
        if platform.system().lower() == 'windows':
            print("  1. Скачайте с https://exiftool.org/")
            print("  2. Распакуйте в папку exiftool_files/")
        else:
            print("  Ubuntu/Debian: sudo apt install libexiftool-perl")
            print("  Fedora: sudo dnf install perl-Image-ExifTool")
            print("  Arch: sudo pacman -S perl-image-exiftool")
        print("="*50 + "\n")
        return False
