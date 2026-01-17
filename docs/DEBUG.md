# KiCad Plugin Debugging Guide

This guide helps you debug and troubleshoot KiCad plugin installation issues.

## Method 1: KiCad Python Scripting Console

### Open Python Console

1. Open KiCad PCB Editor
2. Go to **Tools → Scripting Console**
3. A Python console window will appear

### Check Installed Plugins

In the scripting console, run:

```python
import pcbnew

# Get all registered action plugins
plugins = pcbnew.GetActionPlugins()

print(f"Total plugins registered: {len(plugins)}")
print("\nRegistered plugins:")
for plugin in plugins:
    print(f"  - {plugin.GetName()} (Category: {plugin.GetCategoryName()})")
    print(f"    Show toolbar: {plugin.GetShowToolbarButton()}")
    print(f"    Icon: {plugin.GetIconFileName()}")
    print()
```

### Check LCSC Manager Specifically

```python
import pcbnew

plugins = pcbnew.GetActionPlugins()
lcsc_plugin = None

for plugin in plugins:
    if "LCSC" in plugin.GetName():
        lcsc_plugin = plugin
        break

if lcsc_plugin:
    print("✓ LCSC Manager is registered!")
    print(f"  Name: {lcsc_plugin.GetName()}")
    print(f"  Description: {lcsc_plugin.GetDescription()}")
    print(f"  Category: {lcsc_plugin.GetCategoryName()}")
    print(f"  Show Toolbar: {lcsc_plugin.GetShowToolbarButton()}")
    print(f"  Icon File: {lcsc_plugin.GetIconFileName()}")
else:
    print("✗ LCSC Manager is NOT registered")
    print("\nAll registered plugins:")
    for p in plugins:
        print(f"  - {p.GetName()}")
```

### Check Plugin Import

Test if the plugin can be imported:

```python
import sys
import os

# Check if plugin directory is in Python path
plugin_paths = [p for p in sys.path if 'lcsc_manager' in p.lower()]
print(f"LCSC Manager paths in sys.path: {plugin_paths}")

# Try to import the plugin
try:
    import lcsc_manager
    print(f"✓ lcsc_manager module imported successfully")
    print(f"  Version: {lcsc_manager.__version__}")
    print(f"  Location: {lcsc_manager.__file__}")
except ImportError as e:
    print(f"✗ Failed to import lcsc_manager: {e}")

# Try to import the plugin class
try:
    from lcsc_manager.plugin import LCSCManagerPlugin
    print(f"✓ LCSCManagerPlugin class imported successfully")

    # Try to create an instance
    plugin = LCSCManagerPlugin()
    print(f"✓ LCSCManagerPlugin instance created")
    print(f"  Name: {plugin.name}")
    print(f"  Description: {plugin.description}")
except Exception as e:
    print(f"✗ Failed to import/create LCSCManagerPlugin: {e}")
    import traceback
    traceback.print_exc()
```

## Method 2: Check Plugin Directory

### Find Plugin Installation Location

```python
import pcbnew
import os

# Get KiCad configuration paths
config_path = pcbnew.GetSettingsManager().GetUserSettingsPath()
print(f"KiCad config path: {config_path}")

# Common plugin locations
plugin_dirs = [
    os.path.expanduser("~/Documents/KiCad/9.0/scripting/plugins"),
    os.path.expanduser("~/Library/Application Support/kicad/9.0/3rdparty/plugins"),
    os.path.join(config_path, "scripting/plugins"),
    os.path.join(config_path, "3rdparty/plugins"),
]

print("\nChecking plugin directories:")
for pdir in plugin_dirs:
    exists = os.path.exists(pdir)
    print(f"  [{('✓' if exists else '✗')}] {pdir}")
    if exists:
        try:
            contents = os.listdir(pdir)
            if contents:
                print(f"      Contents: {contents}")
        except:
            pass
```

### Verify LCSC Manager Installation

