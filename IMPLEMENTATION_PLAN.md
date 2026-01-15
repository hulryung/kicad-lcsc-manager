# KiCad LCSC Manager Plugin - Implementation Plan

## Project Overview
A KiCad plugin that allows users to search and import electronic components from LCSC/EasyEDA and JLCPCB directly into their KiCad projects, including symbols, footprints, and 3D models.

## Architecture

### Plugin Type
- **KiCad Action Plugin** - Integrates as a toolbar button in PCB Editor and Symbol Editor
- **Target KiCad Version**: 6.0+ (with backward compatibility considerations)
- **Language**: Python 3.8+

### Core Components

```
kicad-lcsc-manager/
├── plugins/
│   └── lcsc_manager/
│       ├── __init__.py              # Plugin entry point & registration
│       ├── plugin.py                # Main plugin class (ActionPlugin)
│       ├── dialog.py                # GUI dialog for search/selection
│       ├── api/
│       │   ├── __init__.py
│       │   ├── lcsc_api.py          # LCSC/EasyEDA API wrapper
│       │   └── jlcpcb_api.py        # JLCPCB API wrapper
│       ├── converters/
│       │   ├── __init__.py
│       │   ├── symbol_converter.py  # Symbol format conversion
│       │   ├── footprint_converter.py
│       │   └── model_3d_converter.py
│       ├── library/
│       │   ├── __init__.py
│       │   └── library_manager.py   # KiCad library registration
│       ├── utils/
│       │   ├── __init__.py
│       │   ├── logger.py
│       │   └── config.py
│       └── resources/
│           ├── icon.png             # Toolbar icon
│           └── metadata.json        # Plugin metadata for PCM
├── tests/
│   └── test_*.py
├── requirements.txt
├── setup.py
└── README.md
```

## Implementation Phases

### Phase 1: Plugin Core Structure (Current)
**Goal**: Set up basic KiCad plugin with UI dialog

**Files to create**:
1. `plugins/lcsc_manager/__init__.py` - Plugin registration
2. `plugins/lcsc_manager/plugin.py` - ActionPlugin implementation
3. `plugins/lcsc_manager/dialog.py` - wxPython UI for part search
4. `plugins/lcsc_manager/utils/logger.py` - Logging setup
5. `plugins/lcsc_manager/utils/config.py` - Configuration management

**Key Features**:
- Register plugin with KiCad
- Add toolbar button/menu entry
- Create basic search dialog (LCSC ID input)
- Setup logging and error handling

### Phase 2: API Integration
**Goal**: Implement LCSC/JLCPCB API clients

**Files to create**:
1. `plugins/lcsc_manager/api/lcsc_api.py`
   - Search parts by LCSC ID
   - Fetch component data (symbol, footprint, 3D model)
   - Parse EasyEDA format data

2. `plugins/lcsc_manager/api/jlcpcb_api.py`
   - Use official JLCPCB API
   - Search parts by parameters (category, specs)
   - Get pricing and availability info

**API Endpoints** (based on easyeda2kicad research):
- LCSC: Reverse-engineered endpoints from EasyEDA
- JLCPCB: Official API at api.jlcpcb.com

### Phase 3: Format Converters
**Goal**: Convert EasyEDA/LCSC data to KiCad formats

**Files to create**:
1. `plugins/lcsc_manager/converters/symbol_converter.py`
   - Parse EasyEDA symbol JSON
   - Generate `.kicad_sym` format
   - Handle pin mapping and properties

2. `plugins/lcsc_manager/converters/footprint_converter.py`
   - Parse EasyEDA footprint JSON
   - Generate `.kicad_mod` format
   - Handle pad shapes and coordinates

3. `plugins/lcsc_manager/converters/model_3d_converter.py`
   - Download 3D models (STEP/WRL)
   - Convert if necessary
   - Set proper 3D model paths

**Note**: We can leverage/reference easyeda2kicad.py conversion logic

### Phase 4: Library Management
**Goal**: Add components to project libraries

**Files to create**:
1. `plugins/lcsc_manager/library/library_manager.py`
   - Create/update project-specific library files
   - Register libraries in project configuration
   - Handle symbol/footprint library tables
   - Manage 3D model paths

**Output Structure**:
```
<project>/libs/lcsc/
├── symbols/
│   └── lcsc_imported.kicad_sym
├── footprints.pretty/
│   └── <LCSC_ID>.kicad_mod
└── 3dmodels/
    ├── <LCSC_ID>.step
    └── <LCSC_ID>.wrl
```

### Phase 5: Enhanced Features (Future)
- Advanced search (by category, specs, price range)
- Batch import multiple components
- Component preview before import
- Update existing components
- Integration with BOM generation
- PCM (Plugin and Content Manager) packaging

## Technical Decisions

### 1. Dependency on easyeda2kicad
**Decision**: Use as reference but implement independently
**Reasoning**:
- Better integration with KiCad API
- More control over conversion process
- Can optimize for our use case
- However, can reference their conversion algorithms

### 2. Library Storage Location
**Decision**: Project-specific libraries in `<project>/libs/lcsc/`
**Reasoning**:
- Self-contained projects
- Easy to share projects
- Avoids global library pollution
- Matches KiCAD-EasyEDA-Parts approach

### 3. API Strategy
**Decision**: Start with LCSC (via easyeda2kicad approach), add JLCPCB API later
**Reasoning**:
- LCSC/EasyEDA has more component data
- JLCPCB API is for pricing/availability
- Can combine both later for complete solution

### 4. KiCad Version Support
**Decision**: Target KiCad 6.0+ primarily, test on 7.0 and 8.0
**Reasoning**:
- KiCad 6.0+ has stable Python API
- File formats are consistent
- Wide adoption of 6.0+

### 5. GUI Framework
**Decision**: Use wxPython (KiCad's native GUI)
**Reasoning**:
- Consistent look and feel
- No additional dependencies
- KiCad already includes wxPython

## Dependencies
```
requirements.txt:
- requests         # HTTP requests for API
- pydantic         # Data validation
- beautifulsoup4   # HTML parsing if needed
```

## Testing Strategy
1. Unit tests for converters
2. Integration tests with sample LCSC parts
3. Manual testing in KiCad 6, 7, 8
4. Test on Windows, macOS, Linux

## Success Criteria
- [ ] Plugin appears in KiCad toolbar
- [ ] Can search parts by LCSC ID
- [ ] Successfully downloads and converts symbols
- [ ] Successfully downloads and converts footprints
- [ ] Successfully downloads 3D models
- [ ] Components appear in project libraries
- [ ] Components can be placed in schematic/PCB
- [ ] 3D models display correctly

## Next Steps
1. Initialize Python package structure
2. Implement plugin registration (Phase 1)
3. Create basic UI dialog (Phase 1)
4. Implement LCSC API client (Phase 2)
5. Implement converters (Phase 3)
6. Implement library manager (Phase 4)
7. Test with real components
8. Package for distribution
