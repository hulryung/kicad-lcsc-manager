#!/bin/bash
# Complete cleanup script for LCSC Manager plugin

echo "=== LCSC Manager Complete Cleanup ==="
echo ""

# Find all possible locations
LOCATIONS=(
    "$HOME/Documents/KiCad/9.0/3rdparty/plugins/com_github_hulryung_kicad-lcsc-manager"
    "$HOME/Documents/KiCad/9.0/scripting/plugins/lcsc_manager"
    "$HOME/Library/Application Support/kicad/9.0/3rdparty/plugins/com_github_hulryung_kicad-lcsc-manager"
    "$HOME/Library/Application Support/kicad/9.0/scripting/plugins/lcsc_manager"
    "$HOME/Documents/KiCad/8.0/3rdparty/plugins/com_github_hulryung_kicad-lcsc-manager"
    "$HOME/Documents/KiCad/8.0/scripting/plugins/lcsc_manager"
)

echo "Step 1: Removing plugin directories..."
for location in "${LOCATIONS[@]}"; do
    if [ -d "$location" ]; then
        echo "  Removing: $location"
        rm -rf "$location"
    fi
done

echo ""
echo "Step 2: Cleaning Python cache files..."
find "$HOME/Documents/KiCad" -name "__pycache__" -type d 2>/dev/null | while read cache_dir; do
    if [[ "$cache_dir" == *"lcsc"* ]]; then
        echo "  Removing cache: $cache_dir"
        rm -rf "$cache_dir"
    fi
done

find "$HOME/Library/Application Support/kicad" -name "__pycache__" -type d 2>/dev/null | while read cache_dir; do
    if [[ "$cache_dir" == *"lcsc"* ]]; then
        echo "  Removing cache: $cache_dir"
        rm -rf "$cache_dir"
    fi
done

echo ""
echo "Step 3: Cleaning .pyc files..."
find "$HOME/Documents/KiCad" -name "*.pyc" -type f 2>/dev/null | while read pyc_file; do
    if [[ "$pyc_file" == *"lcsc"* ]]; then
        echo "  Removing: $pyc_file"
        rm -f "$pyc_file"
    fi
done

echo ""
echo "Step 4: Verifying cleanup..."
remaining=$(mdfind -name "lcsc_manager" 2>/dev/null | grep -E "(Documents/KiCad|Library/Application Support/kicad)" | grep -v "/dev/" | wc -l)

if [ "$remaining" -eq 0 ]; then
    echo "  ✓ All LCSC Manager files removed"
else
    echo "  Warning: Some files may remain:"
    mdfind -name "lcsc_manager" 2>/dev/null | grep -E "(Documents/KiCad|Library/Application Support/kicad)" | grep -v "/dev/"
fi

echo ""
echo "=== Cleanup Complete ==="
echo ""
echo "Next steps:"
echo "1. Restart KiCad completely (quit and relaunch)"
echo "2. Open Plugin and Content Manager"
echo "3. Go to 'Manage' -> 'Preferences'"
echo "4. Add custom repository URL:"
echo "   https://raw.githubusercontent.com/hulryung/kicad-lcsc-manager/main/repository.json"
echo "5. Install LCSC Manager from the repository"
echo "6. Restart KiCad again"
echo ""
