"""
LCSC Manager Plugin for KiCad

This plugin allows importing components from LCSC/EasyEDA and JLCPCB
directly into KiCad projects with symbols, footprints, and 3D models.
"""
import os
import sys

__version__ = "0.8.1"
__author__ = "hulryung"
__license__ = "MIT"

# Add bundled libraries to Python path
lib_path = os.path.join(os.path.dirname(__file__), "lib")
if os.path.exists(lib_path) and lib_path not in sys.path:
    sys.path.insert(0, lib_path)

# Register the SWIG action plugin with KiCad.
# Guarded so unit tests can import submodules outside of KiCad's Python
# (which lacks pcbnew/wx). Skipped in an IPC plugin process: pcbnew is
# importable there but registering outside the pcbnew process fails, which
# would make importing this package fail (#19). No effect inside pcbnew.
from .utils.runtime import in_ipc_plugin_process

if not in_ipc_plugin_process():
    try:
        from .plugin import LCSCManagerPlugin

        if __name__ != "__main__":
            LCSCManagerPlugin().register()
    except ImportError:
        pass
