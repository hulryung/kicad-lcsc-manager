# KiCad LCSC Manager Plugin

A KiCad plugin that allows you to search and import electronic components from LCSC/EasyEDA and JLCPCB directly into your KiCad projects, including symbols, footprints, and 3D models.

> **🚀 v0.3.0 — Upstream integration (2026-04-08)**: This release incorporates significant conversion-logic fixes **ported directly from [easyeda2kicad.py v1.0.1](https://github.com/uPesy/easyeda2kicad.py)** by [uPesy](https://github.com/uPesy). Highlights:
>
> - **Footprint layer mapping fixed** — 7 previously-miswired EasyEDA layers (TopAssembly/BottomAssembly/LIBBODY/etc.) now land on the correct KiCad layers instead of the wrong side of the board or the User.1/2/3 junk drawer.
> - **Multi-unit symbol pin numbers** — gates, dual op-amps, and multi-channel drivers now get the canonical KiCad pin number from the `^^num` segment instead of the wrong `spice_pin_number`.
> - **3D model placement** — models are XY-centered, Z bottom-aligned, and positioned at the EasyEDA `c_origin` offset (with correct Y negation and canvas-unit scaling).
> - **Plated vias** — `h_VIA` now emits real `thru_hole` pads with `*.Cu *.Paste *.Mask`, matching upstream. Previously vias were silently dropped.
> - **Footprint SVG path parser** — `H` and `V` commands are now handled (rectangular silkscreen outlines no longer truncate).
> - **Pad number normalization** — `"VCC(3)"` → `"3"` for BGA/connector parts.
> - **macOS KiCad SSL** — auto-detects KiCad's bundled `certifi` so HTTPS calls don't fail in KiCad's embedded Python.
> - **Opt-in disk cache** for EasyEDA component JSON (off by default).
>
> See [CHANGELOG.md](CHANGELOG.md) and the **[Credits](#credits)** section for full attribution.

## ✨ Features

### Advanced Component Search
- 🔍 **Multi-parameter search**: Search by component name, value, package type, and manufacturer
- 📊 **Rich search results**: View LCSC ID, name, package, price, stock, and library type (Basic/Extended)
- 🔀 **Sortable columns**: Click column headers to sort results by any field
- 👁️ **High-quality previews**: Symbol and footprint previews rendered directly from EasyEDA's SVG API
- ⚡ **Fully asynchronous**: Previews load independently — browse and import without waiting
- 💾 **Preview caching**: Better performance with cached previews
- ⌨️ **Keyboard support**: Enter to search, ESC to close

### Component Import
- 📦 Automatically download symbols, footprints, and 3D models (WRL and STEP formats)
- 💰 Real-time stock, pricing, and datasheet information from JLCPCB API
- 📚 Add components to project-specific libraries
- ⚠️ Smart overwrite detection with selective import options
- 🎨 Seamless integration with KiCad 9.0+
- 🔄 Support for both LCSC/EasyEDA and JLCPCB parts

## 📥 Installation

> **Note about KiCad PCM**: This plugin is **not available in the official KiCad Plugin and Content Manager** due to KiCad's commercial services policy. Plugins that directly integrate with commercial APIs (like LCSC/JLCPCB) require a formal contract between the service provider and the KiCad team. As a third-party developer, I cannot submit to the official PCM. However, you can install it through the methods below.

### Method 1: Install via Custom Repository (Easiest)

1. Open KiCad PCB Editor
2. Go to **Tools → Plugin and Content Manager**
3. Click **Manage** (bottom-left)
4. Click **Add Repository**
5. Enter the following URL:
   ```
   https://raw.githubusercontent.com/hulryung/kicad-lcsc-manager/main/repository.json
   ```
6. Click **OK** and close the repository manager
7. Search for **"LCSC Manager"** in the PCM
8. Click **Install**
9. Restart KiCad

### Method 2: Manual Installation

1. **Download the latest release**
   - Go to [Releases](https://github.com/hulryung/kicad-lcsc-manager/releases)
   - Download `kicad-lcsc-manager-x.x.x.zip` from the latest release

2. **Extract to KiCad plugins directory**

   Find your KiCad version (e.g., 9.0) and extract to:

   - **Windows**:
     ```
     C:\Users\[USERNAME]\Documents\KiCad\9.0\3rdparty\plugins\
     ```
   - **macOS**:
     ```
     ~/Documents/KiCad/9.0/3rdparty/plugins/
     ```
   - **Linux**:
     ```
     ~/.local/share/kicad/9.0/3rdparty/plugins/
     ```

3. **Install Python dependencies** ⚠️ **REQUIRED**

   **IMPORTANT**: The plugin will NOT work without these Python packages!

   Install them using KiCad's Python (not your system Python):

   **macOS**:
   ```bash
   /Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3 -m pip install --user requests pydantic
   ```

   **Windows** (PowerShell):
   ```powershell
   & "C:\Program Files\KiCad\9.0\bin\python.exe" -m pip install --user requests pydantic
   ```

   **Linux**:
   ```bash
   pip3 install --user requests pydantic
   ```

4. **Restart KiCad completely**

5. **Verify installation**
   - Open KiCad PCB Editor
   - You should see the LCSC Manager icon in the toolbar
   - Or go to **Tools → External Plugins → LCSC Manager**

## Screenshots

![LCSC Manager Dialog](docs/images/screenshot-main-dialog.png)

*Import components from LCSC/EasyEDA with real-time stock and pricing information*

## 🚀 Usage

### Quick Start

1. **Open KiCad PCB Editor** with a saved project
2. **Launch the plugin**:
   - Click the LCSC Manager icon in the toolbar, or
   - Go to **Tools → External Plugins → LCSC Manager**

### Search and Preview Components

3. **Search for components**:
   - Enter search terms (e.g., "RP2040", "10uF", "0603")
   - Optionally filter by package type (e.g., "LQFN", "SOT23")
   - Press **Enter** or click **Search**

4. **Browse results**:
   - View component list with LCSC ID, name, package, price, stock, and type
   - Click any column header to sort results
   - Select a component to view previews

5. **Review previews**:
   - **Symbol tab**: Symbol preview from EasyEDA
   - **Footprint tab**: Footprint preview from EasyEDA
   - Previews load asynchronously - you can browse and import while loading

### Import Components

6. **Select import options**:
   - ✓ Import Symbol
   - ✓ Import Footprint
   - ✓ Import 3D Model

7. **Click "Import Selected"** to add the component to your project

8. **Find imported components** in your project libraries:
   - Symbol: `<project>/libs/lcsc/symbols/lcsc_imported.kicad_sym`
   - Footprint: `<project>/libs/lcsc/footprints.pretty/`
   - 3D Models: `<project>/libs/lcsc/3dmodels/`

### Tips

- **Search by LCSC ID**: Enter part numbers like "C2040" for exact matches
- **Search by value**: Try "10uF", "100nF", "10k" to find capacitors and resistors
- **Filter by package**: Add package filter like "0603", "0805", "SOT23" for better results
- **Browse quickly**: Click through components rapidly - previews load in the background
- **Check stock**: Basic parts are usually cheaper and more available than Extended parts

## 🗑️ Uninstallation

To remove the plugin from your system:

```bash
bash uninstall_test.sh
```

The script will:
- Detect and remove the plugin from KiCad plugins directory
- Optionally remove Python dependencies (if not used by other apps)
- Optionally remove configuration and logs

Alternatively, manually remove:
- Plugin: `~/Documents/KiCad/9.0/3rdparty/plugins/com_github_hulryung_kicad-lcsc-manager/`
- Config/Logs: `~/.kicad/lcsc_manager/`

## 📋 Requirements

- **KiCad**: 9.0 or later (recommended)
  - May work with KiCad 7.0+ but not officially tested
- **Python**: 3.9+ (bundled with KiCad)
- **Python packages**:
  - `requests>=2.31.0` - For API calls
  - `pydantic>=2.5.0` - For data validation
- **Internet connection**: Required for downloading components from LCSC/JLCPCB

## Development

### Setup Development Environment

```bash
# Clone the repository
git clone https://github.com/hulryung/kicad-lcsc-manager.git
cd kicad-lcsc-manager

# Install dependencies
pip install -r requirements.txt

# Run tests
python -m pytest tests/
```

### Project Structure

```
kicad-lcsc-manager/
├── plugins/lcsc_manager/    # Main plugin code
│   ├── api/                 # LCSC/EasyEDA API client
│   ├── converters/          # Symbol, footprint, 3D model converters
│   ├── library/             # KiCad library management
│   ├── preview/             # Preview rendering
│   └── utils/               # Config, logging utilities
├── scripts/                 # Build and packaging scripts
├── tests/                   # Integration tests
├── .github/workflows/       # CI/CD (auto-release on tag)
└── README.md
```

## Related Projects

Check out my other KiCad and LCSC-related tools:

### 🌐 [EasyEDA2KiCad Web](https://github.com/hulryung/easyeda2kicad-web)
A web-based tool to convert EasyEDA/LCSC components to KiCad format with real-time 2D and 3D visualization. Perfect for previewing components before importing them into your project.

**Features:**
- Web-based interface (no installation required)
- Real-time 2D footprint preview
- 3D model visualization
- Instant conversion and download

### 📋 [BOM Extender](https://github.com/hulryung/bom-extender)
BOM (Bill of Materials) extension tool that automatically fetches LCSC component information and exports enhanced BOMs.

**Features:**
- Automatic LCSC component lookup
- Stock and pricing information
- Export to various formats
- Batch processing support

---

## Credits

### Code ported from easyeda2kicad.py v1.0.1

Starting with **v0.3.0**, this plugin incorporates conversion logic **directly ported** from the upstream project **[easyeda2kicad.py v1.0.1](https://github.com/uPesy/easyeda2kicad.py)** by [uPesy](https://github.com/uPesy) (AGPL-3.0). Every ported function carries a `"Ported from easyeda2kicad.py v1.0.1 <module>"` docstring for full traceability.

**What was ported:**

| Upstream source | Ported into |
|---|---|
| `kicad/export_kicad_3d_model.py` — `_get_obj_bbox`, `get_materials`, `get_vertices`, `generate_wrl_model` | `plugins/lcsc_manager/converters/model_3d_converter.py` — 3D model centering, Z bottom alignment, Rec.601 luminance, EE placement offset |
| `easyeda/easyeda_importer.py` — `Easyeda3dModelImporter.parse_3d_model_info` | `model_3d_converter.py::_extract_3d_model_info` — extracts `uuid`, `c_origin`, `z`, `c_rotation` from SVGNODE |
| `kicad/parameters_kicad_footprint.py` — `KI_LAYERS` table | `converters/jlc2kicad/footprint_handlers.py::layer_correspondance` — correct mapping for all 17 EasyEDA layers |
| `kicad/export_kicad_footprint.py` — `_SOLID_REGION_LAYERS`, `_parse_solid_region_path` | `footprint_handlers.py::_SOLID_REGION_LAYERS` filter + `h_SOLIDREGION` M/L/H/V/A/Z parser |
| `kicad/export_kicad_footprint.py` — pad number normalization | `footprint_handlers.py::_normalize_pad_number` |
| `kicad/parameters_kicad_footprint.py` — `KI_VIA` template | `footprint_handlers.py::h_VIA` — plated THT emission |
| `easyeda/easyeda_importer.py` — `add_easyeda_pin` | `converters/jlc2kicad/symbol_handlers.py::_extract_pin_number` — canonical multi-unit pin number |
| `easyeda/easyeda_api.py` — `_create_ssl_context` | `api/lcsc_api.py::_discover_ca_bundle` — macOS KiCad certifi fallback |
| `easyeda/easyeda_api.py` — `_get_cache_path`/`_read_from_cache`/`_write_to_cache` | `api/lcsc_api.py::_cache_path/_cache_read/_cache_write` — opt-in disk cache |

### Other related projects

This plugin was originally structured using concepts and base handler code from:
- [JLC2KiCad_lib](https://github.com/TousstNicolas/JLC2KiCad_lib) — base jlc2kicad handler structure (MIT)
- [easyeda2kicad_plugin](https://github.com/rasmushauschild/easyeda2kicad_plugin) — KiCad plugin wrapper
- [KiCAD-EasyEDA-Parts](https://github.com/Yanndroid/KiCAD-EasyEDA-Parts) — alternative implementation

## License

MIT License — see `LICENSE` file for the plugin wrapper code.

**License note:** Portions of the conversion logic are ported from [easyeda2kicad.py](https://github.com/uPesy/easyeda2kicad.py), which is licensed under **AGPL-3.0**. Each ported function is marked with a docstring attribution. Users redistributing this plugin should review both the MIT license of the plugin wrapper and the AGPL-3.0 license of the upstream easyeda2kicad.py project.

## ❓ FAQ

### Why isn't this available in the official KiCad PCM?

According to [KiCad's commercial services policy](https://dev-docs.kicad.org/en/addons/index.html#_commercial_services), plugins that directly integrate with commercial APIs (like LCSC/JLCPCB) require a formal contract between the service provider and the KiCad team. As a third-party developer, I cannot submit to the official PCM without such a contract.

However, you can still easily install this plugin via:
- **Custom repository** in KiCad PCM (recommended)
- **Manual installation** from GitHub releases

### How do I update the plugin?

**If installed via custom repository:**
- The plugin will show update notifications in KiCad PCM
- Click "Update" when a new version is available

**If installed manually:**
- Check the [Releases page](https://github.com/hulryung/kicad-lcsc-manager/releases) for new versions
- Download and extract the new version to the same location
- Restart KiCad

### Does this work with KiCad 7 or 8?

This plugin is primarily developed and tested with KiCad 9.0. It may work with KiCad 7.0+ but is not officially tested or supported.

### The previews are not showing. What should I do?

Previews are fetched directly from EasyEDA's SVG API and displayed in a WebView. Make sure you have an internet connection. If a component has no preview data on EasyEDA, a placeholder message will be shown.

### Can I search for components without LCSC part numbers?

Yes! You can search by:
- Component name (e.g., "RP2040", "ATmega328")
- Component value (e.g., "10uF", "100k")
- Package type (e.g., "0603", "SOT23", "LQFN")
- Or any combination of these

### Are 3D models included?

Yes, both WRL (VRML) and STEP formats are downloaded when available. They are automatically linked to the footprint.

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 💬 Support

If you encounter any issues or have questions, please [open an issue](https://github.com/hulryung/kicad-lcsc-manager/issues) on GitHub.
