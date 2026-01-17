#!/usr/bin/env python3
"""
Quick diagnostic script for LCSC Manager plugin
Run this in KiCad Scripting Console
"""

import pcbnew
import sys
import os

print("=" * 70)
print("LCSC Manager Plugin Diagnostic")
print("=" * 70)

# 1. Check registered plugins
print("\n[1] Checking registered Action Plugins...")
plugins = pcbnew.GetActionPlugins()
print(f"    Total registered plugins: {len(plugins)}")

lcsc_found = False
for p in plugins:
    name = p.GetName()
    if "LCSC" in name or "lcsc" in name.lower():
        lcsc_found = True
        print(f"\n    ✓ LCSC Manager IS REGISTERED!")
        print(f"      Name: {name}")
        print(f"      Description: {p.GetDescription()}")
        print(f"      Category: {p.GetCategoryName()}")
        print(f"      Show Toolbar: {p.GetShowToolbarButton()}")
        icon = p.GetIconFileName()
        print(f"      Icon: {icon}")
        if icon:
            print(f"      Icon exists: {os.path.exists(icon)}")
            if os.path.exists(icon):
                print(f"      Icon size: {os.path.getsize(icon)} bytes")
        break

if not lcsc_found:
    print(f"\n    ✗ LCSC Manager NOT REGISTERED")
    print(f"\n    All registered plugins:")
    for p in plugins:
        print(f"      - {p.GetName()} ({p.GetCategoryName()})")

# 2. Check module import
print("\n[2] Checking Python module import...")
try:
    import lcsc_manager
    print(f"    ✓ lcsc_manager module can be imported")
    print(f"      Version: {getattr(lcsc_manager, '__version__', 'unknown')}")
    print(f"      File: {lcsc_manager.__file__}")
except ImportError as e:
    print(f"    ✗ Cannot import lcsc_manager: {e}")
except Exception as e:
    print(f"    ✗ Error importing: {e}")

# 3. Check plugin class
print("\n[3] Checking plugin class...")
try:
    from lcsc_manager.plugin import LCSCManagerPlugin
    print(f"    ✓ LCSCManagerPlugin class can be imported")

    # Try to create instance
    try:
        instance = LCSCManagerPlugin()
        print(f"    ✓ Plugin instance created")
        # Check if defaults() was called
        if hasattr(instance, 'name'):
            print(f"      Name: {instance.name}")
        if hasattr(instance, 'description'):
            print(f"      Description: {instance.description}")
        if hasattr(instance, 'show_toolbar_button'):
            print(f"      Show toolbar: {instance.show_toolbar_button}")
        if hasattr(instance, 'icon_file_name'):
            print(f"      Icon file: {instance.icon_file_name}")
    except Exception as e:
        print(f"    ✗ Error creating instance: {e}")
        import traceback
        traceback.print_exc()

except ImportError as e:
    print(f"    ✗ Cannot import plugin class: {e}")

# 4. Check plugin directories
print("\n[4] Checking plugin installation directories...")

plugin_dirs = [
    ("Manual install", "~/Documents/KiCad/9.0/scripting/plugins"),
    ("PCM install", "~/Library/Application Support/kicad/9.0/3rdparty/plugins"),
]

for desc, d in plugin_dirs:
    path = os.path.expanduser(d)
    exists = os.path.exists(path)
    print(f"\n    [{('✓' if exists else '✗')}] {desc}: {d}")

    if exists:
        # Check for direct lcsc_manager directory
        lcsc_dir = os.path.join(path, "lcsc_manager")
        if os.path.exists(lcsc_dir):
            print(f"        ✓ lcsc_manager/ directory found")
            files = ['__init__.py', 'plugin.py', 'resources/icon.png']
            for f in files:
                fpath = os.path.join(lcsc_dir, f)
                print(f"          [{('✓' if os.path.exists(fpath) else '✗')}] {f}")

        # Check for PCM package directory
        pcm_id = "com.github.hulryung.kicad-lcsc-manager"
        pcm_dir = os.path.join(path, pcm_id)
        if os.path.exists(pcm_dir):
            print(f"        ✓ PCM package directory found: {pcm_id}")

            # Check metadata
            metadata_path = os.path.join(pcm_dir, "metadata.json")
            if os.path.exists(metadata_path):
                print(f"          ✓ metadata.json found")
                import json
                try:
                    with open(metadata_path) as f:
                        metadata = json.load(f)
                        print(f"            Version: {metadata.get('versions', [{}])[0].get('version', 'unknown')}")
                except:
                    pass

            # Check plugins subdirectory
            plugins_subdir = os.path.join(pcm_dir, "plugins")
            if os.path.exists(plugins_subdir):
                print(f"          ✓ plugins/ subdirectory found")
                contents = os.listdir(plugins_subdir)
                print(f"            Contents: {contents}")

                # Check lcsc_manager inside
                lcsc_in_pcm = os.path.join(plugins_subdir, "lcsc_manager")
                if os.path.exists(lcsc_in_pcm):
                    print(f"            ✓ plugins/lcsc_manager/ found")
                    files = ['__init__.py', 'plugin.py', 'resources/icon.png']
                    for f in files:
                        fpath = os.path.join(lcsc_in_pcm, f)
                        print(f"              [{('✓' if os.path.exists(fpath) else '✗')}] {f}")

# 5. Check Python path
print("\n[5] Checking Python sys.path...")
print(f"    Python version: {sys.version}")
print(f"    Total paths: {len(sys.path)}")
lcsc_paths = [p for p in sys.path if 'lcsc' in p.lower() or 'kicad' in p.lower()]
if lcsc_paths:
    print(f"    LCSC/KiCad related paths:")
    for p in lcsc_paths:
        print(f"      - {p}")

print("\n" + "=" * 70)
print("Diagnostic Complete!")
print("=" * 70)
print("\nTo run this diagnostic:")
print("1. Open KiCad PCB Editor")
print("2. Tools → Scripting Console")
print("3. Copy and paste this entire script")
print("=" * 70)
