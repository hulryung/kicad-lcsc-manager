# Installation Guide

## Installation Methods

### Method 1: KiCad Plugin Manager (Recommended - Coming Soon)

1. Open KiCad
2. Go to **Tools → Plugin and Content Manager**
3. Search for "LCSC Manager"
4. Click **Install**
5. Restart KiCad

### Method 2: Manual Installation

#### Step 1: Locate Your KiCad Plugins Directory

The plugins directory location varies by operating system:

**Windows:**
```
C:\Users\[USERNAME]\Documents\KiCad\[VERSION]\scripting\plugins\
```

**macOS:**
```
~/Documents/KiCad/[VERSION]/scripting/plugins/
```

**Linux:**
```
~/.kicad/scripting/plugins/
```

Or in your KiCad installation:
```
~/.local/share/kicad/[VERSION]/scripting/plugins/
```

#### Step 2: Find Your Plugins Directory in KiCad

If you're unsure of the exact path:

1. Open KiCad PCB Editor
2. Go to **Tools → External Plugins → Open Plugin Directory**
3. This will open your plugins folder

#### Step 3: Install the Plugin

**Option A: Clone from Git**

```bash
cd [your-kicad-plugins-directory]
git clone https://github.com/hulryung/kicad-lcsc-manager.git
```

**Option B: Download and Extract**

1. Download the latest release from GitHub
2. Extract the `kicad-lcsc-manager` folder
3. Copy the entire `kicad-lcsc-manager/plugins/lcsc_manager` directory to your KiCad plugins directory

The final structure should look like:
```
[kicad-plugins-directory]/
└── lcsc_manager/
    ├── __init__.py
    ├── plugin.py
    ├── dialog.py
    ├── api/
    ├── converters/
    ├── library/
    ├── utils/
    └── resources/
```

#### Step 4: Install Python Dependencies

The plugin requires some Python packages. Install them using pip:

```bash
pip install requests pydantic
```

Or if KiCad uses its own Python installation:

**Windows:**
```cmd
"C:\Program Files\KiCad\[VERSION]\bin\python.exe" -m pip install requests pydantic
```

**macOS:**
```bash
/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/pip3 install requests pydantic
```

**Linux:**
```bash
# Usually uses system Python
pip3 install requests pydantic
```

#### Step 5: Restart KiCad

Close and reopen KiCad for the plugin to be loaded.

## Verification

1. Open KiCad PCB Editor
2. Look for the LCSC Manager icon in the toolbar (if icon is set)
3. Or go to **Tools → External Plugins** and check if "LCSC Manager" is listed

## Troubleshooting

### Plugin Not Showing Up

1. **Check directory location**: Make sure the plugin is in the correct directory
2. **Check file structure**: Ensure `__init__.py` and `plugin.py` are in the `lcsc_manager` folder
3. **Check Python version**: KiCad requires Python 3.8 or later
4. **Check logs**: Look for error messages in KiCad's scripting console

### Import Errors

If you see import errors:

1. Make sure dependencies are installed: `pip install requests pydantic`
2. Check that KiCad can access the Python packages
3. Try installing packages to KiCad's Python installation (see Step 4 above)

### Permission Errors

On Linux/macOS, you might need to set permissions:

```bash
chmod -R 755 ~/.kicad/scripting/plugins/lcsc_manager
```

### Finding Logs

The plugin creates logs at:

**All Platforms:**
```
~/.kicad/lcsc_manager/logs/lcsc_manager.log
```

Check this file for detailed error messages.

## Uninstallation

To remove the plugin:

1. Delete the `lcsc_manager` directory from your KiCad plugins folder
2. Delete the configuration and logs:
   ```bash
   rm -rf ~/.kicad/lcsc_manager
   ```
3. Restart KiCad

## Next Steps

Once installed, check out the [Usage Guide](README.md#usage) to learn how to import components.
