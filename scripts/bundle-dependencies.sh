#!/bin/bash
# Bundle Python dependencies for LCSC Manager plugin

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
PLUGIN_DIR="$PROJECT_ROOT/plugins/lcsc_manager"
LIB_DIR="$PLUGIN_DIR/lib"

echo "=== Bundling Python Dependencies ==="
echo "Plugin directory: $PLUGIN_DIR"
echo "Library directory: $LIB_DIR"
echo ""

# Clean existing lib directory
if [ -d "$LIB_DIR" ]; then
    echo "Cleaning existing lib directory..."
    rm -rf "$LIB_DIR"
fi

# Create lib directory
mkdir -p "$LIB_DIR"

# Install requests and dependencies
echo "Installing requests and dependencies..."
python3 -m pip install \
    --target "$LIB_DIR" \
    --no-deps \
    --upgrade \
    requests certifi charset-normalizer idna urllib3

# Clean up unnecessary files
echo ""
echo "Cleaning up unnecessary files..."

# Remove __pycache__ directories
find "$LIB_DIR" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

# Remove .pyc files
find "$LIB_DIR" -type f -name "*.pyc" -delete

# Remove dist-info directories
find "$LIB_DIR" -type d -name "*.dist-info" -exec rm -rf {} + 2>/dev/null || true

# Remove .so files (binary extensions we don't need)
find "$LIB_DIR" -type f -name "*.so" -delete 2>/dev/null || true
find "$LIB_DIR" -type f -name "*.pyd" -delete 2>/dev/null || true

echo ""
echo "=== Bundling Complete ==="
echo ""
echo "Bundled packages:"
ls -1 "$LIB_DIR" | grep -v "^__" || true

echo ""
echo "Total size:"
du -sh "$LIB_DIR"
