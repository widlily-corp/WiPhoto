# WiPhoto

![WiPhoto Logo](assets/icon.ico)

**Professional Photo Manager & Editor** | **Профессиональный менеджер и редактор фотографий**

WiPhoto is a powerful photo manager and non-destructive image editor built with Python and PyQt6. Lightroom-inspired 3-column layout, 30+ RAW formats, video support, AI analysis, and advanced duplicate detection.

WiPhoto — мощный менеджер и редактор фотографий на Python и PyQt6. Трёхколоночный интерфейс в стиле Lightroom, 30+ RAW форматов, видео, ИИ-анализ и продвинутый поиск дубликатов.

---

## Features / Возможности

### Photo Management / Управление фото
- **30+ RAW formats**: ARW, CR2, CR3, NEF, NRW, DNG, RW2, ORF, PEF, RAF, and more via rawpy
- **Video support**: MP4, AVI, MOV, MKV, WMV, FLV, WebM preview and playback
- **HEIC/HEIF support** via pillow-heif
- **Smart Collections**: Auto-grouping by quality, faces, animals, location, duplicates
- **Duplicate Detection**: Perceptual hashing (pHash, dHash, aHash, combined) with quality ranking
- **EXIF Metadata**: Full metadata display via ExifTool
- **Batch Operations**: Copy, move, delete, export, rename
- **Timeline View**: Browse photos chronologically with FlowLayout wrapping
- **Map View**: GPS coordinates display

### Non-Destructive Editing / Недеструктивное редактирование
- **Real-time Preview** with adjustable quality
- **Full Undo/Redo** with visual history tree
- **Tools**: Exposure, Contrast, Highlights, Shadows, Whites, Blacks, Temperature, Tint, Vibrance, Saturation, Clarity, Sharpness, Vignette, Crop, Rotate, Flip
- **Before/After** comparison mode
- **Keyboard shortcuts**: Ctrl+Z/Y (undo/redo), Ctrl+S (save), Ctrl+0/1 (fit/100%), Escape (back)

### Interface / Интерфейс
- **Lightroom-style 3-column layout**: Left sidebar (folders, collections, filters) | Center (gallery grid/loupe/map) | Right sidebar (preview, metadata, AI info)
- **Professional dark theme** — flat, solid colors, no transparencies
- **Uniform thumbnail grid** with custom delegate (video overlay, face badges, duplicate indicators)
- **Collapsible sidebars** with toggle buttons
- **Zoom slider** for thumbnail size control
- **Quick View** overlay (Space key)
- **Drag & Drop** file import

### AI & Analysis / ИИ и анализ
- **Face detection** (YuNet)
- **Animal detection**
- **Image quality scoring** (sharpness, exposure)
- **Document scanning** with perspective correction

---

## Downloads / Скачать

Download from [Releases](https://github.com/widlily-corp/WiPhoto/releases):

- **Windows**: `WiPhoto_v2.1.1_Windows.zip` — extract and run `WiPhoto.exe`
- **Linux**: `WiPhoto_v2.1.1_Linux.tar.gz` — extract and run `./wiphoto.sh`

### Linux Dependencies / Зависимости Linux
```bash
sudo apt install libgl1 libimage-exiftool-perl libxcb-xinerama0 libxcb-cursor0
```

---

## Build from Source / Сборка из исходников

```bash
git clone https://github.com/widlily-corp/WiPhoto.git
cd WiPhoto
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

### Build Executables / Сборка бинарников
```bash
# Linux
bash build_nuitka_ubuntu.sh

# Windows
build_nuitka_windows.bat
```

---

## System Requirements / Системные требования

| | Minimum | Recommended |
|---|---------|-------------|
| **OS** | Windows 10+ / Ubuntu 22.04+ | Windows 11 / Ubuntu 24.04+ |
| **RAM** | 4 GB | 8 GB+ |
| **Storage** | 500 MB | 1 GB |
| **Display** | 1280x720 | 1920x1080+ |

Also works on: Debian 11+, Fedora 36+, Arch Linux

---

## Keyboard Shortcuts / Горячие клавиши

| Action / Действие | Shortcut |
|---|---|
| Settings / Настройки | `Ctrl + ,` |
| Delete / Удалить | `Delete` |
| Copy / Копировать | `Ctrl + C` |
| Move / Переместить | `Ctrl + X` |
| Compare / Сравнить | `Ctrl + D` |
| Fullscreen / Полный экран | `F11` |
| Quick View / Быстрый просмотр | `Space` |
| Next/Prev / Следующий/Предыдущий | `→` / `←` |
| Select All / Выделить всё | `Ctrl + A` |
| Refresh / Обновить | `F5` |
| Undo / Отмена | `Ctrl + Z` |
| Redo / Повтор | `Ctrl + Y` |
| Save / Сохранить | `Ctrl + S` |
| Back to Gallery / Назад в галерею | `Escape` |
| Zoom Fit / Zoom 100% | `Ctrl + 0` / `Ctrl + 1` |

---

## Architecture / Архитектура

MVC pattern / Паттерн MVC:

```
WiPhoto/
├── assets/              # Icons, resources
├── core/                # Image processing, scanning, analysis
│   ├── editing/         # Non-destructive editing tools
│   ├── api/             # External API integrations
│   ├── analyzer.py      # Image analysis (faces, animals, quality)
│   ├── file_scanner.py  # Multi-process file scanning
│   └── metadata_reader.py  # ExifTool integration
├── models/              # Data models (ImageInfo, RAW_EXTENSIONS)
├── views/               # PyQt6 UI components
├── controllers/         # Business logic
├── main.py              # Entry point
├── _meta.py             # Version info
└── pro_dark.qss         # Professional dark stylesheet
```

---

## Contributing / Участие

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Commit and push
4. Open a Pull Request

---

## License / Лицензия

Copyright © 2026, Widlily Corporation. All rights reserved.

## Contact / Контакты

- **Email**: widlily.corp@gmail.com
- **GitHub**: [widlily-corp](https://github.com/widlily-corp)

## Acknowledgments / Благодарности

[PyQt6](https://www.riverbankcomputing.com/software/pyqt/) · [Pillow](https://python-pillow.org/) · [OpenCV](https://opencv.org/) · [scikit-image](https://scikit-image.org/) · [rawpy](https://github.com/letmaik/rawpy) · [ExifTool](https://exiftool.org/) · [imagehash](https://github.com/JohannesBuchner/imagehash) · [pillow-heif](https://github.com/bigcat88/pillow_heif)

---

**Made with ❤️ by Widlily Corporation**
