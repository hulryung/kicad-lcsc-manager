"""
LCSC Manager Plugin for KiCad

This plugin allows importing components from LCSC/EasyEDA and JLCPCB
directly into KiCad projects with symbols, footprints, and 3D models.
"""

__version__ = "0.2.1"
__author__ = "hulryung"
__license__ = "MIT"

# Register the plugin with KiCad
from .plugin import LCSCManagerPlugin

if __name__ != "__main__":
    LCSCManagerPlugin().register()
