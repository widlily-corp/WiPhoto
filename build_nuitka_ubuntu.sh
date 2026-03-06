#!/bin/bash
# ========================================
# WiPhoto v2.0.0 Ubuntu Build Script (Nuitka)
# ========================================

set -e  # Exit on error

echo "========================================"
echo "WiPhoto v2.0.0 Ubuntu Build with Nuitka"
echo "========================================"
echo ""

# Check if running on Ubuntu/Debian
if ! command -v apt &> /dev/null; then
    echo "WARNING: This script is optimized for Ubuntu/Debian"
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Install system dependencies
echo "Checking system dependencies..."
echo ""

MISSING_DEPS=()

if ! dpkg -l 2>/dev/null | grep -q "^ii.*libgl1[: ]"; then
    MISSING_DEPS+=("libgl1")
fi
if ! dpkg -l 2>/dev/null | grep -q "^ii.*libglib2.0-0"; then
    MISSING_DEPS+=("libglib2.0-0t64")
fi
if ! dpkg -l 2>/dev/null | grep -q "^ii.*libxcb-xinerama0"; then
    MISSING_DEPS+=("libxcb-xinerama0")
fi
if ! dpkg -l 2>/dev/null | grep -q "^ii.*libxcb-cursor0"; then
    MISSING_DEPS+=("libxcb-cursor0")
fi
if ! dpkg -l 2>/dev/null | grep -q "^ii.*libimage-exiftool-perl"; then
    MISSING_DEPS+=("libimage-exiftool-perl")
fi
if ! dpkg -l 2>/dev/null | grep -q "^ii.*patchelf"; then
    MISSING_DEPS+=("patchelf")
fi
if ! dpkg -l 2>/dev/null | grep -q "^ii.*ccache"; then
    MISSING_DEPS+=("ccache")
fi

if [ ${#MISSING_DEPS[@]} -ne 0 ]; then
    echo "Missing system dependencies: ${MISSING_DEPS[*]}"
    echo ""
    echo "Installing missing dependencies..."
    sudo apt update
    sudo apt install -y ${MISSING_DEPS[*]}
fi

echo "System dependencies OK"
echo ""

# Setup virtual environment
if [ ! -f ".venv/bin/activate" ]; then
    echo "Creating virtual environment..."
    rm -rf .venv
    python3 -m venv .venv
fi

echo "Activating virtual environment..."
source .venv/bin/activate

# Install Python dependencies
echo ""
echo "Installing Python dependencies..."
pip install --upgrade pip wheel
pip install -r requirements.txt
pip install pillow-heif
pip install nuitka ordered-set zstandard

# Clean previous builds
echo ""
echo "Cleaning previous builds..."
rm -rf build/wiphoto.dist
rm -rf build/wiphoto.build
rm -rf dist/WiPhoto_Linux

# Create dist directory
mkdir -p dist

echo ""
echo "========================================"
echo "Building WiPhoto v2.0.0 with Nuitka..."
echo "This may take 15-30 minutes..."
echo "========================================"
echo ""

# Build with Nuitka
python -m nuitka \
    --standalone \
    --onefile \
    --enable-plugin=pyqt6 \
    --include-data-dir=assets=assets \
    --include-data-file=liquid_glass.qss=liquid_glass.qss \
    --include-package=cv2 \
    --include-package=PIL \
    --include-package=numpy \
    --include-package=rawpy \
    --include-package=imagehash \
    --include-package=skimage \
    --include-package=pillow_heif \
    --include-package-data=cv2 \
    --nofollow-import-to=matplotlib \
    --nofollow-import-to=scipy \
    --nofollow-import-to=tkinter \
    --nofollow-import-to=torch \
    --nofollow-import-to=torchvision \
    --nofollow-import-to=simple_lama_inpainting \
    --linux-icon=assets/icon.ico \
    --output-dir=build \
    main.py

if [ $? -ne 0 ]; then
    echo ""
    echo "Build FAILED!"
    exit 1
fi

echo ""
echo "========================================"
echo "Creating distribution package..."
echo "========================================"

# Create distribution directory
mkdir -p dist/WiPhoto_Linux

# Copy executable
cp build/main.bin dist/WiPhoto_Linux/WiPhoto
chmod +x dist/WiPhoto_Linux/WiPhoto

# Copy data files
cp -r assets dist/WiPhoto_Linux/
cp liquid_glass.qss dist/WiPhoto_Linux/

# Create launcher script
cat > dist/WiPhoto_Linux/wiphoto.sh << 'LAUNCHER_EOF'
#!/bin/bash
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"
export LD_LIBRARY_PATH="$SCRIPT_DIR:$LD_LIBRARY_PATH"
if [ -n "$WAYLAND_DISPLAY" ] && [ -z "$FORCE_X11" ]; then
    export QT_QPA_PLATFORM=wayland
else
    export QT_QPA_PLATFORM=xcb
fi
exec ./WiPhoto "$@"
LAUNCHER_EOF

chmod +x dist/WiPhoto_Linux/wiphoto.sh

# Create README
cat > dist/WiPhoto_Linux/README.txt << 'README_EOF'
WiPhoto v2.0.0 for Linux

Installation:
1. Install dependencies:
   sudo apt install libgl1 libimage-exiftool-perl libxcb-xinerama0 libxcb-cursor0

2. Run:
   ./wiphoto.sh

https://github.com/widlily-corp/WiPhoto
README_EOF

# Create install script
cat > dist/WiPhoto_Linux/install.sh << 'INSTALL_EOF'
#!/bin/bash
set -e
echo "Installing WiPhoto v2.0.0..."
if [ "$EUID" -ne 0 ]; then
    exec sudo "$0" "$@"
fi
INSTALL_DIR="/opt/wiphoto"
mkdir -p "$INSTALL_DIR"
cp -r ./* "$INSTALL_DIR/"
chmod +x "$INSTALL_DIR/WiPhoto"
chmod +x "$INSTALL_DIR/wiphoto.sh"
cat > /usr/share/applications/wiphoto.desktop << DESKTOP_EOF
[Desktop Entry]
Type=Application
Name=WiPhoto
Comment=Professional Photo Manager
Exec=$INSTALL_DIR/wiphoto.sh %F
Icon=$INSTALL_DIR/assets/icon.ico
Terminal=false
Categories=Graphics;Photography;
MimeType=image/jpeg;image/png;image/bmp;image/gif;image/tiff;image/heic;video/mp4;
DESKTOP_EOF
ln -sf "$INSTALL_DIR/wiphoto.sh" /usr/local/bin/wiphoto
echo "Installation complete! Run 'wiphoto' or find WiPhoto in applications menu"
INSTALL_EOF

chmod +x dist/WiPhoto_Linux/install.sh

echo ""
echo "Creating archive..."

cd dist
tar -czf WiPhoto_v2.0.0_Linux.tar.gz WiPhoto_Linux/
cd ..

if [ -f "dist/WiPhoto_v2.0.0_Linux.tar.gz" ]; then
    echo ""
    echo "========================================"
    echo "Build completed successfully!"
    echo "========================================"
    echo ""
    echo "Executable: dist/WiPhoto_Linux/WiPhoto"
    echo "Archive: dist/WiPhoto_v2.0.0_Linux.tar.gz"
    echo ""
    ls -lh dist/WiPhoto_v2.0.0_Linux.tar.gz
    echo ""
    echo "Test: cd dist/WiPhoto_Linux && ./wiphoto.sh"
else
    echo "Archive creation FAILED!"
    exit 1
fi
