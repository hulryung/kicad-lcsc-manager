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

# Python dependencies info
echo ""
echo "════════════════════════════════════════════════════════════════"
echo "⚠️  WARNING: Python Dependencies"
echo "════════════════════════════════════════════════════════════════"
echo ""
echo "The following Python packages were installed for this plugin:"
echo "  - requests (used by many apps for HTTP requests)"
echo "  - pydantic (used for data validation)"
echo "  - Pillow (common image processing library)"
echo "  - cairosvg (SVG conversion library)"
echo ""
echo "These packages may be used by:"
echo "  - Other KiCad plugins"
echo "  - Other Python applications on your system"
echo "  - Development tools"
echo ""
echo "⚠️  DO NOT REMOVE unless you're certain they're not needed!"
echo ""
echo "If you want to remove them manually later, you can use:"
echo "  pip3 list --user  # To see installed packages"
echo "  pip3 uninstall <package-name>  # To remove specific packages"
echo ""
echo "════════════════════════════════════════════════════════════════"
echo ""
echo "We recommend KEEPING the Python packages installed."
echo ""

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
