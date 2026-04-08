# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.0] - 2026-04-08

Major integration of fixes ported from [easyeda2kicad.py v1.0.1](https://github.com/uPesy/easyeda2kicad.py) upstream. Improves correctness for footprint layer assignment, multi-unit symbol pin numbers, 3D model placement, and via handling. Several latent bugs in the JLC2KiCad_lib fork are fixed.

### Fixed
- **Footprint layer mapping**: corrected 7 EasyEDA layers that were miswired to wrong KiCad layers. TopAssembly (13) now lands on `F.Fab` instead of the wrong-side `B.Fab`; BottomAssembly (14) on `B.Fab` instead of `F.CrtYd`. Component Shape (99), Lead Shape (100), and Component Polarity (101) now map to `F.CrtYd`, `F.Fab`, and `F.SilkS` instead of being dumped on User.1/2/3.
- **Multi-unit symbol pin numbers**: canonical KiCad pin numbers are now extracted from the `^^num` segment (segment 4, field 4) instead of `spice_pin_number`. Multi-unit ICs (gates, dual op-amps, drivers) now show correct pin numbers.
- **3D model placement**: models are now XY-centered and Z bottom-aligned on the footprint origin, with EasyEDA `c_origin` translation offset applied (including upstream's Y axis negation and Z-axis canvas-unit scaling). Previously imported models were offset from the footprint reference.
- **Vias (`h_VIA`)**: implemented as plated through-hole (THT) pads matching upstream's `KI_VIA` template. Previously vias were silently dropped via a warning-only stub, breaking thermal relief and ground via connectivity.
- **SOLIDREGION H/V commands**: SVG path parser now handles horizontal (`H`) and vertical (`V`) commands. Rectangular silkscreen/edge-cut outlines are no longer silently truncated.
- **Pad number normalization**: `NAME(NUMBER)`-style EasyEDA pad numbers (e.g. `"A(1)"`, `"VCC(3)"`) are now normalized to the bare number. Fixes BGA/connector imports.
- **macOS KiCad SSL certificate verification**: API client now detects KiCad's bundled `certifi` inside `KiCad.app` (sorted by mtime for newest install) and falls back to the `certifi` package. Prevents `SSL: CERTIFICATE_VERIFY_FAILED` inside KiCad's embedded Python.
- **3D model OBJ→WRL conversion**: removed a corrupt-vertex-ordering `points.insert(-1, points[-1])` line, fixed transparency parser collision with `Kd` lines, added Rec.601 luminance-based `ambientIntensity` computation, and protected `material_id` against unbound variable on malformed OBJ.
- **SOLIDREGION filter**: decorative SOLIDREGIONs on layers 100/101 (lead solder indicators, pin-1 markers) are now dropped via an allow-list, matching upstream. Import output is significantly cleaner.

### Added
- **Opt-in disk cache** for EasyEDA component JSON responses. Gated on `api_cache_enabled` config flag (default `false`). Cache directory: `~/.kicad_lcsc_manager_cache/`. Atomic writes, corrupt-file cleanup, and opt-in-by-default design preserve existing behaviour.
- **Unit test infrastructure** under `tests/`: `test_3d_centering.py` (6), `test_lcsc_cache.py` (7), `test_footprint_handlers_patches.py` (20), `test_symbol_pin_numbers.py` (4), `test_regression_components.py` (2 E2E). Plugin `__init__.py` now guards the KiCad plugin registration so submodules can be imported for testing outside KiCad.

### Notes
- **Backward compatibility**: Footprints imported with previous versions have graphics on the old (wrong) layers. Already-placed footprints in existing projects are unchanged — only new imports use the corrected mappings.
- **Attribution**: Conversion logic adapted from [easyeda2kicad.py v1.0.1](https://github.com/uPesy/easyeda2kicad.py). Each ported function carries a `"Ported from easyeda2kicad.py v1.0.1"` docstring for traceability.

## [0.2.0] - 2026-01-17

### Added
- Advanced component search dialog with multi-parameter filtering
  - Search by component name, value, package type, and manufacturer
  - Support for LCSC ID direct search
  - Enter key support for quick search
- Real-time component search results with detailed information
  - LCSC ID, component name, package type
  - Pricing information from JLCPCB
  - Stock quantity with formatted display
  - Library type indicator (Basic/Extended)
- Sortable search results table
  - Click column headers to sort by any field
  - Ascending/descending order toggle
- Component preview functionality
  - Symbol preview using KiCad native rendering
  - Footprint preview using KiCad native rendering
  - High-quality preview images with 5x supersampling
  - Intelligent footprint cropping and scaling
- Asynchronous preview loading
  - Non-blocking UI for smooth navigation
  - Loading placeholder for immediate feedback
  - Auto-cancel previous requests when selecting new items
  - Preview caching for better performance
- JLCPCB API integration
  - Component search via JLCPCB API
  - Rate limiting with exponential backoff (10s, 20s, 30s)
  - Fresh session per request to avoid 403 errors
  - Enhanced browser headers for reliability
- Responsive dialog layout
  - 1400x900 default size with 1200x800 minimum
  - Balanced splitter layout for results and previews
  - Tab-based preview organization

### Changed
- Improved search workflow with preview before import
- Enhanced user experience with non-blocking UI operations
- Better API reliability with aggressive rate limiting

### Dependencies
- Added `Pillow>=10.0.0` for image processing
- Added `cairosvg>=2.7.0` for SVG to PNG conversion

## [0.1.0] - 2026-01-14

### Added
- Initial release
- Basic component import functionality
  - Import symbols from EasyEDA
  - Import footprints from EasyEDA
  - Import 3D models (WRL and STEP formats)
- LCSC/EasyEDA API integration
- JLCPCB API integration for component information
- Project-specific library management
  - Automatic creation of symbol libraries
  - Automatic creation of footprint libraries
  - Automatic creation of 3D model directories
- Symbol conversion from EasyEDA format to KiCad format
  - Support for rectangles, circles, polygons, polylines, arcs, ellipses
  - Pin conversion with proper electrical types
  - Text elements (reference, value, properties)
- Footprint conversion from EasyEDA format to KiCad format
  - PAD conversion (SMD and through-hole)
  - Copper shapes (tracks, circles, arcs, polygons)
  - Silkscreen and fabrication layers
  - 3D model references
- Configuration management
  - User preferences stored in ~/.kicad/lcsc_manager/
  - Logging system with file output
- KiCad 9.0 compatibility
- KiCad Plugin and Content Manager (PCM) support

### Dependencies
- `requests>=2.31.0`
- `pydantic>=2.5.0`

[0.2.0]: https://github.com/hulryung/kicad-lcsc-manager/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/hulryung/kicad-lcsc-manager/releases/tag/v0.1.0
