#!/bin/bash

echo "=== KiCad LCSC Manager Plugin - Installation Script ==="
echo ""

# Detect KiCad version
KICAD_VERSIONS=("9.0" "8.0" "7.0" "6.0")
PLUGIN_DIR=""

for version in "${KICAD_VERSIONS[@]}"; do
    DIR="$HOME/Documents/KiCad/$version/scripting/plugins"
    if [ -d "$DIR" ]; then
        PLUGIN_DIR="$DIR"
        echo "Found KiCad $version at: $PLUGIN_DIR"
        break
    fi
done

if [ -z "$PLUGIN_DIR" ]; then
    echo "Error: Could not find KiCad plugins directory"
    echo "Please create it manually at:"
    echo "  ~/Documents/KiCad/[VERSION]/scripting/plugins/"
    exit 1
fi

# Create plugins directory if it doesn't exist
mkdir -p "$PLUGIN_DIR"

# Copy plugin files
echo ""
echo "Installing plugin..."
SOURCE_DIR="/Users/dkkang/dev/kicad-lcsc-manager/plugins/lcsc_manager"
TARGET_DIR="$PLUGIN_DIR/lcsc_manager"

if [ -d "$TARGET_DIR" ]; then
    echo "Removing existing installation..."
    rm -rf "$TARGET_DIR"
fi

cp -r "$SOURCE_DIR" "$TARGET_DIR"
echo "✓ Plugin files copied to: $TARGET_DIR"

# Install Python dependencies
echo ""
echo "Installing Python dependencies..."

# Try to find KiCad's Python
KICAD_PYTHON="/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3"

if [ -f "$KICAD_PYTHON" ]; then
    echo "Using KiCad's Python: $KICAD_PYTHON"
    "$KICAD_PYTHON" -m pip install --user requests pydantic KicadModTree Pillow cairosvg
else
    echo "Using system Python"
    pip3 install --user requests pydantic KicadModTree Pillow cairosvg
fi

echo ""
echo "=== Installation Complete! ==="
echo ""
echo "Next steps:"
echo "1. Restart KiCad completely"
echo "2. Open KiCad PCB Editor"
echo "3. Create or open a project (and SAVE it!)"
echo "4. Go to: Tools → External Plugins → LCSC Manager"
echo ""
echo "Test with LCSC part number: C2040"
echo ""
echo "Logs will be at: ~/.kicad/lcsc_manager/logs/lcsc_manager.log"
