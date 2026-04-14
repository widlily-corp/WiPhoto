# core/metadata_reader.py

import subprocess
import os
import sys
import logging
import threading
import queue
import time


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

    # Определяем base_path (где находится приложение)
    if getattr(sys, 'frozen', False):
        # Nuitka или PyInstaller
        if hasattr(sys, '_MEIPASS'):
            # PyInstaller
            base_path = sys._MEIPASS
        else:
            # Nuitka: exe находится в папке рядом с .dist папкой
            base_path = os.path.dirname(sys.executable)
    else:
        # Development: находимся в core/ подпапке, поднимаемся на уровень выше
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    logging.debug(f"ExifTool search - app mode: frozen={getattr(sys, 'frozen', False)}, base_path={base_path}")

    # Порядок поиска в Nuitka builede:
    # 1. base_path/exiftool.exe (рядом с exe)
    # 2. base_path/exiftool_files/exiftool.exe
    # 3. AppData
    # 4. PATH (Unix)
    
    check_paths = [
        os.path.join(base_path, exiftool_name),  # Рядом с exe
        os.path.join(base_path, 'exiftool_files', exiftool_name),  # В папке exiftool_files
    ]
    
    for check_path in check_paths:
        if os.path.exists(check_path):
            logging.info(f"ExifTool найден: {check_path}")
            return check_path

    # Fallback на AppData
    data_path = os.path.join(_get_app_data_dir(), 'exiftool_files', exiftool_name)
    if os.path.exists(data_path):
        logging.info(f"ExifTool найден в AppData: {data_path}")
        return data_path

    # Для Unix ищем в PATH
    if not sys.platform.startswith('win'):
        import shutil
        system_exiftool = shutil.which('exiftool')
        if system_exiftool:
            logging.info(f"ExifTool найден в PATH: {system_exiftool}")
            return system_exiftool

    # Для Windows - пытаемся скачать
    if sys.platform.startswith('win') and not getattr(sys, 'frozen', False):
        logging.info("Попытка скачать ExifTool...")
        downloaded = _download_exiftool_windows()
        if downloaded:
            return downloaded

    # Default return (вернём путь даже если не существует, fallback механизм сработает)
    logging.warning(f"ExifTool не найден по путям: {check_paths}")
    return os.path.join(base_path, exiftool_name)


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


# ---------------------------------------------------------------------------
# ExifTool stay_open daemon — один процесс на весь рантайм воркера
# ---------------------------------------------------------------------------

class _ExifToolDaemon:
    """
    Держит один процесс ExifTool в режиме -stay_open.
    Потокобезопасен: защищён локом, один инстанс на PID воркера.
    """

    _instance: "_ExifToolDaemon | None" = None
    _lock = threading.Lock()

    @classmethod
    def get(cls) -> "_ExifToolDaemon | None":
        if not EXIFTOOL_AVAILABLE:
            return None
        with cls._lock:
            if cls._instance is None or not cls._instance._alive():
                try:
                    cls._instance = cls()
                except Exception as e:
                    logging.error(f"ExifToolDaemon: не удалось запустить: {e}")
                    cls._instance = None
        return cls._instance

    def __init__(self):
        kwargs: dict = {}
        if sys.platform.startswith('win'):
            si = subprocess.STARTUPINFO()
            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            si.wShowWindow = subprocess.SW_HIDE
            kwargs['startupinfo'] = si

        cmd = [
            EXIFTOOL_PATH,
            "-stay_open", "True",
            "-@", "-",          # читаем аргументы из stdin
            "-common_args",
            "-charset", "UTF-8",
        ]
        self._proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            cwd=os.path.dirname(EXIFTOOL_PATH),
            **kwargs,
        )
        self._io_lock = threading.Lock()
        logging.info(f"ExifToolDaemon запущен (PID {self._proc.pid})")

    def _alive(self) -> bool:
        return self._proc.poll() is None

    def execute(self, file_path: str) -> str:
        """Читает метаданные файла, возвращает сырой stdout."""
        cmd_bytes = f"{file_path}\n-execute\n".encode("utf-8")

        with self._io_lock:
            try:
                self._proc.stdin.write(cmd_bytes)
                self._proc.stdin.flush()

                output_parts = []
                timeout = 10  # 10 секунд на чтение EXIF
                import select
                
                if sys.platform.startswith('win'):
                    # На Windows используем простой fallback — это надёжнее
                    # Daemon может привести к зависаниям, лучше использовать subprocess
                    return ""
                
                # На Unix используем select с таймаутом
                while True:
                    ready, _, _ = select.select([self._proc.stdout], [], [], timeout)
                    if not ready:
                        logging.warning(f"ExifTool timeout для {file_path}")
                        break
                    
                    line = self._proc.stdout.readline()
                    if not line:
                        break
                    output_parts.append(line)
                    
                    # Проверяем конец вывода (пустая строка с -execute)
                    if line.strip() == b"":
                        break

                raw = b"".join(output_parts)
                if sys.platform.startswith('win'):
                    return raw.decode('cp1251', errors='ignore')
                return raw.decode('utf-8', errors='ignore')
            except Exception as e:
                logging.error(f"ExifToolDaemon.execute error: {e}")
                return ""

    def terminate(self):
        try:
            self._proc.stdin.write(b"-stay_open\nFalse\n")
            self._proc.stdin.flush()
            self._proc.wait(timeout=5)
        except Exception:
            self._proc.kill()


