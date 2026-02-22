# WiPhoto.spec
# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs
import os

block_cipher = None

# Собираем все данные из библиотек
datas = []
datas += collect_data_files('skimage')
datas += collect_data_files('rawpy')

# Явно добавляем наши собственные файлы и папки
added_files = [
    ('assets', 'assets'),
    ('style.qss', '.'),
    ('dark.qss', '.'),
    ('liquid_glass.qss', '.'),  # Если используете новый стиль
]

# КРИТИЧЕСКИ ВАЖНО: Добавляем ExifTool правильно
# Проверяем существование файлов перед добавлением
if os.path.exists('exiftool.exe'):
    added_files.append(('exiftool.exe', '.'))
    print("✓ exiftool.exe найден")
else:
    print("✗ ВНИМАНИЕ: exiftool.exe не найден!")

if os.path.exists('exiftool_files'):
    added_files.append(('exiftool_files', 'exiftool_files'))
    print("✓ exiftool_files найдена")
else:
    print("✗ ВНИМАНИЕ: папка exiftool_files не найдена!")

datas += added_files

# Скрытые импорты для PIL/Pillow и других библиотек
hidden_imports = [
    'PIL._imagingtk',
    'PIL._tkinter_finder',
    'rawpy',
    'numpy',
    'cv2',
]

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False
)

pyz = PYZ(
    a.pure,
    a.zipped_data,
    cipher=block_cipher
)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='WiPhoto',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # Измените на True для отладки
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets\\icon.ico'
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='WiPhoto'
)