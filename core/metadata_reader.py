# core/metadata_reader.py

import subprocess
import os
import sys
import logging
import threading
import time


def _get_app_data_dir():
    if sys.platform.startswith('win'):
        base = os.environ.get('LOCALAPPDATA', os.path.expanduser('~'))
        return os.path.join(base, 'WiPhoto')
    else:
        return os.path.join(os.path.expanduser('~'), '.local', 'share', 'wiphoto')


def _download_exiftool_windows():
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
    if sys.platform.startswith('win'):
        exiftool_name = 'exiftool.exe'
    else:
        exiftool_name = 'exiftool'

    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS if hasattr(sys, '_MEIPASS') else os.path.dirname(sys.executable)
    else:
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    check_paths = [
        os.path.join(base_path, exiftool_name),
        os.path.join(base_path, 'exiftool_files', exiftool_name),
    ]

    for check_path in check_paths:
        if os.path.exists(check_path):
            return check_path

    data_path = os.path.join(_get_app_data_dir(), 'exiftool_files', exiftool_name)
    if os.path.exists(data_path):
        return data_path

    if not sys.platform.startswith('win'):
        import shutil
        system_exiftool = shutil.which('exiftool')
        if system_exiftool:
            return system_exiftool

    if sys.platform.startswith('win') and not getattr(sys, 'frozen', False):
        downloaded = _download_exiftool_windows()
        if downloaded:
            return downloaded

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

_READY_SENTINEL = b"{ready}"

# Таймаут на один файл в секундах.
# 5 с достаточно для любого JPEG/RAW; 10 с давало ложные «зависания» при
# временной нагрузке диска.
_EXIFTOOL_TIMEOUT = 5.0


class _ExifToolDaemon:
    """
    Держит один процесс ExifTool в режиме -stay_open.
    Потокобезопасен через _io_lock.
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
            "-@", "-",
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
        self._dead = False
        logging.info(f"ExifToolDaemon запущен (PID {self._proc.pid})")

    def _alive(self) -> bool:
        return not self._dead and self._proc.poll() is None

    def execute(self, file_path: str) -> str:
        """
        Читает метаданные через stay_open daemon.
        Sentinel конца вывода: строка b'{ready}' после каждого -execute.
        """
        if self._dead:
            return ""

        if sys.platform.startswith('win'):
            return ""

        cmd_bytes = f"{file_path}\n-execute\n".encode("utf-8")

        with self._io_lock:
            if self._dead:
                return ""
            try:
                self._proc.stdin.write(cmd_bytes)
                self._proc.stdin.flush()
            except (BrokenPipeError, OSError):
                self._dead = True
                return ""

            output_parts: list[bytes] = []
            import select

            try:
                deadline = time.monotonic() + _EXIFTOOL_TIMEOUT
                while True:
                    remaining = max(0.0, deadline - time.monotonic())

                    ready, _, _ = select.select(
                        [self._proc.stdout], [], [], remaining
                    )
                    if not ready:
                        # select вернул пустой список — реальный таймаут
                        logging.warning(
                            f"ExifTool timeout ({_EXIFTOOL_TIMEOUT:.0f}s) для {file_path}"
                        )
                        self._dead = True
                        try:
                            self._proc.kill()
                        except Exception:
                            pass
                        return ""

                    line = self._proc.stdout.readline()
                    if not line:
                        self._dead = True
                        return ""

                    if line.strip() == _READY_SENTINEL:
                        break

                    output_parts.append(line)

            except (BrokenPipeError, OSError):
                self._dead = True
                return ""
            except Exception as e:
                logging.debug(f"ExifToolDaemon.execute unexpected error: {e}")
                self._dead = True
                return ""

        return b"".join(output_parts).decode("utf-8", errors="ignore")

    def terminate(self):
        self._dead = True
        try:
            self._proc.stdin.write(b"-stay_open\nFalse\n")
            self._proc.stdin.flush()
        except Exception:
            pass
        try:
            self._proc.stdin.close()
        except Exception:
            pass
        try:
            self._proc.wait(timeout=2)
        except Exception:
            pass
        try:
            self._proc.kill()
        except Exception:
            pass
        try:
            self._proc.stdout.close()
        except Exception:
            pass


def _parse_exiftool_output(stdout_str: str) -> dict:
    metadata = {}
    for line in stdout_str.splitlines():
        if ":" in line:
            key, _, val = line.partition(":")
            metadata[key.strip()] = val.strip()
    return metadata


def startup_exiftool():
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
    with _ExifToolDaemon._lock:
        d = _ExifToolDaemon._instance
        if d:
            try:
                d.terminate()
            except Exception:
                pass
            _ExifToolDaemon._instance = None


def _run_exiftool_fallback(file_path: str) -> str:
    if not EXIFTOOL_AVAILABLE:
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
            timeout=_EXIFTOOL_TIMEOUT,
            cwd=os.path.dirname(EXIFTOOL_PATH),
            **kwargs,
        )
        if sys.platform.startswith('win'):
            return result.stdout.decode('cp1251', errors='ignore')
        return result.stdout.decode('utf-8', errors='ignore')
    except subprocess.TimeoutExpired:
        logging.warning(f"ExifTool subprocess timeout для {file_path}")
        return ""
    except FileNotFoundError:
        logging.error(f"ExifTool не найден: {EXIFTOOL_PATH}")
        return ""
    except Exception as e:
        logging.error(f"ExifTool ошибка для {file_path}: {e}")
        return ""


def _is_worker_thread() -> bool:
    return threading.current_thread() is not threading.main_thread()


def _get_raw_output(file_path: str) -> str:
    if not sys.platform.startswith('win') and _is_worker_thread():
        daemon = _ExifToolDaemon.get()
        if daemon and daemon._alive():
            result = daemon.execute(os.path.normpath(file_path))
            if result:
                return result
    return _run_exiftool_fallback(file_path)


def read_metadata(image_path: str) -> dict:
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
