#!/bin/bash

echo "=== Real-time Plugin Debug Logs ==="
echo "Press Ctrl+C to stop"
echo ""
echo "Watching: ~/.kicad/lcsc_manager/logs/lcsc_manager.log"
echo ""

# Create log file if it doesn't exist
mkdir -p ~/.kicad/lcsc_manager/logs
touch ~/.kicad/lcsc_manager/logs/lcsc_manager.log

# Follow the log file in real-time
tail -f ~/.kicad/lcsc_manager/logs/lcsc_manager.log
