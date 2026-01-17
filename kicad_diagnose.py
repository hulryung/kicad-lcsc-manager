"""
KiCad Plugin Diagnostic Script
Copy and paste this into KiCad Python Console to diagnose issues
"""

import sys
import os
from pathlib import Path

print("=" * 70)
print("LCSC Manager Plugin Diagnostic")
print("=" * 70)
print()

# Check Python version
print(f"Python version: {sys.version}")
print(f"Python executable: {sys.executable}")
print()

# Check sys.path
print("Python paths:")
for i, p in enumerate(sys.path[:10]):
    print(f"  [{i}] {p}")
print()

# Look for installed plugins
print("Looking for LCSC Manager installation...")
possible_locations = [
    Path.home() / "Documents/KiCad/9.0/3rdparty/plugins",
    Path.home() / "Documents/KiCad/9.0/scripting/plugins",
    Path.home() / "Library/Application Support/kicad/9.0/3rdparty/plugins",
    Path.home() / "Library/Application Support/kicad/9.0/scripting/plugins",
]

found_plugins = []
for base in possible_locations:
    if not base.exists():
        continue

    for plugin_dir in base.iterdir():
        if not plugin_dir.is_dir():
            continue

        # Check for lcsc_manager
        init_file = plugin_dir / "plugins/lcsc_manager/__init__.py"
        if init_file.exists():
            found_plugins.append(plugin_dir)
            print(f"\n✓ Found: {plugin_dir}")

            # Read version
            try:
                with open(init_file) as f:
                    for line in f:
                        if '__version__' in line:
                            print(f"  Version: {line.strip()}")
                            break
            except Exception as e:
                print(f"  Error reading version: {e}")

            # Check for lib directory
            lib_dir = plugin_dir / "plugins/lcsc_manager/lib"
            if lib_dir.exists():
                print(f"  ✓ lib/ directory exists")

                # Check for requests
                requests_dir = lib_dir / "requests"
                if requests_dir.exists():
                    print(f"  ✓ requests library bundled")
                else:
                    print(f"  ✗ requests library NOT found in lib/")
            else:
                print(f"  ✗ lib/ directory NOT found")

            # Try to import
            print(f"\n  Testing import...")
            plugin_path = str(plugin_dir / "plugins")
            if plugin_path not in sys.path:
                sys.path.insert(0, plugin_path)

            try:
                import lcsc_manager
                print(f"  ✓ Import successful!")
                print(f"  ✓ Version: {lcsc_manager.__version__}")
            except Exception as e:
                print(f"  ✗ Import failed: {e}")
                import traceback
                traceback.print_exc()

if not found_plugins:
    print("\n✗ No LCSC Manager installation found!")
    print("\nSearched locations:")
    for loc in possible_locations:
        print(f"  - {loc}")

print()
print("=" * 70)
print("Diagnostic complete")
print("=" * 70)
