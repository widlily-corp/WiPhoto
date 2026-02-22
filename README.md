# WiPhoto

![WiPhoto Logo](assets/icon.ico)

**Professional Photo Management and Editing Application**

WiPhoto is a powerful, feature-rich photo manager and non-destructive image editor built with Python and PyQt6. It combines advanced image processing capabilities with an intuitive user interface to help photographers organize, analyze, and edit their photo collections efficiently.

## ✨ Features

### Photo Management
- **Smart Photo Scanning**: Multi-threaded folder scanning with progress tracking
- **RAW Format Support**: Native support for `.arw`, `.cr2`, `.nef`, `.dng`, and `.raw` files via rawpy
- **Duplicate Detection**: Advanced perceptual hashing to identify similar images
- **Smart Collections**: Intelligent filtering and organization
- **Metadata Viewing**: Comprehensive EXIF data display using ExifTool
- **Batch Operations**: Copy, move, or delete multiple files at once

### Non-Destructive Editing
- **Real-time Preview**: Instant visual feedback with adjustable preview quality
- **Undo/Redo System**: Complete history tree for all editing operations
- **Professional Tools**:
  - **Light**: Exposure, Contrast, Highlights, Shadows, Whites, Blacks
  - **Color**: Temperature, Tint, Vibrance, Saturation
  - **Detail**: Clarity, Sharpness
  - **Effects**: Vignette
  - **Transform**: Crop, Rotate, Flip (Horizontal/Vertical)

### User Interface
- **Modern Design**: Custom "Liquid Glass" dark theme with glass-morphism effects
- **Multi-tab Layout**: Gallery, Smart Collections, Comparison, and Editor views
- **Image Comparison**: Side-by-side view for comparing photos
- **Keyboard Shortcuts**: Efficient workflow with hotkeys
- **Drag & Drop**: Easy file import

## 📋 System Requirements

### Minimum Requirements
- **OS**: Windows 10/11 (64-bit)
- **RAM**: 4 GB
- **Storage**: 500 MB free space
- **Display**: 1280x720 resolution

### Recommended Requirements
- **OS**: Windows 10/11 (64-bit)
- **RAM**: 8 GB or more
- **Storage**: 1 GB free space
- **Display**: 1920x1080 or higher
- **CPU**: Multi-core processor for faster image processing

### Linux Compatibility

WiPhoto can run on Linux with the following setup:

**Tested Distributions:**
- Ubuntu 22.04 LTS and later
- Debian 11+
- Fedora 36+
- Arch Linux (latest)

**Installation Steps for Linux:**

1. Install system dependencies:
   ```bash
   # Ubuntu/Debian
   sudo apt install python3-pyqt6 python3-pip libexiftool-perl

   # Fedora
   sudo dnf install python3-qt6 python3-pip perl-Image-ExifTool

   # Arch
   sudo pacman -S python-pyqt6 python-pip perl-image-exiftool
   ```

2. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Modify `core/metadata_reader.py`:
   - Change `exiftool.exe` to `exiftool` (system ExifTool)
   - Or download Linux ExifTool from https://exiftool.org/

**Known Issues:**
- Some UI themes may look different on certain desktop environments
- Tested with GNOME, KDE Plasma, and XFCE
- Dark theme works best on dark system themes

**Performance Notes:**
- Linux version typically runs 10-15% faster due to better process handling
- RAW file processing benefits from native library support

## 🚀 Installation

### From Source

1. **Clone the repository**:
   ```bash
   git clone https://github.com/widlily-corp/WiPhoto.git
   cd WiPhoto
   ```

