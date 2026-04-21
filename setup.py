# setup.py для cx_Freeze

import sys
from cx_Freeze import setup, Executable
import os

# --- ИМПОРТИРУЕМ МЕТАДАННЫЕ ИЗ НАШЕГО НОВОГО ФАЙЛА ---
from _meta import __version__, __author__, __email__, __description__

# Зависимости
build_exe_options = {
    "packages": [
        "PyQt6",
        "PIL",
        "numpy",
        "rawpy",
        "cv2",
        "skimage",
        "imagehash",
    ],
    "excludes": [
        "tkinter",
        "matplotlib",
        "scipy",
        "pandas",
    ],
    "include_files": [
        # Ресурсы приложения
        ("assets", "assets"),
        ("liquid_glass.qss", "liquid_glass.qss"),
    ],
    "include_msvcr": True,
}

# Определяем базу для GUI приложения (без консоли)
base = None
if sys.platform == "win32":
    base = "Win32GUI"

setup(
    name="WiPhoto",
    version=__version__,
    description=__description__,
    author=__author__,
    author_email=__email__,
    options={
        "build_exe": build_exe_options
    },
    executables=[
        Executable(
            "main.py",
            base=base,
            target_name="WiPhoto.exe",
            icon="assets/icon.ico",
            shortcut_name="WiPhoto",
            shortcut_dir="DesktopFolder",
        )
    ]
)