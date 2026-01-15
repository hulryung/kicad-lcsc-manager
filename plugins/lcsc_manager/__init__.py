"""
LCSC Manager Plugin for KiCad

This plugin allows importing components from LCSC/EasyEDA and JLCPCB
directly into KiCad projects with symbols, footprints, and 3D models.
"""

__version__ = "0.1.0"
__author__ = "hulryung"
__license__ = "MIT"

# Register the plugin with KiCad
try:
    from .plugin import LCSCManagerPlugin

    # Create plugin instance
    # KiCad will automatically discover and register this
    LCSCManagerPlugin().register()

except Exception as e:
    import sys
    print(f"Failed to register LCSC Manager plugin: {e}", file=sys.stderr)
