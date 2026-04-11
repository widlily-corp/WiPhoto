# core/metadata_reader.py
#
# ОПТИМИЗАЦИЯ: ExifTool теперь запускается в батч-режиме через stay_open / -@
# Вместо subprocess.run на каждый файл — один процесс на всю сессию.
# Скорость чтения метаданных вырастает в 10–50x на больших папках.

import subprocess
import os
import sys
import logging
import threading
import time

logger = logging.getLogger(__name__)


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
    logger.info("Скачивание ExifTool для Windows...")

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
        logger.info(f"ExifTool установлен: {exiftool_exe}")
        return exiftool_exe
    except Exception as e:
        logger.error(f"Не удалось скачать ExifTool: {e}")
        return None


def get_exiftool_path():
    if sys.platform.startswith('win'):
        exiftool_name = 'exiftool.exe'
    else:
        exiftool_name = 'exiftool'

    if getattr(sys, 'frozen', False):
        base_path = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
    else:
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    for check_dir in [os.path.join(base_path, 'exiftool_files'), base_path]:
        path = os.path.join(check_dir, exiftool_name)
        if os.path.exists(path):
            return path

    data_path = os.path.join(_get_app_data_dir(), 'exiftool_files', exiftool_name)
    if os.path.exists(data_path):
        return data_path

    if not sys.platform.startswith('win'):
        import shutil
        system_exiftool = shutil.which('exiftool')
        if system_exiftool:
            return system_exiftool

    if sys.platform.startswith('win'):
        downloaded = _download_exiftool_windows()
        if downloaded:
            return downloaded

    return data_path


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

# ─────────────────────────────────────────────
# ExifTool Daemon — stay_open режим
# ─────────────────────────────────────────────
# Один долгоживущий процесс ExifTool вместо subprocess.run на каждый файл.
# Коммуникация: пишем имя файла в stdin, читаем вывод до маркера "{ready}".

_SENTINEL = "{ready}"
_ENCODING = 'cp1251' if sys.platform.startswith('win') else 'utf-8'


