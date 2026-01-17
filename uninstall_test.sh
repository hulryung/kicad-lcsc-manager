#!/bin/bash

echo "=== KiCad LCSC Manager Plugin - Uninstall Script ==="
echo ""

# Detect KiCad version
KICAD_VERSIONS=("9.0" "8.0" "7.0" "6.0")
PLUGIN_DIR=""

for version in "${KICAD_VERSIONS[@]}"; do
    DIR="$HOME/Documents/KiCad/$version/scripting/plugins"
    if [ -d "$DIR/lcsc_manager" ]; then
        PLUGIN_DIR="$DIR"
        echo "Found LCSC Manager plugin for KiCad $version at: $PLUGIN_DIR"
        break
    fi
done

if [ -z "$PLUGIN_DIR" ]; then
    echo "LCSC Manager plugin not found in any KiCad version"
    echo "Checked locations:"
    for version in "${KICAD_VERSIONS[@]}"; do
        echo "  - ~/Documents/KiCad/$version/scripting/plugins/lcsc_manager"
    done
    exit 0
fi

# Confirm uninstall
echo ""
echo "This will remove the LCSC Manager plugin from:"
echo "  $PLUGIN_DIR/lcsc_manager"
echo ""
read -p "Continue? (y/N) " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Uninstall cancelled."
    exit 0
fi

# Remove plugin
echo ""
echo "Removing plugin..."
TARGET_DIR="$PLUGIN_DIR/lcsc_manager"

if [ -d "$TARGET_DIR" ]; then
    rm -rf "$TARGET_DIR"
    echo "✓ Plugin removed from: $TARGET_DIR"
else
    echo "Plugin directory not found: $TARGET_DIR"
fi

# Ask about Python dependencies
echo ""
echo "Python dependencies (requests, pydantic, Pillow, cairosvg) were installed."
echo "These packages may be used by other plugins or applications."
echo ""
read -p "Remove Python dependencies? (y/N) " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo ""
    echo "Removing Python dependencies..."

    # Try to find KiCad's Python
    KICAD_PYTHON="/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3"

    if [ -f "$KICAD_PYTHON" ]; then
        echo "Using KiCad's Python: $KICAD_PYTHON"
        "$KICAD_PYTHON" -m pip uninstall -y requests pydantic Pillow cairosvg 2>/dev/null || echo "Some packages may not have been installed"
    else
        echo "Using system Python"
        pip3 uninstall -y requests pydantic Pillow cairosvg 2>/dev/null || echo "Some packages may not have been installed"
    fi

    echo "✓ Python dependencies removed (if they were installed)"
fi

# Clean up config and logs (optional)
echo ""
echo "Configuration and logs are stored in:"
echo "  ~/.kicad/lcsc_manager/"
echo ""
read -p "Remove configuration and logs? (y/N) " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    if [ -d "$HOME/.kicad/lcsc_manager" ]; then
        rm -rf "$HOME/.kicad/lcsc_manager"
        echo "✓ Configuration and logs removed"
    else
        echo "Configuration directory not found"
    fi
fi

echo ""
echo "=== Uninstall Complete! ==="
echo ""
echo "The plugin has been removed. Restart KiCad to complete the uninstall."
echo ""
