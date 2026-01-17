#!/usr/bin/env python3
"""
Check LCSC Manager plugin status using KiCad Python environment
Run this with KiCad's Python interpreter
"""

import sys
import os

# Add KiCad Python modules to path
# KiCad 9.0 on macOS
kicad_python_paths = [
    "/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/lib/python3.11/site-packages",
    "/Applications/KiCad/KiCad.app/Contents/PlugIns",
]

for path in kicad_python_paths:
    if os.path.exists(path) and path not in sys.path:
        sys.path.insert(0, path)

print("=" * 70)
print("LCSC Manager Plugin Status Check")
print("=" * 70)
print()

# Try to import pcbnew
try:
    import pcbnew
    print("✓ pcbnew module imported successfully")
    print(f"  KiCad Version: {pcbnew.Version()}")
    print()
except ImportError as e:
    print(f"✗ Failed to import pcbnew: {e}")
    print("\nMake sure to run this with KiCad's Python:")
    print("  /Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3 check-plugin-cli.py")
    sys.exit(1)

# Check registered plugins
print("[1] Registered Action Plugins")
print("-" * 70)
try:
    plugins = pcbnew.GetActionPlugins()
    print(f"Total plugins registered: {len(plugins)}\n")

    if len(plugins) == 0:
        print("⚠ No plugins registered!")
        print("This could mean:")
        print("  - No plugins installed")
        print("  - Plugin registration failed")
        print("  - KiCad hasn't loaded plugins yet")
    else:
        lcsc_found = False
        for i, plugin in enumerate(plugins, 1):
            name = plugin.GetName()
            is_lcsc = "LCSC" in name or "lcsc" in name.lower()

            if is_lcsc:
                lcsc_found = True
                print(f"✓ PLUGIN #{i}: {name} (LCSC MANAGER FOUND!)")
            else:
                print(f"  Plugin #{i}: {name}")

            print(f"    Category: {plugin.GetCategoryName()}")
            print(f"    Description: {plugin.GetDescription()[:80]}...")
            print(f"    Show Toolbar: {plugin.GetShowToolbarButton()}")

            icon = plugin.GetIconFileName()
            if icon:
                icon_exists = os.path.exists(icon)
                print(f"    Icon: {icon}")
                print(f"    Icon Exists: {icon_exists}")
                if icon_exists:
                    print(f"    Icon Size: {os.path.getsize(icon)} bytes")
            else:
                print(f"    Icon: Not specified")
            print()

        if not lcsc_found:
            print("✗ LCSC Manager plugin NOT found in registered plugins")
            print()

except Exception as e:
    print(f"✗ Error checking plugins: {e}")
    import traceback
    traceback.print_exc()
    print()

# Check Python module import
print("[2] Python Module Import Test")
print("-" * 70)
try:
    import lcsc_manager
    print(f"✓ lcsc_manager module imported successfully")
    print(f"  Version: {getattr(lcsc_manager, '__version__', 'unknown')}")
    print(f"  File: {lcsc_manager.__file__}")
    print(f"  Author: {getattr(lcsc_manager, '__author__', 'unknown')}")
    print()

    # Try to import plugin class
    try:
        from lcsc_manager.plugin import LCSCManagerPlugin
        print(f"✓ LCSCManagerPlugin class imported successfully")

        # Create instance
        plugin_instance = LCSCManagerPlugin()
        print(f"✓ Plugin instance created")

        # Call defaults to initialize
        plugin_instance.defaults()
        print(f"✓ Plugin defaults() called")

        print(f"\n  Plugin properties after initialization:")
        print(f"    Name: {getattr(plugin_instance, 'name', 'N/A')}")
        print(f"    Category: {getattr(plugin_instance, 'category', 'N/A')}")
        print(f"    Description: {getattr(plugin_instance, 'description', 'N/A')}")
        print(f"    Show Toolbar: {getattr(plugin_instance, 'show_toolbar_button', 'N/A')}")
        print(f"    Icon File: {getattr(plugin_instance, 'icon_file_name', 'N/A')}")

        if hasattr(plugin_instance, 'icon_file_name'):
            icon_path = plugin_instance.icon_file_name
            if icon_path and os.path.exists(icon_path):
                print(f"    Icon Exists: ✓ ({os.path.getsize(icon_path)} bytes)")
            else:
                print(f"    Icon Exists: ✗")

    except Exception as e:
        print(f"✗ Error with plugin class: {e}")
        import traceback
        traceback.print_exc()

