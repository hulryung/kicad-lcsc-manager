"""BOM (Bill of Materials) import support.

Parses a JLCPCB / EasyEDA / KiCad-style BOM file, extracts the LCSC part
numbers, and batch-imports every referenced component (symbol, footprint,
3D model) into the project libraries.
"""
