#!/usr/bin/env python3
"""
Check LCSC Manager plugin installation status
"""
import os
import sys
from pathlib import Path

# Possible KiCad plugin locations
possible_paths = [
    Path.home() / "Library/Application Support/kicad/9.0/3rdparty/plugins",
    Path.home() / "Library/Application Support/kicad/8.0/3rdparty/plugins",
    Path.home() / "Documents/KiCad/9.0/3rdparty/plugins",
    Path.home() / "Documents/KiCad/8.0/3rdparty/plugins",
]

print("=== LCSC Manager Installation Check ===\n")

found = False
for base_path in possible_paths:
    if not base_path.exists():
        continue

    # Look for lcsc_manager plugin
    for plugin_dir in base_path.iterdir():
        if not plugin_dir.is_dir():
            continue

        init_file = plugin_dir / "plugins/lcsc_manager/__init__.py"
        dialog_file = plugin_dir / "plugins/lcsc_manager/dialog_search.py"

        if init_file.exists():
            found = True
            print(f"✓ Found installation: {plugin_dir}")

            # Check version
            try:
                with open(init_file, 'r') as f:
                    for line in f:
                        if '__version__' in line:
                            print(f"  Version: {line.strip()}")
                            break
            except Exception as e:
                print(f"  Error reading version: {e}")

            # Check if dialog_search.py has Specifications tab
            if dialog_file.exists():
                try:
                    with open(dialog_file, 'r') as f:
                        content = f.read()
                        if 'Specifications' in content:
                            print(f"  ✓ Specifications tab code found")
                            # Count occurrences
                            count = content.count('Specifications')
                            print(f"    (appears {count} times in code)")
                        else:
                            print(f"  ✗ Specifications tab code NOT found")
                except Exception as e:
                    print(f"  Error reading dialog_search.py: {e}")
            else:
                print(f"  ✗ dialog_search.py not found")

            print()

if not found:
    print("✗ No LCSC Manager installation found in standard locations")
    print("\nSearched locations:")
    for path in possible_paths:
        print(f"  - {path}")
    print("\nPlease check your KiCad plugin installation manually.")

print("\n=== Additional Checks ===")

# Check if there are any .pyc files that might be cached
print("\nLooking for cached .pyc files...")
for base_path in possible_paths:
    if not base_path.exists():
        continue

    for plugin_dir in base_path.iterdir():
        pycache = plugin_dir / "plugins/lcsc_manager/__pycache__"
        if pycache.exists():
            print(f"Found cache: {pycache}")
            print("  → Consider deleting this cache and restarting KiCad")
