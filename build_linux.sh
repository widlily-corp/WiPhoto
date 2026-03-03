#!/bin/bash
# WiPhoto Linux Build Script with PyInstaller

set -e

echo "========================================"
echo "WiPhoto Linux Build Script"
echo "========================================"
echo ""

# Activate virtual environment if exists
if [ -d ".venv" ]; then
    echo "Activating virtual environment..."
    source .venv/bin/activate
else
    echo "Virtual environment not found. Creating..."
    python3 -m venv .venv
    source .venv/bin/activate
    echo "Installing dependencies..."
    pip install -r requirements.txt
    pip install pyinstaller
fi

# Clean previous builds
echo "Cleaning previous builds..."
rm -rf build
rm -rf dist/WiPhoto

# Build with PyInstaller
echo ""
echo "Building WiPhoto..."
pyinstaller WiPhoto_Linux.spec

# Check if build was successful
if [ -f "dist/WiPhoto/WiPhoto" ]; then
    echo ""
    echo "========================================"
    echo "Build completed successfully!"
    echo "Executable location: dist/WiPhoto/WiPhoto"
    echo "========================================"

    # Make executable
    chmod +x dist/WiPhoto/WiPhoto

    # Create launcher script
    echo ""
    echo "Creating launcher script..."
    cat > dist/WiPhoto/wiphoto.sh << 'EOF'
#!/bin/bash
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"
./WiPhoto "$@"
EOF
    chmod +x dist/WiPhoto/wiphoto.sh

    # Create archive
    echo "Creating distribution archive..."
    cd dist
    tar -czf WiPhoto_v1.5.0_Linux.tar.gz WiPhoto/
    cd ..

    echo ""
    echo "Distribution archive: dist/WiPhoto_v1.5.0_Linux.tar.gz"
    echo ""
    echo "You can now run: ./dist/WiPhoto/WiPhoto"
    echo "or use the launcher: ./dist/WiPhoto/wiphoto.sh"
else
    echo ""
    echo "========================================"
    echo "Build FAILED!"
    echo "Check the output above for errors."
    echo "========================================"
    exit 1
fi