class ExifToolDaemon:
    """
    Управляет одним stay_open процессом ExifTool.
    Потокобезопасен через Lock.
    """

    def __init__(self, exiftool_path: str):
        self._path = exiftool_path
        self._proc: subprocess.Popen | None = None
        self._lock = threading.Lock()
        self._start()

    def _start(self):
        kwargs = {}
        if sys.platform.startswith('win'):
            si = subprocess.STARTUPINFO()
            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            si.wShowWindow = subprocess.SW_HIDE
            kwargs['startupinfo'] = si

        self._proc = subprocess.Popen(
            [self._path, '-stay_open', 'True', '-@', '-'],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            cwd=os.path.dirname(self._path),
            **kwargs,
        )
        logger.info("ExifTool daemon запущен (stay_open mode)")

    def _is_alive(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def _ensure_alive(self):
        if not self._is_alive():
            logger.warning("ExifTool daemon умер, перезапускаем...")
            self._start()

    def execute(self, file_path: str, extra_args: list[str] | None = None) -> str:
        """
        Выполняет ExifTool для одного файла, возвращает stdout как строку.
        """
        with self._lock:
            self._ensure_alive()

            args = (extra_args or []) + [file_path, '-execute\n']
            command = '\n'.join(args)
            try:
                self._proc.stdin.write(command.encode(_ENCODING, errors='replace'))
                self._proc.stdin.flush()
            except OSError as e:
                logger.error(f"Ошибка записи в ExifTool stdin: {e}")
                return ''

            output_lines = []
            try:
                while True:
                    line = self._proc.stdout.readline()
                    if not line:
                        break
                    decoded = line.decode(_ENCODING, errors='ignore').rstrip('\r\n')
                    if decoded == _SENTINEL:
                        break
                    output_lines.append(decoded)
            except Exception as e:
                logger.error(f"Ошибка чтения ExifTool stdout: {e}")

            return '\n'.join(output_lines)

    def execute_batch(self, file_paths: list[str]) -> dict[str, str]:
        """
        Читает метаданные для нескольких файлов за один вызов ExifTool.
        Возвращает dict {path: raw_output}.
        Используй для предварительного кэширования при сканировании.
        """
        if not file_paths:
            return {}

        with self._lock:
            self._ensure_alive()

            # Формируем одну команду на все файлы с разделителем
            lines = []
            for path in file_paths:
                lines.append(path)
            lines.append('-execute\n')

            command = '\n'.join(lines)
            try:
                self._proc.stdin.write(command.encode(_ENCODING, errors='replace'))
                self._proc.stdin.flush()
            except OSError as e:
                logger.error(f"Ошибка записи batch в ExifTool: {e}")
                return {}

            # Читаем вывод до {ready}
            raw_output = []
            try:
                while True:
                    line = self._proc.stdout.readline()
                    if not line:
                        break
                    decoded = line.decode(_ENCODING, errors='ignore').rstrip('\r\n')
                    if decoded == _SENTINEL:
                        break
                    raw_output.append(decoded)
            except Exception as e:
                logger.error(f"Ошибка чтения ExifTool batch stdout: {e}")

            # Разбиваем вывод по файлам через "======== <path>"
            results: dict[str, str] = {}
            current_path = None
            current_lines: list[str] = []

            for line in raw_output:
                if line.startswith('======== '):
                    if current_path is not None:
                        results[os.path.normpath(current_path)] = '\n'.join(current_lines)
                    current_path = line[9:].strip()
                    current_lines = []
                else:
                    current_lines.append(line)

            if current_path is not None:
                results[os.path.normpath(current_path)] = '\n'.join(current_lines)

            return results

    def shutdown(self):
        if self._proc and self._proc.poll() is None:
            try:
                self._proc.stdin.write(b'-stay_open\nFalse\n')
                self._proc.stdin.flush()
                self._proc.wait(timeout=5)
            except Exception:
                self._proc.kill()
            finally:
                self._proc = None
            logger.info("ExifTool daemon остановлен")


# Глобальный синглтон демона
_daemon: ExifToolDaemon | None = None
_daemon_lock = threading.Lock()


def _get_daemon() -> ExifToolDaemon | None:
    global _daemon
    if not EXIFTOOL_AVAILABLE:
        return None
    with _daemon_lock:
        if _daemon is None:
            _daemon = ExifToolDaemon(EXIFTOOL_PATH)
    return _daemon


# ─────────────────────────────────────────────
# Публичный API (совместим со старым кодом)
# ─────────────────────────────────────────────

def startup_exiftool() -> bool:
    if not os.path.exists(EXIFTOOL_PATH):
        logger.error(f"ExifTool не найден: {EXIFTOOL_PATH}")
        return False
    daemon = _get_daemon()
    if daemon is None:
        return False
    logger.info(f"ExifTool daemon готов: {EXIFTOOL_PATH}")
    return True


def cleanup_exiftool():
    global _daemon
    with _daemon_lock:
        if _daemon is not None:
            _daemon.shutdown()
            _daemon = None


def _parse_raw_output(stdout_str: str) -> dict[str, str]:
    metadata = {}
    for line in stdout_str.splitlines():
        if ':' in line:
            key, _, value = line.partition(':')
            metadata[key.strip()] = value.strip()
    return metadata


def read_metadata(image_path: str) -> dict:
    """Читает все метаданные из файла."""
    daemon = _get_daemon()
    if daemon is None:
        return {}
    try:
        stdout_str = daemon.execute(os.path.normpath(image_path))
        if not stdout_str.strip():
            return {}
        return _parse_raw_output(stdout_str)
    except Exception:
        return {}


def read_exif(image_path: str) -> dict:
    """Читает ключевые EXIF-теги из файла."""
    daemon = _get_daemon()
    if daemon is None:
        return {"Error": "ExifTool не найден"}

    try:
        stdout_str = daemon.execute(os.path.normpath(image_path))
        if not stdout_str.strip():
            return {"Info": "EXIF-данные отсутствуют."}

        full_metadata = _parse_raw_output(stdout_str)

        filtered = {
            display: full_metadata[tag]
            for tag, display in TAG_MAP.items()
            if tag in full_metadata
        }
        return filtered if filtered else {"Info": "EXIF-данные отсутствуют."}

    except Exception as e:
        logger.error(f"Ошибка чтения EXIF: {e}")
        return {"Error": "Не удалось обработать ответ ExifTool."}


def read_exif_batch(image_paths: list[str]) -> dict[str, dict]:
    """
    Читает EXIF для нескольких файлов за один запрос к ExifTool.
    Возвращает dict {path: {display_name: value}}.
    Используй при массовом сканировании для максимальной скорости.
    """
    daemon = _get_daemon()
    if daemon is None:
        return {}

    normalized = [os.path.normpath(p) for p in image_paths]
    raw_results = daemon.execute_batch(normalized)

    results = {}
    for path, stdout_str in raw_results.items():
        if not stdout_str.strip():
            results[path] = {}
            continue
        full_metadata = _parse_raw_output(stdout_str)
        results[path] = {
            display: full_metadata[tag]
            for tag, display in TAG_MAP.items()
            if tag in full_metadata
        }
    return results