2. **Create virtual environment**:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Download ExifTool**:
   - Download from [https://exiftool.org/](https://exiftool.org/)
   - Place `exiftool.exe` in the project root directory

5. **Run the application**:
   ```bash
   python main.py
   ```

### Building Executable (Windows)

```bash
python setup.py build
```

The executable will be created in the `build/` directory.

## 🎯 Usage

### Getting Started

1. **Launch WiPhoto**: Run `python main.py` or use the built executable
2. **Select Folder**: Choose a folder containing your photos
3. **Wait for Scanning**: The app will analyze all images and create thumbnails
4. **Explore**: Use tabs to navigate between Gallery, Smart Collections, Comparison, and Editor views

### Keyboard Shortcuts

| Action | Shortcut |
|--------|----------|
| Settings | `Ctrl + ,` |
| Delete | `Delete` |
| Copy | `Ctrl + C` |
| Move | `Ctrl + X` |
| Rotate | `R` |
| Compare | `Ctrl + D` |
| Fullscreen | `F11` |
| Quick View | `Space` |
| Next Image | `→` |
| Previous Image | `←` |
| Select All | `Ctrl + A` |
| Deselect All | `Ctrl + Shift + A` |
| Refresh | `F5` |
| Quit | `Ctrl + Q` |

### Editing Workflow

1. Select an image in the Gallery
2. Switch to the **Editor** tab
3. Adjust parameters using sliders in the control panel
4. See real-time preview of changes
5. Use **Reset** to revert individual tools or **Reset All** for complete reset
6. Export when satisfied with results

## 🛠️ Architecture

WiPhoto follows the Model-View-Controller (MVC) pattern:

- **Models** (`models/`): Data structures (e.g., `ImageInfo`)
- **Views** (`views/`): PyQt6 UI components
- **Controllers** (`controllers/`): Business logic and coordination
- **Core** (`core/`): Image processing, file scanning, duplicate detection

### Key Components

- **Image Processor** (`core/editing/image_processor.py`): Non-destructive editing pipeline
- **File Scanner** (`core/file_scanner.py`): Multi-process image scanning
- **Editing Tools** (`core/editing/tool_*.py`): Individual image adjustment tools
- **Metadata Reader** (`core/metadata_reader.py`): ExifTool integration

## 🔮 Planned Features

### Upcoming Enhancements

- **Geotag Support**: Display and edit GPS metadata, map integration
- **Face Detection**: Automatic face recognition and organization
- **Animal Detection**: Identify and tag pets/wildlife in photos
- **Document Scanning**: Auto-detect document boundaries, perspective correction, OCR
- **Additional Export Formats**: Support for more output formats
- **Cloud Integration**: Backup and sync capabilities
- **Plugin System**: Extensible architecture for third-party tools

## 📝 Development

### Project Structure

```
WiPhoto/
├── assets/              # Icons, images, resources
├── core/                # Core functionality
│   ├── editing/         # Image editing tools
│   ├── api/             # External API integrations
│   ├── file_scanner.py  # Photo scanning
│   ├── analyzer.py      # Image analysis
│   └── metadata_reader.py
├── models/              # Data models
├── views/               # UI components
├── controllers/         # Application controllers
├── main.py              # Entry point
├── _meta.py             # Version and metadata
├── liquid_glass.qss     # Stylesheet
└── requirements.txt     # Dependencies
```

### Adding a New Editing Tool

1. Create `core/editing/tool_yourname.py` inheriting from `EditingTool`
2. Implement required methods: `name`, `label`, `_create_ui()`, `apply()`, `get_params()`, `set_params()`, `reset()`
3. Add to `core/editing/__init__.py`:
   - Import the tool
   - Add to appropriate group in `TOOL_GROUPS`
   - Add to `ALL_TOOLS_MAP`

## 🤝 Contributing

Contributions are welcome! Please follow these guidelines:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Code Style

- Follow PEP 8 guidelines
- Use type hints where applicable
- Add docstrings for public methods
- Keep UI text in Russian (for now - internationalization planned)

## 📄 License

Copyright © 2026, Widlily Corporation. All rights reserved.

## 📧 Contact

- **Email**: widlily.corp@gmail.com
- **GitHub**: [widlily-corp](https://github.com/widlily-corp)

## 🙏 Acknowledgments

- Built with [PyQt6](https://www.riverbankcomputing.com/software/pyqt/)
- Image processing powered by [Pillow](https://python-pillow.org/), [OpenCV](https://opencv.org/), and [scikit-image](https://scikit-image.org/)
- RAW support via [rawpy](https://github.com/letmaik/rawpy)
- Metadata handling with [ExifTool](https://exiftool.org/) by Phil Harvey
- Duplicate detection using [imagehash](https://github.com/JohannesBuchner/imagehash)

---

**Made with ❤️ by Widlily Corporation**
