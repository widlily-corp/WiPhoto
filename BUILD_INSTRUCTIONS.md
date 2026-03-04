# WiPhoto Build Instructions

## ⚠️ Build System: Nuitka

WiPhoto uses **Nuitka** for compilation (not PyInstaller). Nuitka compiles Python to C for better performance, smaller size, and better reliability.

## Requirements

### All Platforms
- Python 3.9-3.11 (3.11 recommended)
- pip (Python package manager)
- 4 GB RAM minimum, 8 GB recommended
- 5 GB free disk space for build process

### Windows
- **Microsoft Visual C++** 14.0 or higher (Visual Studio 2019/2022 Build Tools)
- Nuitka: `pip install nuitka ordered-set zstandard`
- All dependencies from requirements.txt

**Install MSVC Build Tools:**
1. Download [Visual Studio Build Tools](https://visualstudio.microsoft.com/downloads/#build-tools-for-visual-studio-2022)
2. Install with "Desktop development with C++" workload
3. Or install via: `winget install Microsoft.VisualStudio.2022.BuildTools`

### Linux (Ubuntu/Debian)
```bash
sudo apt update
sudo apt install python3-pip python3-venv python3-dev
sudo apt install build-essential patchelf ccache
sudo apt install libgl1-mesa-glx libglib2.0-0
sudo apt install libxcb-xinerama0 libxcb-cursor0
sudo apt install libexiftool-perl
```

### Linux (Fedora/RHEL)
```bash
sudo dnf install python3-pip python3-devel
sudo dnf install gcc-c++ patchelf ccache
sudo dnf install mesa-libGL glib2
sudo dnf install perl-Image-ExifTool
```

## Build Steps

### Windows (Nuitka)

1. **Setup Virtual Environment**
   ```cmd
   python -m venv .venv
   .venv\Scripts\activate
   ```

2. **Install Dependencies**
   ```cmd
   pip install --upgrade pip
   pip install -r requirements.txt
   pip install nuitka ordered-set zstandard
   ```

3. **Build Application**
   ```cmd
   build_nuitka_windows.bat
   ```

   **Build time**: 10-20 minutes on modern hardware

4. **Output Location**
   - Executable: `dist/WiPhoto_Windows/WiPhoto.exe`
   - Archive: `dist/WiPhoto_v1.5.1_Windows.zip`
   - Single-file executable with all dependencies embedded
   - ExifTool.exe included in exiftool_files/

### Linux (Ubuntu - Nuitka)

1. **Make script executable**
   ```bash
   chmod +x build_nuitka_ubuntu.sh
   ```

2. **Build Application**
   ```bash
   ./build_nuitka_ubuntu.sh
   ```

   The script will automatically:
   - Check and install system dependencies
   - Create virtual environment
   - Install all Python dependencies
   - Build with Nuitka
   - Create distributable package with launcher

   **Build time**: 15-30 minutes on modern hardware

3. **Output Location**
   - Executable: `dist/WiPhoto_Linux/WiPhoto`
   - Archive: `dist/WiPhoto_v1.5.1_Linux.tar.gz`
   - Launcher script: `dist/WiPhoto_Linux/wiphoto.sh`
   - Install script: `dist/WiPhoto_Linux/install.sh`

## Common Issues

### Windows

**Issue**: "Unable to find a C compiler"
- **Solution**: Install Visual Studio Build Tools with C++ workload
  ```cmd
  winget install Microsoft.VisualStudio.2022.BuildTools
  ```

**Issue**: Build is very slow
- **Solution**: This is normal for first build. Nuitka compiles to C which takes time. Subsequent builds are faster.

**Issue**: Out of memory during build
- **Solution**: Close other applications, increase virtual memory, or build with `--low-memory` flag

**Issue**: ExifTool not found in build
- **Solution**: Ensure `exiftool_files/` directory exists with ExifTool.exe before building

### Linux

**Issue**: `libGL.so.1: cannot open shared object file`
- **Solution**:
  ```bash
  sudo apt install libgl1-mesa-glx  # Ubuntu/Debian
  sudo dnf install mesa-libGL       # Fedora
  ```

**Issue**: `patchelf: command not found`
- **Solution**:
  ```bash
  sudo apt install patchelf
  ```

**Issue**: Qt platform plugin error
- **Solution**:
  ```bash
  sudo apt install libxcb-xinerama0 libxcb-cursor0
  ```
  Or use the launcher script which sets proper Qt platform

**Issue**: Application won't start
- **Solution**: Use the provided launcher script:
  ```bash
  cd dist/WiPhoto_Linux
  ./wiphoto.sh
  ```
  The launcher handles library paths and Qt platform detection

## Nuitka vs PyInstaller

### Why Nuitka?

| Feature | Nuitka | PyInstaller |
|---------|--------|-------------|
| Method | Compiles to C | Bundles Python bytecode |
| Speed | Faster execution | Slower |
| Size | Smaller (single file) | Larger (many files) |
| Compatibility | Better | Good |
| Build Time | Longer (10-30 min) | Shorter (3-5 min) |
| Dependencies | More reliable inclusion | Sometimes misses |

### Key Advantages

✅ **Single executable** - One file, not a folder
✅ **Better performance** - Compiled to native code
✅ **Smaller size** - Better compression
✅ **More reliable** - Fewer runtime issues
✅ **Better dependency handling** - Especially for CV2, PyQt6, Torch

## Distribution

### Windows
Distribute the `WiPhoto_v1.5.1_Windows.zip` file. Users extract and run `WiPhoto.exe`.

**No installation required!**

### Linux
Distribute the `WiPhoto_v1.5.1_Linux.tar.gz` file.

**Option 1: Run directly**
```bash
tar -xzf WiPhoto_v1.5.1_Linux.tar.gz
cd WiPhoto_Linux
./wiphoto.sh
```

**Option 2: System-wide install**
```bash
tar -xzf WiPhoto_v1.5.1_Linux.tar.gz
cd WiPhoto_Linux
sudo ./install.sh
# Now run from anywhere: wiphoto
```

## Development Mode

For development without building:

### Windows
```cmd
.venv\Scripts\activate
python main.py
```

### Linux
```bash
source .venv/bin/activate
python3 main.py
```

## Advanced Build Options

### Custom Nuitka Flags

**Faster build (less optimization)**:
```bash
--no-prefer-source-code
```

**Debug build**:
```bash
--debug
--windows-console-mode=force  # Windows
```

**Smaller executable**:
```bash
--lto=yes
```

### Build without GUI (for testing)
```bash
python -m nuitka --standalone --follow-imports main.py
```

## Troubleshooting Build Process

### 1. Clean build
```bash
# Remove build artifacts
rm -rf build/
rm -rf dist/

# Rebuild
./build_nuitka_windows.bat  # Windows
./build_nuitka_ubuntu.sh     # Linux
```

### 2. Verify dependencies
```bash
pip list
pip check
```

### 3. Test before building
```bash
python main.py  # Should run without errors
```

### 4. Check Nuitka version
```bash
python -m nuitka --version
# Should be 2.8+ for best results
```

### 5. Enable verbose output
Edit build script and add:
```bash
--verbose
```

## Performance Optimization

### Build Caching
Nuitka uses ccache on Linux for faster rebuilds:
```bash
export CCACHE_DIR=~/.ccache
export PATH="/usr/lib/ccache:$PATH"
```

### Parallel Compilation
Use all CPU cores:
```bash
--jobs=$(nproc)  # Linux
--jobs=%NUMBER_OF_PROCESSORS%  # Windows
```

## Version Information

- **App Version**: 1.5.1
- **Build System**: Nuitka 2.8+
- **Python**: 3.9-3.11
- **UI Framework**: PyQt6
- **Image Processing**: OpenCV, Pillow, scikit-image
- **AI Models**: PyTorch, simple-lama-inpainting

## Support

For build issues:
1. Check this document
2. Review Nuitka documentation: https://nuitka.net
3. Check project issues on GitHub
4. Ensure all system dependencies are installed

## Tips for Smaller Builds

1. **Exclude unused packages** - Edit build script to add:
   ```bash
   --nofollow-import-to=matplotlib
   --nofollow-import-to=scipy
   --nofollow-import-to=tkinter
   ```

2. **Use UPX compression** (Windows only):
   ```bash
   --windows-onefile-tempdir-spec=%TEMP%/wiphoto
   ```

3. **Remove debug symbols**:
   ```bash
   --windows-company-name=""
   ```

## License
Check repository for license information.
