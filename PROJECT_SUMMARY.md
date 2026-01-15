# KiCad LCSC Manager - Project Summary

## Overview

KiCad LCSC Manager is a plugin for KiCad that enables users to search and import electronic components from LCSC/EasyEDA and JLCPCB directly into their projects. The plugin automatically downloads symbols, footprints, and 3D models, adding them to project-specific libraries.

## Implementation Status

### ✅ Completed Components

#### Phase 1: Plugin Core Structure
- ✅ Plugin registration with KiCad (ActionPlugin)
- ✅ Main plugin class with toolbar integration
- ✅ wxPython GUI dialog for component search and import
- ✅ Configuration management system
- ✅ Logging infrastructure
- ✅ Project structure and packaging setup

#### Phase 2: API Integration
- ✅ LCSC/EasyEDA API client
  - Component search by LCSC ID
  - Rate limiting (30 requests/minute)
  - Error handling and retry logic
  - File download functionality
- ✅ JLCPCB API client (official API)
  - Component search and details
  - Pricing and inventory information
  - Category browsing

#### Phase 3: Format Converters
- ✅ Symbol converter (EasyEDA → KiCad .kicad_sym)
  - Placeholder symbol generation
  - Component properties and metadata
  - Library file management
- ✅ Footprint converter (EasyEDA → KiCad .kicad_mod)
  - Placeholder footprint generation
  - 3D model path integration
- ✅ 3D Model converter/downloader
  - Model download from URLs
  - STEP and VRML format support
  - Placeholder model generation

#### Phase 4: Library Management
- ✅ Project-specific library organization
- ✅ Symbol library table management (sym-lib-table)
- ✅ Footprint library table management (fp-lib-table)
- ✅ Automatic library registration with KiCad
- ✅ Component import workflow integration

### 🚧 Known Limitations

#### 1. Placeholder Converters
The current implementation uses **placeholder converters** that generate generic symbols and footprints. Full conversion from EasyEDA format requires:

- Parsing EasyEDA's custom JSON format for shapes, pins, pads
- Converting coordinate systems
- Handling all component types (resistors, ICs, connectors, etc.)
- Proper pin numbering and naming

