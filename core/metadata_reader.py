# core/metadata_reader.py

import subprocess
import os
import sys


def get_exiftool_path():
    """Возвращает корректный путь к exiftool в зависимости от режима запуска и ОС"""
    if sys.platform.startswith('win'):
        exiftool_name = 'exiftool.exe'
    else:
        exiftool_name = 'exiftool'

    if getattr(sys, 'frozen', False):
        if hasattr(sys, '_MEIPASS'):
            base_path = sys._MEIPASS
        else:
            base_path = os.path.dirname(sys.executable)
    else:
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    exiftool_dir = os.path.join(base_path, 'exiftool_files')
    exiftool_path = os.path.join(exiftool_dir, exiftool_name)

    if os.path.exists(exiftool_path):
        return exiftool_path

    exiftool_path = os.path.join(base_path, exiftool_name)
    if os.path.exists(exiftool_path):
        return exiftool_path

    if not sys.platform.startswith('win'):
        import shutil
        system_exiftool = shutil.which('exiftool')
        if system_exiftool:
            return system_exiftool

    return os.path.join(exiftool_dir, exiftool_name)


EXIFTOOL_PATH = get_exiftool_path()

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


def _run_exiftool(command):
    """Запускает ExifTool кроссплатформенно, возвращает stdout строку"""
    kwargs = {}
    if sys.platform.startswith('win'):
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = subprocess.SW_HIDE
        kwargs['startupinfo'] = si

    result = subprocess.run(
        command,
        capture_output=True,
        check=False,
        timeout=10,
        cwd=os.path.dirname(EXIFTOOL_PATH),
        **kwargs
    )

    if sys.platform.startswith('win'):
        return result.stdout.decode('cp1251', errors='ignore')
    else:
        return result.stdout.decode('utf-8', errors='ignore')


def startup_exiftool():
    """Проверяет доступность ExifTool"""
    if not os.path.exists(EXIFTOOL_PATH):
        print(f"[ERROR] ExifTool не найден: {EXIFTOOL_PATH}")
        return False
    else:
        print(f"[OK] Служба ExifTool готова: {EXIFTOOL_PATH}")
        return True


def cleanup_exiftool():
    pass


def read_metadata(image_path: str) -> dict:
    """Читает все метаданные из файла (включая GPS)"""
    if not os.path.exists(EXIFTOOL_PATH):
        return {}

    try:
        stdout_str = _run_exiftool([EXIFTOOL_PATH, os.path.normpath(image_path)])
        if not stdout_str.strip():
            return {}

        metadata = {}
        for line in stdout_str.splitlines():
            if ":" in line:
                parts = line.split(':', 1)
                metadata[parts[0].strip()] = parts[1].strip()
        return metadata
    except Exception:
        return {}


def read_exif(image_path: str) -> dict:
    """Читает EXIF данные из изображения (только ключевые теги)"""
    if not os.path.exists(EXIFTOOL_PATH):
        return {"Error": "ExifTool не найден"}

    try:
        stdout_str = _run_exiftool([EXIFTOOL_PATH, os.path.normpath(image_path)])
        if not stdout_str.strip():
            return {"Info": "EXIF-данные отсутствуют."}

        full_metadata = {}
        for line in stdout_str.splitlines():
            if ":" in line:
                parts = line.split(':', 1)
                full_metadata[parts[0].strip()] = parts[1].strip()

        filtered_metadata = {}
        for tag_key, display_name in TAG_MAP.items():
            if tag_key in full_metadata:
                filtered_metadata[display_name] = full_metadata[tag_key]

        return filtered_metadata if filtered_metadata else {"Info": "EXIF-данные отсутствуют."}

    except subprocess.TimeoutExpired:
        return {"Error": "Превышено время ожидания"}
    except Exception as e:
        print(f"[ERROR] Ошибка чтения EXIF: {e}")
        return {"Error": "Не удалось обработать ответ ExifTool."}
