#!/bin/bash
# Build script for Linux

set -e

echo "===================================="
echo "WiPhoto Linux Build Script"
echo "===================================="

echo ""
echo "Step 1: Checking Python environment..."
python3 --version

echo ""
echo "Step 2: Creating virtual environment..."
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi
source .venv/bin/activate

echo ""
echo "Step 3: Installing dependencies..."
pip install -r requirements.txt

echo ""
echo "Step 4: Creating release directory..."
RELEASE_DIR="WiPhoto_v1.5.0_Linux"
rm -rf "$RELEASE_DIR"
mkdir -p "$RELEASE_DIR"

echo ""
echo "Step 5: Copying application files..."
cp -r *.py "$RELEASE_DIR/"
cp -r assets "$RELEASE_DIR/"
cp -r controllers "$RELEASE_DIR/"
cp -r core "$RELEASE_DIR/"
cp -r models "$RELEASE_DIR/"
cp -r views "$RELEASE_DIR/"
cp liquid_glass.qss "$RELEASE_DIR/"
cp requirements.txt "$RELEASE_DIR/"
cp README.md "$RELEASE_DIR/"
cp README_RU.md "$RELEASE_DIR/"

echo ""
echo "Step 6: Creating launch script..."
cat > "$RELEASE_DIR/wiphoto.sh" << 'EOF'
#!/bin/bash
# WiPhoto launcher for Linux

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Check if running in virtual environment
if [ -z "$VIRTUAL_ENV" ]; then
    if [ -d ".venv" ]; then
        source .venv/bin/activate
    fi
fi

python3 main.py "$@"
EOF

chmod +x "$RELEASE_DIR/wiphoto.sh"

echo ""
echo "Step 7: Creating archive..."
tar -czf "${RELEASE_DIR}.tar.gz" "$RELEASE_DIR"

echo ""
echo "===================================="
echo "Build completed successfully!"
echo "Release: ${RELEASE_DIR}.tar.gz"
echo "===================================="
echo ""
echo "Installation instructions:"
echo "1. Extract: tar -xzf ${RELEASE_DIR}.tar.gz"
echo "2. Navigate: cd $RELEASE_DIR"
echo "3. Install deps: pip install -r requirements.txt"
echo "4. Install ExifTool: sudo apt install libexiftool-perl"
echo "5. Run: ./wiphoto.sh"
