# core/metadata_reader.py

import subprocess
import os
import sys
import logging


def _get_app_data_dir():
    """Возвращает директорию данных приложения"""
    if sys.platform.startswith('win'):
        base = os.environ.get('LOCALAPPDATA', os.path.expanduser('~'))
        return os.path.join(base, 'WiPhoto')
    else:
        return os.path.join(os.path.expanduser('~'), '.local', 'share', 'wiphoto')


def _download_exiftool_windows():
    """Скачивает ExifTool для Windows автоматически"""
    import zipfile
    import urllib.request

    data_dir = _get_app_data_dir()
    exiftool_dir = os.path.join(data_dir, 'exiftool_files')
    exiftool_exe = os.path.join(exiftool_dir, 'exiftool.exe')

    if os.path.exists(exiftool_exe):
        return exiftool_exe

    os.makedirs(exiftool_dir, exist_ok=True)
    logging.info("Скачивание ExifTool для Windows...")

    try:
        url = "https://sourceforge.net/projects/exiftool/files/exiftool-13.52_64.zip/download"
        zip_path = os.path.join(data_dir, 'exiftool.zip')
        urllib.request.urlretrieve(url, zip_path)

        with zipfile.ZipFile(zip_path, 'r') as zf:
            zf.extractall(exiftool_dir)

        # exiftool zip содержит exiftool(-k).exe — переименовываем
        for f in os.listdir(exiftool_dir):
            if f.lower().startswith('exiftool') and f.lower().endswith('.exe'):
                src = os.path.join(exiftool_dir, f)
                if src != exiftool_exe:
                    os.rename(src, exiftool_exe)
                    break

        os.remove(zip_path)
        logging.info(f"ExifTool установлен: {exiftool_exe}")
        return exiftool_exe
    except Exception as e:
        logging.error(f"Не удалось скачать ExifTool: {e}")
        return None


def get_exiftool_path():
    """Возвращает путь к exiftool, при необходимости скачивает"""
    if sys.platform.startswith('win'):
        exiftool_name = 'exiftool.exe'
    else:
        exiftool_name = 'exiftool'

    # 1. Проверяем рядом с приложением (bundled)
    if getattr(sys, 'frozen', False):
        if hasattr(sys, '_MEIPASS'):
            base_path = sys._MEIPASS
        else:
            base_path = os.path.dirname(sys.executable)
    else:
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    for check_dir in [os.path.join(base_path, 'exiftool_files'), base_path]:
        path = os.path.join(check_dir, exiftool_name)
        if os.path.exists(path):
            return path

    # 2. Проверяем в данных приложения (скачанный ранее)
    data_path = os.path.join(_get_app_data_dir(), 'exiftool_files', exiftool_name)
    if os.path.exists(data_path):
        return data_path

    # 3. Linux: системный exiftool
    if not sys.platform.startswith('win'):
        import shutil
        system_exiftool = shutil.which('exiftool')
        if system_exiftool:
            return system_exiftool

    # 4. Windows: скачиваем автоматически
    if sys.platform.startswith('win'):
        downloaded = _download_exiftool_windows()
        if downloaded:
            return downloaded

    return data_path  # fallback path


# Флаг доступности
EXIFTOOL_PATH = get_exiftool_path()
EXIFTOOL_AVAILABLE = os.path.exists(EXIFTOOL_PATH)

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
        logging.error(f"ExifTool не найден: {EXIFTOOL_PATH}")
        return False
    else:
        logging.info(f"Служба ExifTool готова: {EXIFTOOL_PATH}")
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
        logging.error(f"Ошибка чтения EXIF: {e}")
        return {"Error": "Не удалось обработать ответ ExifTool."}
