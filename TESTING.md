# Testing Guide - KiCad LCSC Manager Plugin

## Prerequisites

1. **KiCad 6.0 or later** installed
2. **Python 3.8+** (KiCad includes Python)
3. **Git** for cloning the repository

## Installation for Testing

### Step 1: Find Your KiCad Plugins Directory

On **macOS**, the plugins directory is typically:
```bash
~/Documents/KiCad/[VERSION]/scripting/plugins/
```

For example:
- KiCad 8.0: `~/Documents/KiCad/8.0/scripting/plugins/`
- KiCad 7.0: `~/Documents/KiCad/7.0/scripting/plugins/`
- KiCad 6.0: `~/Documents/KiCad/6.0/scripting/plugins/`

**Quick way to find it:**
1. Open KiCad PCB Editor
2. Go to **Tools → External Plugins → Open Plugin Directory**
3. This will open your plugins folder

### Step 2: Install the Plugin

```bash
# Navigate to your KiCad plugins directory
cd ~/Documents/KiCad/8.0/scripting/plugins/

# Clone the repository (already exists locally, so copy it)
cp -r /Users/dkkang/dev/kicad-lcsc-manager/plugins/lcsc_manager .

# Verify the structure
ls -la lcsc_manager/
```

The structure should look like:
```
~/Documents/KiCad/8.0/scripting/plugins/
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

### Step 3: Install Python Dependencies

KiCad uses its own Python installation. Install dependencies to KiCad's Python:

**macOS:**
```bash
# Find KiCad's Python
/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3 --version

# Install dependencies
/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/pip3 install requests pydantic
```

Or try with system Python (if KiCad uses it):
```bash
pip3 install requests pydantic
```

### Step 4: Restart KiCad

Close KiCad completely and reopen it.

### Step 5: Verify Plugin is Loaded

1. Open **KiCad PCB Editor** (not the main KiCad window)
2. Go to **Tools → External Plugins**
3. You should see **"LCSC Manager"** in the list
4. Click on it to open the plugin dialog

Or check the toolbar for a new icon (if icon.png exists).

## Testing the Plugin

### Test 1: Open the Dialog

1. Open KiCad PCB Editor
2. Create a new project or open an existing one
3. **IMPORTANT**: Save the project first! (Plugin needs project path)
4. Go to **Tools → External Plugins → LCSC Manager**
5. Dialog should open

**Expected Result:**
- Dialog window opens
- Shows "Import components from LCSC/EasyEDA and JLCPCB"
- Has input field for LCSC Part Number
- Has checkboxes for Symbol, Footprint, 3D Model

### Test 2: Search for a Component

1. Enter a common LCSC part number: **C2040** (a common capacitor)
2. Click **"Search"**
3. Wait for API response

**Expected Result:**
- Component information displays in the text area
- Shows: Part number, name, description, manufacturer, package, stock, pricing
- If search fails, you'll see an error (API issues, rate limiting, or network)

**Alternative test parts:**
- **C1525** - 0.1uF capacitor
- **C22965** - Resistor
- **C2762247** - USB-C connector

### Test 3: Import a Component

1. After successful search, select import options:
   - ☑ Import Symbol
   - ☑ Import Footprint
   - ☑ Import 3D Model
2. Click **"Import"**
3. Watch the progress dialog

**Expected Result:**
- Progress dialog shows steps
- Success message appears
- Files created in `<project>/libs/lcsc/`:
  ```
  <project>/libs/lcsc/
  ├── symbols/
  │   └── lcsc_imported.kicad_sym
  ├── footprints.pretty/
  │   └── <LCSC_ID>_<package>.kicad_mod
  └── 3dmodels/
      └── <LCSC_ID>.wrl or .step
  ```
- Library tables updated:
  - `sym-lib-table`
  - `fp-lib-table`

### Test 4: Use the Component in KiCad

1. Close the plugin dialog
2. Open the **Schematic Editor**
3. Press **"A"** to add a symbol
4. In the symbol chooser, look for library: **"lcsc_imported"**
5. You should see the imported component
6. Place it on the schematic

**For PCB:**
1. Open **PCB Editor**
2. Go to **Footprint Libraries Manager**
3. Look for **"lcsc_footprints"** library
4. The imported footprint should be there

## Troubleshooting

### Plugin Not Appearing

**Check 1: Plugin Directory**
```bash
ls -la ~/Documents/KiCad/8.0/scripting/plugins/lcsc_manager/
```
Should show all files including `__init__.py` and `plugin.py`

**Check 2: Python Import**
```bash
/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3 -c "import requests; import pydantic; print('Dependencies OK')"
```

**Check 3: KiCad Console**
In KiCad PCB Editor:
1. Go to **Tools → Scripting Console**
2. Check for error messages
3. Try importing:
   ```python
   import lcsc_manager
   print(lcsc_manager.__version__)
   ```

### Import Error Messages

**Check logs:**
```bash
# View plugin logs
tail -f ~/.kicad/lcsc_manager/logs/lcsc_manager.log

