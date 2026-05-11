"""Vendored subset of easyeda2kicad.py (footprint pipeline only).

Upstream's package __init__ re-exports symbol + 3D-model exporters too; we
only ship the footprint-related modules, so this file is intentionally
empty. Import the submodules directly:

    from lcsc_manager.vendor.easyeda2kicad.easyeda.easyeda_importer \\
        import EasyedaFootprintImporter
    from lcsc_manager.vendor.easyeda2kicad.kicad.export_kicad_footprint \\
        import ExporterFootprintKicad

Original project: https://github.com/uPesy/easyeda2kicad.py (AGPL-3.0).
See LICENSE in this directory.
"""

__upstream_version__ = "1.0.1"
