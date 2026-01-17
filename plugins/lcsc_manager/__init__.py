"""
LCSC Manager Plugin for KiCad

This plugin allows importing components from LCSC/EasyEDA and JLCPCB
directly into KiCad projects with symbols, footprints, and 3D models.
"""
import os
import sys

__version__ = "0.2.5"
__author__ = "hulryung"
__license__ = "MIT"

# Add bundled libraries to Python path
lib_path = os.path.join(os.path.dirname(__file__), "lib")
if os.path.exists(lib_path) and lib_path not in sys.path:
    sys.path.insert(0, lib_path)

# Register the plugin with KiCad
from .plugin import LCSCManagerPlugin

if __name__ != "__main__":
    LCSCManagerPlugin().register()