# Or open in editor
cat ~/.kicad/lcsc_manager/logs/lcsc_manager.log
```

Common issues:
1. **Module not found**: Dependencies not installed
2. **No board loaded**: Open/save a PCB file first
3. **API errors**: Network issues or rate limiting
4. **Conversion errors**: Expected with placeholder converters

### Testing Without KiCad GUI

You can test components individually:

```bash
cd /Users/dkkang/dev/kicad-lcsc-manager

# Test imports
python3 -c "from plugins.lcsc_manager.api.lcsc_api import get_api_client; print('API client OK')"

# Test API search (requires internet)
python3 << 'EOF'
from plugins.lcsc_manager.api.lcsc_api import get_api_client

client = get_api_client()
result = client.search_component("C2040")
if result:
    print(f"Found: {result.get('name')}")
    print(f"Stock: {result.get('stock')}")
else:
    print("Not found")
EOF
```

## Development Testing

For development, you can symlink instead of copying:

```bash
cd ~/Documents/KiCad/8.0/scripting/plugins/
ln -s /Users/dkkang/dev/kicad-lcsc-manager/plugins/lcsc_manager lcsc_manager
```

This way, changes to the source code are immediately reflected (after KiCad restart).

## Known Limitations in Testing

1. **Placeholder Converters**: Generated symbols/footprints are generic
2. **API Reliability**: LCSC API is reverse-engineered, may be unstable
3. **EasyEDA Data**: Not all components have EasyEDA library data
4. **Rate Limiting**: Max 30 requests/minute to LCSC API
5. **3D Models**: May not download if not available on EasyEDA

## Next Steps After Successful Test

1. Test with multiple different components
2. Verify library registration works
3. Check symbol/footprint quality
4. Test in actual schematic/PCB workflow
5. Report any bugs or issues

## Quick Test Script

Save this as `test_plugin.sh` and run it:

```bash
#!/bin/bash

echo "=== KiCad LCSC Manager Plugin Test ==="
echo ""

# Check plugin directory
PLUGIN_DIR="$HOME/Documents/KiCad/8.0/scripting/plugins/lcsc_manager"
if [ -d "$PLUGIN_DIR" ]; then
    echo "✓ Plugin directory exists: $PLUGIN_DIR"
else
    echo "✗ Plugin directory NOT found: $PLUGIN_DIR"
    exit 1
fi

# Check required files
for file in __init__.py plugin.py dialog.py; do
    if [ -f "$PLUGIN_DIR/$file" ]; then
        echo "✓ File exists: $file"
    else
        echo "✗ File missing: $file"
        exit 1
    fi
done

# Check Python dependencies
echo ""
echo "Checking Python dependencies..."
python3 -c "import requests" 2>/dev/null && echo "✓ requests installed" || echo "✗ requests NOT installed"
python3 -c "import pydantic" 2>/dev/null && echo "✓ pydantic installed" || echo "✗ pydantic NOT installed"
python3 -c "import wx" 2>/dev/null && echo "✓ wxPython installed" || echo "✗ wxPython NOT installed (should come with KiCad)"

echo ""
echo "=== Setup complete! ==="
echo "1. Open KiCad PCB Editor"
echo "2. Go to Tools → External Plugins → LCSC Manager"
echo "3. Try searching for part: C2040"
```

Run it:
```bash
chmod +x test_plugin.sh
./test_plugin.sh
```