```python
import os

# Check both possible locations
locations = [
    os.path.expanduser("~/Documents/KiCad/9.0/scripting/plugins/lcsc_manager"),
    os.path.expanduser("~/Library/Application Support/kicad/9.0/3rdparty/plugins/com.github.hulryung.kicad-lcsc-manager"),
]

for loc in locations:
    print(f"\nChecking: {loc}")
    if os.path.exists(loc):
        print(f"  ✓ Directory exists")

        # Check for key files
        key_files = ['__init__.py', 'plugin.py', 'resources/icon.png']
        for f in key_files:
            fpath = os.path.join(loc, f)
            exists = os.path.exists(fpath)
            print(f"  [{('✓' if exists else '✗')}] {f}")
    else:
        print(f"  ✗ Directory does not exist")
```

## Method 3: Check KiCad Logs

### macOS Log Location

```bash
# In Terminal
tail -f ~/Library/Logs/kicad/kicad.log

# Or view recent errors
grep -i "lcsc\|plugin\|error" ~/Library/Logs/kicad/kicad.log | tail -50
```

### Check Console Output

```bash
# Run KiCad from terminal to see console output
/Applications/KiCad/KiCad.app/Contents/MacOS/kicad

# Or for PCB Editor directly
/Applications/KiCad/KiCad.app/Contents/MacOS/pcbnew
```

## Method 4: Manual Plugin Test

Create a test script to manually register the plugin:

```python
import pcbnew
import sys
import os

# Add plugin path if needed
plugin_path = os.path.expanduser("~/Documents/KiCad/9.0/scripting/plugins")
if plugin_path not in sys.path:
    sys.path.insert(0, plugin_path)

print(f"Python path: {sys.path[:3]}...")

try:
    # Import and register plugin manually
    from lcsc_manager.plugin import LCSCManagerPlugin

    plugin = LCSCManagerPlugin()
    print(f"Created plugin instance: {plugin.name}")

    # Register it
    plugin.register()
    print("✓ Plugin registered successfully")

    # Verify registration
    plugins = pcbnew.GetActionPlugins()
    for p in plugins:
        if "LCSC" in p.GetName():
            print(f"✓ Found in registered plugins: {p.GetName()}")
            break
    else:
        print("✗ Not found in registered plugins after manual registration")

except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()
```

## Method 5: Check PCM Installation Status

### Via Scripting Console

```python
import pcbnew
import os
import json

# PCM plugin installation directory (KiCad 9.0)
pcm_plugin_dir = os.path.expanduser("~/Library/Application Support/kicad/9.0/3rdparty/plugins")

print(f"PCM Plugin directory: {pcm_plugin_dir}")
print(f"Exists: {os.path.exists(pcm_plugin_dir)}")

if os.path.exists(pcm_plugin_dir):
    plugins = os.listdir(pcm_plugin_dir)
    print(f"\nInstalled PCM plugins ({len(plugins)}):")
    for p in plugins:
        pdir = os.path.join(pcm_plugin_dir, p)
        if os.path.isdir(pdir):
            # Check for metadata
            metadata_file = os.path.join(pdir, "metadata.json")
            if os.path.exists(metadata_file):
                with open(metadata_file) as f:
                    metadata = json.load(f)
                    print(f"  - {metadata.get('name', p)} ({p})")
            else:
                print(f"  - {p} (no metadata)")

            # Check for plugins subdirectory
            plugins_subdir = os.path.join(pdir, "plugins")
            if os.path.exists(plugins_subdir):
                print(f"    plugins/: {os.listdir(plugins_subdir)}")
```

## Common Issues and Solutions

### Issue 1: Plugin Not Registered

**Symptoms**: Plugin doesn't appear in Tools menu or toolbar

**Debug**:
```python
import pcbnew
plugins = pcbnew.GetActionPlugins()
print([p.GetName() for p in plugins])
```

**Solutions**:
- Check if `__init__.py` has `if __name__ != "__main__"` guard
- Verify plugin imports without errors
- Check icon file exists at correct path

### Issue 2: Icon Not Showing

**Symptoms**: Plugin appears in menu but no toolbar icon

**Debug**:
```python
import pcbnew
for p in pcbnew.GetActionPlugins():
    if "LCSC" in p.GetName():
        print(f"Icon file: {p.GetIconFileName()}")
        print(f"Icon exists: {os.path.exists(p.GetIconFileName())}")
```

