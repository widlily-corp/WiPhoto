# core/metadata_reader.py

import subprocess
import os
import sys


def get_exiftool_path():
    """Возвращает корректный путь к exiftool.exe в зависимости от режима запуска"""
    if getattr(sys, 'frozen', False):
        # Запущено из exe - PyInstaller распаковывает файлы
        if hasattr(sys, '_MEIPASS'):
            # Временная папка PyInstaller (ONE-FILE или ONE-DIR)
            base_path = sys._MEIPASS
        else:
            # Папка с exe (если что-то пошло не так)
            base_path = os.path.dirname(sys.executable)
    else:
        # Запущено из исходников - корневая папка проекта
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    exiftool_path = os.path.join(base_path, 'exiftool.exe')
    return exiftool_path


EXIFTOOL_PATH = get_exiftool_path()

# Ключи метаданных
TAG_MAP = {
    "Make": "Камера (производитель)",
    "Camera Model Name": "Камера (модель)",
    "Lens Model": "Объектив",
    "Date/Time Original": "Дата съемки",
    "Exposure Time": "Выдержка",
    "F Number": "Диафрагма",
    "ISO": "ISO",
    "Focal Length": "Фокусное расстояние",
    "Megapixels": "Мегапиксели"
}
TAGS_TO_FIND = list(TAG_MAP.keys())


def startup_exiftool():
    """Проверяет доступность ExifTool"""
    if not os.path.exists(EXIFTOOL_PATH):
        print(f"!!! КРИТИЧЕСКАЯ ОШИБКА: exiftool.exe не найден по пути: {EXIFTOOL_PATH}")
        print(f"[DEBUG] sys.frozen: {getattr(sys, 'frozen', False)}")
        print(f"[DEBUG] sys._MEIPASS: {getattr(sys, '_MEIPASS', 'Не установлен')}")
        print(f"[DEBUG] sys.executable: {sys.executable}")
        return False
    else:
        print(f"[OK] Служба ExifTool готова: {EXIFTOOL_PATH}")
        return True


def cleanup_exiftool():
    """Очистка ресурсов (если нужно)"""
    pass


def read_exif(image_path: str) -> dict:
    """Читает EXIF данные из изображения"""
    if not os.path.exists(EXIFTOOL_PATH):
        print(f"[ERROR] ExifTool не найден: {EXIFTOOL_PATH}")
        return {"Error": "ExifTool не найден"}

    normalized_path = os.path.normpath(image_path)

    # Команда для запуска ExifTool
    command = [
        EXIFTOOL_PATH,
        normalized_path
    ]

    filtered_metadata = {}
    try:
        # Настройки для скрытия окна консоли
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = subprocess.SW_HIDE

        # Устанавливаем рабочую директорию
        exiftool_dir = os.path.dirname(EXIFTOOL_PATH)

        # Запуск ExifTool
        result = subprocess.run(
            command,
            capture_output=True,
            check=False,
            startupinfo=si,
            timeout=10,
            cwd=exiftool_dir  # Рабочая директория = папка с exiftool.exe
        )

        # Декодируем вывод (cp1251 для русского Windows)
        stdout_str = result.stdout.decode('cp1251', errors='ignore')

        if not stdout_str.strip():
            return {"Info": "EXIF-данные отсутствуют."}

        # Парсим текстовый вывод ExifTool
        full_metadata = {}
        lines = stdout_str.splitlines()
        for line in lines:
            if ":" in line:
                # Разделяем по первому двоеточию
                parts = line.split(':', 1)
                key = parts[0].strip()
                value = parts[1].strip()
                full_metadata[key] = value

        # Выбираем только нужные теги
        for tag_key, display_name in TAG_MAP.items():
            if tag_key in full_metadata:
                filtered_metadata[display_name] = full_metadata[tag_key]

    except subprocess.TimeoutExpired:
        print(f"[ERROR] Таймаут при чтении EXIF для '{normalized_path}'")
        return {"Error": "Превышено время ожидания"}
    except Exception as e:
        return {"Error": "Не удалось обработать ответ ExifTool."}

    if not filtered_metadata:
        return {"Info": "EXIF-данные отсутствуют."}

    return filtered_metadata