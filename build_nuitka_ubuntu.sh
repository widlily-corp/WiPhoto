#!/bin/bash
# ========================================
# WiPhoto Ubuntu Build Script (Nuitka)
# ========================================

set -e  # Exit on error

echo "========================================"
echo "WiPhoto Ubuntu Build with Nuitka"
echo "========================================"
echo ""

# Check if running on Ubuntu/Debian
if ! command -v apt &> /dev/null; then
    echo "WARNING: This script is optimized for Ubuntu/Debian"
    echo "It may work on other distributions but is not tested"
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

# Check for required packages
if ! dpkg -l | grep -q libgl1-mesa-glx; then
    MISSING_DEPS+=("libgl1-mesa-glx")
fi
if ! dpkg -l | grep -q libglib2.0-0; then
    MISSING_DEPS+=("libglib2.0-0")
fi
if ! dpkg -l | grep -q libxcb-xinerama0; then
    MISSING_DEPS+=("libxcb-xinerama0")
fi
if ! dpkg -l | grep -q libxcb-cursor0; then
    MISSING_DEPS+=("libxcb-cursor0")
fi
if ! dpkg -l | grep -q libexiftool-perl; then
    MISSING_DEPS+=("libexiftool-perl")
fi
if ! dpkg -l | grep -q patchelf; then
    MISSING_DEPS+=("patchelf")
fi
if ! dpkg -l | grep -q ccache; then
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
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi

echo "Activating virtual environment..."
source .venv/bin/activate

# Install Python dependencies
echo ""
echo "Installing Python dependencies..."
pip install --upgrade pip wheel
pip install -r requirements.txt
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
echo "Building WiPhoto with Nuitka..."
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
    --include-package=simple_lama_inpainting \
    --include-package=torch \
    --include-package=torchvision \
    --include-package-data=cv2 \
    --include-package-data=simple_lama_inpainting \
    --include-package-data=torch \
    --nofollow-import-to=matplotlib \
    --nofollow-import-to=scipy \
    --nofollow-import-to=tkinter \
    --linux-icon=assets/icon.ico \
    --output-dir=build \
    main.py

if [ $? -ne 0 ]; then
    echo ""
    echo "========================================"
    echo "Build FAILED!"
    echo "Check the output above for errors."
    echo "========================================"
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
# WiPhoto Launcher Script

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Set library paths
export LD_LIBRARY_PATH="$SCRIPT_DIR:$LD_LIBRARY_PATH"

# Detect and set Qt platform
if [ -n "$WAYLAND_DISPLAY" ] && [ -z "$FORCE_X11" ]; then
    export QT_QPA_PLATFORM=wayland
else
    export QT_QPA_PLATFORM=xcb
fi

# Run WiPhoto
exec ./WiPhoto "$@"
LAUNCHER_EOF

chmod +x dist/WiPhoto_Linux/wiphoto.sh

# Create README
cat > dist/WiPhoto_Linux/README.txt << 'README_EOF'
WiPhoto v1.5.1 for Linux

Installation:
1. Ensure dependencies are installed:
   sudo apt install libgl1-mesa-glx libexiftool-perl libxcb-xinerama0 libxcb-cursor0

2. Run the launcher:
   ./wiphoto.sh

   Or run directly:
   ./WiPhoto

For more information:
https://github.com/widlily-corp/WiPhoto

Troubleshooting:
- If you see Qt platform errors, try: export QT_QPA_PLATFORM=xcb
- For Wayland, use: export QT_QPA_PLATFORM=wayland
- For X11 force: export FORCE_X11=1 && ./wiphoto.sh
README_EOF

# Create install script
cat > dist/WiPhoto_Linux/install.sh << 'INSTALL_EOF'
#!/bin/bash
# WiPhoto System-wide Installation Script

set -e

echo "Installing WiPhoto v1.5.1..."

# Check for sudo
if [ "$EUID" -ne 0 ]; then
    echo "This script requires sudo privileges"
    exec sudo "$0" "$@"
fi

# Install to /opt
INSTALL_DIR="/opt/wiphoto"
echo "Installing to $INSTALL_DIR..."

mkdir -p "$INSTALL_DIR"
cp -r ./* "$INSTALL_DIR/"
chmod +x "$INSTALL_DIR/WiPhoto"
chmod +x "$INSTALL_DIR/wiphoto.sh"

# Create desktop entry
cat > /usr/share/applications/wiphoto.desktop << DESKTOP_EOF
[Desktop Entry]
Type=Application
Name=WiPhoto
Comment=Professional Photo Manager
Exec=$INSTALL_DIR/wiphoto.sh %F
Icon=$INSTALL_DIR/assets/icon.ico
Terminal=false
Categories=Graphics;Photography;
MimeType=image/jpeg;image/png;image/bmp;image/gif;image/tiff;video/mp4;
DESKTOP_EOF

# Create symlink
ln -sf "$INSTALL_DIR/wiphoto.sh" /usr/local/bin/wiphoto

echo ""
echo "Installation complete!"
echo "Run 'wiphoto' from terminal or find WiPhoto in your applications menu"
INSTALL_EOF

chmod +x dist/WiPhoto_Linux/install.sh

echo ""
echo "========================================"
echo "Creating archive..."
echo "========================================"

# Create tarball
cd dist
tar -czf WiPhoto_v1.5.1_Linux.tar.gz WiPhoto_Linux/
cd ..

if [ -f "dist/WiPhoto_v1.5.1_Linux.tar.gz" ]; then
    echo ""
    echo "========================================"
    echo "Build completed successfully!"
    echo "========================================"
    echo ""
    echo "Executable: dist/WiPhoto_Linux/WiPhoto"
    echo "Archive: dist/WiPhoto_v1.5.1_Linux.tar.gz"
    echo ""
    ls -lh dist/WiPhoto_v1.5.1_Linux.tar.gz
    echo ""
    echo "Test the build:"
    echo "  cd dist/WiPhoto_Linux"
    echo "  ./wiphoto.sh"
    echo ""
else
    echo ""
    echo "========================================"
    echo "Archive creation FAILED!"
    echo "========================================"
    exit 1
fi
