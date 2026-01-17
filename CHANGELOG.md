# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