def _parse_exiftool_output(stdout_str: str) -> dict:
    """Парсит вывод ExifTool в dict."""
    metadata = {}
    for line in stdout_str.splitlines():
        if ":" in line:
            key, _, val = line.partition(":")
            metadata[key.strip()] = val.strip()
    return metadata


def startup_exiftool():
    """Проверяет доступность ExifTool и поднимает daemon."""
    if not os.path.exists(EXIFTOOL_PATH):
        logging.error(f"ExifTool не найден: {EXIFTOOL_PATH}")
        return False
    daemon = _ExifToolDaemon.get()
    if daemon:
        logging.info(f"ExifTool daemon готов: {EXIFTOOL_PATH}")
        return True
    logging.warning("ExifTool daemon не запустился, fallback на subprocess")
    return False


def cleanup_exiftool():
    """Завершает daemon при выходе."""
    with _ExifToolDaemon._lock:
        d = _ExifToolDaemon._instance
        if d:
            try:
                d.terminate()
            except Exception:
                pass
            _ExifToolDaemon._instance = None


def _run_exiftool_fallback(file_path: str) -> str:
    """Старый метод — один subprocess на файл. Используется если daemon упал."""
    if not EXIFTOOL_AVAILABLE:
        logging.warning(f"ExifTool не доступен для {file_path}")
        return ""
    
    kwargs: dict = {}
    if sys.platform.startswith('win'):
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = subprocess.SW_HIDE
        kwargs['startupinfo'] = si

    try:
        result = subprocess.run(
            [EXIFTOOL_PATH, os.path.normpath(file_path)],
            capture_output=True,
            check=False,
            timeout=10,
            cwd=os.path.dirname(EXIFTOOL_PATH),
            **kwargs,
        )
        if sys.platform.startswith('win'):
            return result.stdout.decode('cp1251', errors='ignore')
        return result.stdout.decode('utf-8', errors='ignore')
    except subprocess.TimeoutExpired:
        logging.warning(f"ExifTool timeout для {file_path}")
        return ""
    except FileNotFoundError:
        logging.error(f"ExifTool не найден: {EXIFTOOL_PATH}")
        return ""
    except Exception as e:
        logging.error(f"ExifTool ошибка для {file_path}: {e}")
        return ""


def _get_raw_output(file_path: str) -> str:
    # TEMP: daemon на Windows вызывает зависания, используем fallback
    # daemon = _ExifToolDaemon.get()
    # if daemon:
    #     return daemon.execute(os.path.normpath(file_path))
    return _run_exiftool_fallback(file_path)


def read_metadata(image_path: str) -> dict:
    """Читает все метаданные из файла (включая GPS)."""
    if not EXIFTOOL_AVAILABLE:
        return {}
    try:
        stdout_str = _get_raw_output(image_path)
        if not stdout_str.strip():
            return {}
        return _parse_exiftool_output(stdout_str)
    except Exception:
        return {}


def read_exif(image_path: str) -> dict:
    """Читает EXIF данные из изображения (только ключевые теги)."""
    if not EXIFTOOL_AVAILABLE:
        return {"Error": "ExifTool не найден"}

    try:
        stdout_str = _get_raw_output(image_path)
        if not stdout_str.strip():
            return {"Info": "EXIF-данные отсутствуют."}

        full_metadata = _parse_exiftool_output(stdout_str)

        filtered_metadata = {
            display_name: full_metadata[tag_key]
            for tag_key, display_name in TAG_MAP.items()
            if tag_key in full_metadata
        }
        return filtered_metadata if filtered_metadata else {"Info": "EXIF-данные отсутствуют."}

    except subprocess.TimeoutExpired:
        return {"Error": "Превышено время ожидания"}
    except Exception as e:
        logging.error(f"Ошибка чтения EXIF: {e}")
        return {"Error": "Не удалось обработать ответ ExifTool."}
