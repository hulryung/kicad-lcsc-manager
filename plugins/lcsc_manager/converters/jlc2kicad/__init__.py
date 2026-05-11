"""
JLC2KiCad conversion handlers (symbol path only).

Originally adapted from TousstNicolas/JLC2KiCad_lib. Footprint and 3D-model
handlers were removed in v0.5.0; that pipeline is now backed by the
vendored upstream easyeda2kicad.py code under lcsc_manager.vendor.
Symbol conversion still lives here.
"""
from . import symbol_handlers

__all__ = ['symbol_handlers']