except ImportError as e:
    print(f"✗ Cannot import lcsc_manager: {e}")
    print("\nPossible reasons:")
    print("  - Plugin not installed")
    print("  - Plugin installed in wrong location")
    print("  - Missing dependencies")

print()

# Check installation directories
print("[3] Installation Directories")
print("-" * 70)

plugin_locations = [
    ("PCM 3rdparty", "~/Library/Application Support/kicad/9.0/3rdparty/plugins"),
    ("Manual scripting", "~/Documents/KiCad/9.0/scripting/plugins"),
]

for desc, path in plugin_locations:
    expanded_path = os.path.expanduser(path)
    exists = os.path.exists(expanded_path)

    print(f"\n{desc}:")
    print(f"  Path: {path}")
    print(f"  Exists: {('✓' if exists else '✗')}")

    if exists:
        # Check for direct lcsc_manager
        lcsc_dir = os.path.join(expanded_path, "lcsc_manager")
        if os.path.exists(lcsc_dir):
            print(f"  ✓ Found: lcsc_manager/")
            print(f"    Files:")
            for f in ['__init__.py', 'plugin.py', 'resources/icon.png']:
                fpath = os.path.join(lcsc_dir, f)
                exists_f = os.path.exists(fpath)
                size = f" ({os.path.getsize(fpath)} bytes)" if exists_f else ""
                print(f"      [{('✓' if exists_f else '✗')}] {f}{size}")

        # Check for PCM package
        pcm_package = "com.github.hulryung.kicad-lcsc-manager"
        pcm_dir = os.path.join(expanded_path, pcm_package)
        if os.path.exists(pcm_dir):
            print(f"  ✓ Found PCM package: {pcm_package}/")

            # Check metadata
            metadata_file = os.path.join(pcm_dir, "metadata.json")
            if os.path.exists(metadata_file):
                print(f"    ✓ metadata.json exists")
                try:
                    import json
                    with open(metadata_file) as f:
                        metadata = json.load(f)
                        version = metadata.get('versions', [{}])[0].get('version', 'unknown')
                        print(f"      Version: {version}")
                except:
                    pass

            # Check plugins subdirectory
            plugins_subdir = os.path.join(pcm_dir, "plugins")
            if os.path.exists(plugins_subdir):
                print(f"    ✓ plugins/ subdirectory exists")
                contents = os.listdir(plugins_subdir)
                print(f"      Contents: {contents}")

                # Check lcsc_manager inside plugins/
                lcsc_in_pcm = os.path.join(plugins_subdir, "lcsc_manager")
                if os.path.exists(lcsc_in_pcm):
                    print(f"      ✓ plugins/lcsc_manager/ found")
                    for f in ['__init__.py', 'plugin.py', 'resources/icon.png']:
                        fpath = os.path.join(lcsc_in_pcm, f)
                        exists_f = os.path.exists(fpath)
                        size = f" ({os.path.getsize(fpath)} bytes)" if exists_f else ""
                        print(f"        [{('✓' if exists_f else '✗')}] {f}{size}")

print()
print("=" * 70)
print("Diagnostic Complete")
print("=" * 70)
print()
print("Summary:")
print("  - Check if LCSC Manager appears in section [1]")
print("  - Check if module imports successfully in section [2]")
print("  - Check installation locations in section [3]")
print()
print("If plugin is installed but not registered:")
print("  - Check __init__.py has: if __name__ != '__main__':")
print("  - Check icon file exists at correct path")
print("  - Try restarting KiCad completely")
print("  - Check KiCad logs for errors")
print()