**Solutions**:
- Verify icon exists at `plugins/lcsc_manager/resources/icon.png`
- Check icon file permissions
- Ensure `show_toolbar_button = True` in plugin code

### Issue 3: Import Errors

**Symptoms**: Errors in KiCad log about missing modules

**Debug**:
```python
import sys
try:
    import lcsc_manager
except ImportError as e:
    print(f"Import error: {e}")
    print(f"sys.path: {sys.path}")
```

**Solutions**:
- Install missing Python dependencies
- Check Python version compatibility
- Verify all plugin files are present

### Issue 4: Wrong Installation Directory

**Symptoms**: Files copied but plugin not loading

**Debug**: Check all possible plugin locations

**Solutions**:
- For PCM installs: Should be in `~/Library/Application Support/kicad/9.0/3rdparty/plugins/`
- For manual installs: Should be in `~/Documents/KiCad/9.0/scripting/plugins/`
- Package should extract to create `plugins/lcsc_manager/` subdirectory

## Quick Diagnostic Script

Save this as `check_lcsc_plugin.py` and run in KiCad scripting console:

```python
#!/usr/bin/env python3
"""Quick diagnostic for LCSC Manager plugin"""

import pcbnew
import sys
import os

print("=" * 60)
print("LCSC Manager Plugin Diagnostic")
print("=" * 60)

# 1. Check registered plugins
print("\n1. Checking registered plugins...")
plugins = pcbnew.GetActionPlugins()
print(f"   Total plugins: {len(plugins)}")

lcsc_found = False
for p in plugins:
    if "LCSC" in p.GetName():
        lcsc_found = True
        print(f"   ✓ LCSC Manager IS registered")
        print(f"     Name: {p.GetName()}")
        print(f"     Category: {p.GetCategoryName()}")
        print(f"     Toolbar: {p.GetShowToolbarButton()}")
        print(f"     Icon: {p.GetIconFileName()}")
        if p.GetIconFileName():
            print(f"     Icon exists: {os.path.exists(p.GetIconFileName())}")
        break

if not lcsc_found:
    print(f"   ✗ LCSC Manager NOT registered")
    print(f"   Registered plugins:")
    for p in plugins:
        print(f"     - {p.GetName()}")

# 2. Check import
print("\n2. Checking module import...")
try:
    import lcsc_manager
    print(f"   ✓ Module imported")
    print(f"     Version: {lcsc_manager.__version__}")
    print(f"     Location: {lcsc_manager.__file__}")
except ImportError as e:
    print(f"   ✗ Import failed: {e}")

# 3. Check plugin directories
print("\n3. Checking plugin directories...")
dirs = [
    "~/Documents/KiCad/9.0/scripting/plugins",
    "~/Library/Application Support/kicad/9.0/3rdparty/plugins",
]

for d in dirs:
    path = os.path.expanduser(d)
    exists = os.path.exists(path)
    print(f"   [{('✓' if exists else '✗')}] {d}")
    if exists:
        lcsc_dir = os.path.join(path, "lcsc_manager")
        if os.path.exists(lcsc_dir):
            print(f"       ✓ lcsc_manager/ found")

        # Check for PCM package
        pcm_dir = os.path.join(path, "com.github.hulryung.kicad-lcsc-manager")
        if os.path.exists(pcm_dir):
            print(f"       ✓ PCM package found")
            plugins_dir = os.path.join(pcm_dir, "plugins")
            if os.path.exists(plugins_dir):
                print(f"         Contents: {os.listdir(plugins_dir)}")

print("\n" + "=" * 60)
print("Diagnostic complete")
print("=" * 60)
```

## Next Steps

Based on diagnostic results:

1. **If plugin is registered but no icon**: Check icon file path and permissions
2. **If plugin not registered**: Check import errors and `__init__.py`
3. **If import fails**: Check installation directory and file structure
4. **If nothing works**: Try manual installation in `~/Documents/KiCad/9.0/scripting/plugins/`
