#!/usr/bin/env python3
"""
Verification script to test if the LCSC Manager plugin can be loaded properly
Run this with KiCad's Python: ./kicad_python.sh verify_plugin.py
"""
import sys
import os

print("=== LCSC Manager Plugin Verification ===\n")

# Check plugin installation
plugin_dir = os.path.expanduser("~/Documents/KiCad/9.0/3rdparty/plugins/com_github_hulryung_kicad-lcsc-manager")
print(f"1. Checking plugin directory: {plugin_dir}")
if os.path.exists(plugin_dir):
    print("   ✓ Plugin directory exists")
else:
    print("   ✗ Plugin directory NOT found")
    sys.exit(1)

# Check key files
required_files = [
    "__init__.py",
    "plugin.py",
    "metadata.json",
    "lib/requests/__init__.py"
]

print("\n2. Checking required files:")
for file in required_files:
    file_path = os.path.join(plugin_dir, file)
    if os.path.exists(file_path):
        print(f"   ✓ {file}")
    else:
        print(f"   ✗ {file} MISSING")

# Check Python path
print(f"\n3. Python path:")
for path in sys.path[:5]:
    print(f"   - {path}")

# Try importing the plugin
print("\n4. Attempting to import plugin module:")
# Need to import as a package, so add parent directory to path
plugins_dir = os.path.dirname(plugin_dir)
sys.path.insert(0, plugins_dir)
package_name = os.path.basename(plugin_dir)

try:
    # Import as package to support relative imports
    import importlib
    lcsc_module = importlib.import_module(package_name)
    print(f"   ✓ Package imported successfully")
    print(f"   Version: {lcsc_module.__version__}")
except Exception as e:
    print(f"   ✗ Failed to import package: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

try:
    LCSCManagerPlugin = getattr(lcsc_module, 'LCSCManagerPlugin', None)
    if LCSCManagerPlugin is None:
        # Try importing from submodule
        plugin_module = importlib.import_module(f"{package_name}.plugin")
        LCSCManagerPlugin = plugin_module.LCSCManagerPlugin
    print(f"   ✓ LCSCManagerPlugin class found")
except Exception as e:
    print(f"   ✗ Failed to get LCSCManagerPlugin class: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Try creating plugin instance
print("\n5. Attempting to create plugin instance:")
try:
    plugin = LCSCManagerPlugin()
    print(f"   ✓ Plugin instance created")
    print(f"   Name: {plugin.name}")
    print(f"   Description: {plugin.description}")
    print(f"   Show toolbar: {plugin.show_toolbar_button}")

    # Test GetIconFileName
    print("\n6. Testing GetIconFileName:")
    icon_light = plugin.GetIconFileName(False)
    icon_dark = plugin.GetIconFileName(True)
    print(f"   Light mode icon: {icon_light}")
    print(f"   Dark mode icon: {icon_dark}")

    if os.path.exists(icon_light):
        print(f"   ✓ Icon file exists")
    else:
        print(f"   ✗ Icon file NOT found")

except Exception as e:
    print(f"   ✗ Failed to create plugin instance: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n=== All checks passed! ===")
print("\nIf toolbar icon still doesn't appear:")
print("1. Make sure KiCad is completely closed")
print("2. Restart KiCad")
print("3. Open PCB Editor")
print("4. Check the toolbar for the LCSC Manager icon")
