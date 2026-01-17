#!/usr/bin/env python3
"""
Test LCSC Manager plugin in KiCad environment
Run with: ./kicad_python.sh test_plugin.py
"""

import sys
import os

print("=" * 70)
print("LCSC Manager Plugin Test")
print("=" * 70)
print()

# Add plugin to path - use development version
plugin_path = '/Users/dkkang/dev/kicad-lcsc-manager/plugins'
if os.path.exists(plugin_path):
    sys.path.insert(0, plugin_path)
    print(f"✓ Added plugin path (dev): {plugin_path}")
else:
    print(f"✗ Plugin path not found: {plugin_path}")
    sys.exit(1)

print()
print("1. Testing import...")
try:
    import lcsc_manager
    print(f"   ✓ Import successful! Version: {lcsc_manager.__version__}")
except Exception as e:
    print(f"   ✗ Import failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print()
print("2. Checking lib directory...")
lib_path = os.path.join(plugin_path, 'lcsc_manager', 'lib')
print(f"   Checking: {lib_path}")
if os.path.exists(lib_path):
    print(f"   ✓ lib/ directory exists")
    lib_contents = os.listdir(lib_path)
    if 'requests' in lib_contents:
        print(f"   ✓ requests library found")
    else:
        print(f"   ✗ requests library not found")
        print(f"   Contents: {lib_contents}")
else:
    print(f"   ✗ lib/ directory not found")

print()
print("3. Testing requests import...")
try:
    import requests
    print(f"   ✓ Requests imported: {requests.__version__}")
    print(f"   From: {requests.__file__}")
except Exception as e:
    print(f"   ✗ Requests import failed: {e}")

print()
print("4. Testing pcbnew import...")
try:
    import pcbnew
    print(f"   ✓ pcbnew imported successfully")
except Exception as e:
    print(f"   ✗ pcbnew import failed: {e}")
    print(f"   This is expected if KiCad is not running")

print()
print("5. Testing plugin registration...")
try:
    import pcbnew
    from lcsc_manager.plugin import LCSCManagerPlugin

    plugin = LCSCManagerPlugin()
    print(f"   Plugin name: {plugin.GetName()}")
    print(f"   Description: {plugin.GetDescription()}")
    print(f"   Show toolbar: {plugin.GetShowToolbarButton()}")

    # Test GetIconFileName with both light and dark modes
    icon_path_light = plugin.GetIconFileName(False)
    icon_path_dark = plugin.GetIconFileName(True)
    print(f"   Icon path (light): {icon_path_light}")
    print(f"   Icon path (dark): {icon_path_dark}")
    icon_path = icon_path_light

    if os.path.exists(icon_path):
        print(f"   ✓ Icon file exists")
    else:
        print(f"   ✗ Icon file not found")

    print()
    print("   ⚠ Skipping registration test")
    print("   (Registration only works when KiCad application is running)")

except Exception as e:
    print(f"   ✗ Registration test failed: {e}")
    import traceback
    traceback.print_exc()

print()
print("=" * 70)
print("Test Complete")
print("=" * 70)
