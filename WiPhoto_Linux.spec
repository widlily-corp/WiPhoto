# -*- mode: python ; coding: utf-8 -*-
# Linux build specification for WiPhoto

import os
import sys
import cv2
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# Collect OpenCV data files (including Haar cascades)
cv2_data_path = os.path.join(os.path.dirname(cv2.__file__), 'data')
opencv_datas = [(cv2_data_path, 'cv2/data')]

# Collect all hidden imports
hidden_imports = [
    'cv2',
    'numpy',
    'PIL',
    'rawpy',
    'imagehash',
    'skimage',
    'skimage.exposure',
    'simple_lama_inpainting',
    'PyQt6.QtMultimedia',
    'PyQt6.QtMultimediaWidgets',
]

# Add submodules
hidden_imports += collect_submodules('skimage')
hidden_imports += collect_submodules('PIL')

# Collect data files for packages
datas = [
    ('assets', 'assets'),
    ('liquid_glass.qss', '.'),
    ('exiftool_files', 'exiftool_files')
]
datas += opencv_datas
datas += collect_data_files('simple_lama_inpainting', include_py_files=True)

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'scipy'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

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
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='WiPhoto',
)