**Recommendation**: For production use, integrate with or reference the [easyeda2kicad library](https://github.com/uPesy/easyeda2kicad.py) which has full conversion logic.

#### 2. API Endpoints
The LCSC/EasyEDA APIs are **reverse-engineered** and not officially documented:
- Endpoints may change without notice
- Rate limits are approximate
- Some data fields may be unavailable

**Recommendation**: Monitor API responses and update error handling as needed.

#### 3. EasyEDA Data Availability
Not all LCSC components have EasyEDA symbol/footprint data:
- Some components only have basic LCSC product info
- EasyEDA UUID may not be available
- Symbol/footprint quality varies

**Fallback**: Plugin generates placeholder components when EasyEDA data is unavailable.

## Architecture

### Directory Structure

```
kicad-lcsc-manager/
├── plugins/
│   └── lcsc_manager/
│       ├── __init__.py              # Plugin registration
│       ├── plugin.py                # Main ActionPlugin
│       ├── dialog.py                # GUI interface
│       ├── api/
│       │   ├── lcsc_api.py          # LCSC/EasyEDA client
│       │   └── jlcpcb_api.py        # JLCPCB client
│       ├── converters/
│       │   ├── symbol_converter.py   # Symbol conversion
│       │   ├── footprint_converter.py # Footprint conversion
│       │   └── model_3d_converter.py  # 3D model handling
│       ├── library/
│       │   └── library_manager.py    # Library management
│       ├── utils/
│       │   ├── logger.py            # Logging
│       │   └── config.py            # Configuration
│       └── resources/
│           └── icon.png             # Toolbar icon (optional)
├── tests/                           # Unit tests (future)
├── requirements.txt
├── setup.py
├── README.md
├── INSTALL.md
└── IMPLEMENTATION_PLAN.md
```

### Data Flow

1. **User Input** → User enters LCSC part number in dialog
2. **API Search** → LCSC API returns component data
3. **EasyEDA Fetch** → If available, fetch EasyEDA symbol/footprint data
4. **Conversion** → Convert EasyEDA format to KiCad format
5. **Library Import** → Save to project libraries and update library tables
6. **KiCad Integration** → Component appears in KiCad libraries

### Key Design Decisions

1. **Project-Specific Libraries**
   - Components saved to `<project>/libs/lcsc/`
   - Makes projects self-contained and portable
   - Avoids polluting global libraries

2. **Modular Architecture**
   - Separate API, converter, and library management modules
   - Easy to test and maintain
   - Can swap implementations (e.g., different converters)

3. **Error Handling**
   - Graceful degradation when API fails
   - Fallback to placeholder components
   - Detailed logging for debugging

4. **Rate Limiting**
   - Respects API rate limits
   - Prevents plugin from getting blocked
   - User-friendly progress indicators

## Installation

See [INSTALL.md](INSTALL.md) for detailed installation instructions.

### Quick Start

1. Copy `plugins/lcsc_manager/` to your KiCad plugins directory
2. Install dependencies: `pip install requests pydantic`
3. Restart KiCad
4. Look for "LCSC Manager" in Tools → External Plugins

## Usage

1. Open a KiCad project (PCB Editor)
2. Click the LCSC Manager icon or go to Tools → External Plugins → LCSC Manager
3. Enter an LCSC part number (e.g., "C2040")
4. Click "Search" to view component details
5. Select import options (symbol, footprint, 3D model)
6. Click "Import" to add to project libraries
7. Use components from the `lcsc_imported` library in your schematic/PCB

## Configuration

Configuration file: `~/.kicad/lcsc_manager/config.json`

Default settings:
```json
{
  "library_path": "libs/lcsc",
  "symbol_lib_name": "lcsc_imported.kicad_sym",
  "footprint_lib_name": "footprints.pretty",
  "model_3d_path": "3dmodels",
  "api_timeout": 30,
  "download_timeout": 60,
  "cache_enabled": true,
  "cache_expiry_days": 7
}
```

## Future Enhancements

### Priority 1: Full Conversion Logic
- Integrate with easyeda2kicad library
- Parse complete EasyEDA JSON format
- Support all component types
- Accurate pin/pad placement

### Priority 2: Advanced Features
- Batch import multiple components
- Component preview before import
- Search by parameters (category, specs, price)
- Update existing components
- BOM integration

### Priority 3: User Experience
- In-dialog component preview
- Symbol/footprint comparison view
- Recently imported components list
- Favorites/bookmarks

### Priority 4: Distribution
- Package for KiCad Plugin and Content Manager (PCM)
- Automated testing
- CI/CD pipeline
- Version management

## Contributing

Contributions are welcome! Areas that need work:

1. **Full converter implementation** - Parse EasyEDA format completely
2. **API stability** - Monitor and adapt to API changes
3. **Testing** - Unit tests and integration tests
4. **Documentation** - User guides and API docs
5. **Packaging** - PCM integration

## Credits

Inspired by and references:
- [easyeda2kicad.py](https://github.com/uPesy/easyeda2kicad.py) - CLI conversion tool
- [easyeda2kicad_plugin](https://github.com/rasmushauschild/easyeda2kicad_plugin) - KiCad plugin wrapper
- [KiCAD-EasyEDA-Parts](https://github.com/Yanndroid/KiCAD-EasyEDA-Parts) - Alternative implementation
- [JLC2KiCadLib](https://pypi.org/project/JLC2KiCadLib/) - JLCPCB component library tool

## License

MIT License - See [LICENSE](LICENSE) file

## Support

- GitHub Issues: [Report bugs or request features](https://github.com/yourusername/kicad-lcsc-manager/issues)
- Logs: Check `~/.kicad/lcsc_manager/logs/lcsc_manager.log` for errors
- KiCad Forums: [KiCad.info](https://forum.kicad.info/)

---

**Version**: 0.1.0 (Alpha)
**Status**: Functional with placeholder converters
**Tested**: KiCad 6.0, 7.0, 8.0 (architecture only, needs testing in real environment)
