# Debugging Guide

## Real-time Log Monitoring

### Method 1: Using the Debug Script (Recommended)

```bash
cd /Users/dkkang/dev/kicad-lcsc-manager
./debug_realtime.sh
```

This will show real-time logs as you use the plugin. Keep this terminal open while testing in KiCad.

### Method 2: Manual Tail

```bash
tail -f ~/.kicad/lcsc_manager/logs/lcsc_manager.log
```

### Method 3: View All Logs

```bash
cat ~/.kicad/lcsc_manager/logs/lcsc_manager.log
```

Or open in editor:
```bash
open ~/.kicad/lcsc_manager/logs/lcsc_manager.log
```

## Log Levels

The plugin logs at different levels:
- **DEBUG**: Detailed API requests, responses
- **INFO**: Normal operations (search, import, etc.)
- **WARNING**: Non-fatal issues
- **ERROR**: Failures that prevent operations

## Common Issues and Solutions

### 1. API Errors

**Issue**: "Search failed: Network error: Expecting value: line 1 column 1"

**Solution**: The API endpoint has been updated. Make sure you have the latest version:
```bash
cd /Users/dkkang/dev/kicad-lcsc-manager
git pull
./install_test.sh
```

**Current Working API**: `https://easyeda.com/api/products/{component_id}/svgs`

### 2. Component Not Found

**Issue**: Component search returns no results

**Check**:
1. Verify the part number is correct (e.g., "C2040" not "c2040")
2. Ensure the component exists on JLCPCB/EasyEDA
3. Check network connectivity
4. Look at logs for detailed error

### 3. Import Fails

**Issue**: Import operation fails or creates empty/placeholder components

**Note**: Current implementation uses placeholder converters. For production use:
1. Integrate with [JLC2KiCad_lib](https://github.com/TousstNicolas/JLC2KiCad_lib)
2. Or implement full EasyEDA format parsing

### 4. Plugin Not Loading

**Check Installation**:
```bash
ls -la ~/Documents/KiCad/9.0/scripting/plugins/lcsc_manager/
```

Should show all files including `__init__.py`, `plugin.py`, etc.

**Check Dependencies**:
```bash
/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3 -c "import requests, pydantic; print('OK')"
```

**KiCad Scripting Console**:
1. Open KiCad PCB Editor
2. Tools → Scripting Console
3. Try:
   ```python
   import lcsc_manager
   print(lcsc_manager.__version__)
   ```

## Testing API Directly

Test the API outside of KiCad:

```bash
/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3 << 'EOF'
import requests
import json

component_id = "C2040"
url = f"https://easyeda.com/api/products/{component_id}/svgs"

response = requests.get(url)
data = json.loads(response.content.decode())

print(f"Success: {data.get('success')}")
if data.get('success'):
    print(f"Found {len(data.get('result', []))} components")
    for item in data['result']:
        print(f"  UUID: {item['component_uuid']}")
else:
    print("Error:", data)
EOF
```

## Development Debugging

### Hot Reload (Development Mode)

Use symlink instead of copying:

```bash
cd ~/Documents/KiCad/9.0/scripting/plugins/
rm -rf lcsc_manager
ln -s /Users/dkkang/dev/kicad-lcsc-manager/plugins/lcsc_manager lcsc_manager
```

Now changes to source code will be reflected after restarting KiCad.

### Add Debug Print Statements

Edit files in `/Users/dkkang/dev/kicad-lcsc-manager/plugins/lcsc_manager/`

Add debug logging:
```python
logger.debug(f"Debug info: {variable}")
```

### Python Debugger

For advanced debugging, add breakpoint in code:
```python
import pdb; pdb.set_trace()
```

Then watch KiCad's console output.

## Network Debugging

### Check API Response

```bash
curl -v "https://easyeda.com/api/products/C2040/svgs"
```

### Check Connectivity

```bash
ping easyeda.com
```

### Proxy Issues

If behind a proxy, configure:
```bash
export HTTP_PROXY=http://proxy:port
export HTTPS_PROXY=http://proxy:port
```

## Log File Location

Logs are stored at:
```
~/.kicad/lcsc_manager/logs/lcsc_manager.log
```

Config file:
```
~/.kicad/lcsc_manager/config.json
```

## Getting Help

1. Check logs first: `cat ~/.kicad/lcsc_manager/logs/lcsc_manager.log`
2. Try the test script: `./install_test.sh`
3. Open an issue on GitHub with:
   - Log excerpts (last 50 lines)
   - KiCad version
   - macOS version
   - Steps to reproduce

## Quick Diagnostic Script

```bash
#!/bin/bash
echo "=== KiCad LCSC Manager Diagnostic ==="
echo ""
echo "1. Plugin installed:"
ls -d ~/Documents/KiCad/*/scripting/plugins/lcsc_manager 2>/dev/null || echo "NOT FOUND"
echo ""
echo "2. Python dependencies:"
/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3 -c "import requests; print('✓ requests')" 2>/dev/null || echo "✗ requests"
/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3 -c "import pydantic; print('✓ pydantic')" 2>/dev/null || echo "✗ pydantic"
echo ""
echo "3. API test:"
/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3 -c "import requests; r=requests.get('https://easyeda.com/api/products/C2040/svgs'); print('✓ API accessible' if r.status_code==200 else '✗ API error')"
echo ""
echo "4. Recent logs:"
tail -5 ~/.kicad/lcsc_manager/logs/lcsc_manager.log 2>/dev/null || echo "No logs yet"
```

Save as `diagnostic.sh`, make executable, and run:
```bash
chmod +x diagnostic.sh
./diagnostic.sh
```
