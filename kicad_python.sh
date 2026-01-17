#!/bin/bash
# Launch KiCad Python in terminal with proper environment

# KiCad Python paths
KICAD_APP="/Applications/KiCad/KiCad.app"
PYTHON_BIN="$KICAD_APP/Contents/Frameworks/Python.framework/Versions/Current/bin/python3"
KICAD_PYTHON_PATH="$KICAD_APP/Contents/SharedSupport/scripting"

# Set environment for KiCad Python modules
export PYTHONPATH="$KICAD_PYTHON_PATH:$PYTHONPATH"

# Add KiCad libraries to DYLD path
export DYLD_LIBRARY_PATH="$KICAD_APP/Contents/Frameworks:$DYLD_LIBRARY_PATH"

echo "KiCad Python Terminal"
echo "====================="
echo "Python: $PYTHON_BIN"
echo "KiCad path: $KICAD_PYTHON_PATH"
echo ""
echo "You can now import pcbnew and use KiCad modules."
echo "Type 'exit()' to quit."
echo ""

# Launch Python REPL
"$PYTHON_BIN" "$@"
