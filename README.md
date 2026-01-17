# KiCad LCSC Manager Plugin

A KiCad plugin that allows you to search and import electronic components from LCSC/EasyEDA and JLCPCB directly into your KiCad projects, including symbols, footprints, and 3D models.

## ✨ Features

### Advanced Component Search (v0.2.0)
- 🔍 **Multi-parameter search**: Search by component name, value, package type, and manufacturer
- 📊 **Rich search results**: View LCSC ID, name, package, price, stock, and library type (Basic/Extended)
- 🔀 **Sortable columns**: Click column headers to sort results by any field
- 👁️ **High-quality previews**:
  - Symbol preview using KiCad's native rendering
  - Footprint preview using KiCad's native rendering
  - 5x supersampling for crisp, clear images
- ⚡ **Asynchronous loading**: Non-blocking UI for smooth navigation
- 💾 **Preview caching**: Better performance with cached previews
- ⌨️ **Enter key support**: Quick search with Enter key

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
     C:\Users\[USERNAME]\Documents\KiCad\9.0\scripting\plugins\
     ```
   - **macOS**:
     ```
     ~/Documents/KiCad/9.0/scripting/plugins/
     ```
   - **Linux**:
     ```
     ~/.local/share/kicad/9.0/scripting/plugins/
     ```

3. **Install Python dependencies**

   The plugin requires additional Python packages. Install them using KiCad's Python:

   **macOS**:
   ```bash
   /Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3 -m pip install --user requests pydantic Pillow cairosvg
   ```

   **Windows** (PowerShell):
   ```powershell
   & "C:\Program Files\KiCad\9.0\bin\python.exe" -m pip install --user requests pydantic Pillow cairosvg
   ```

   **Linux**:
   ```bash
   pip3 install --user requests pydantic Pillow cairosvg
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
   - **Symbol tab**: High-quality symbol preview rendered by KiCad
   - **Footprint tab**: High-quality footprint preview rendered by KiCad
   - Previews load asynchronously - you can continue browsing while loading

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

## 📋 Requirements

- **KiCad**: 9.0 or later (recommended)
  - May work with KiCad 7.0+ but not officially tested
- **Python**: 3.9+ (bundled with KiCad)
- **Python packages**:
  - `requests>=2.31.0` - For API calls
  - `pydantic>=2.5.0` - For data validation
  - `Pillow>=10.0.0` - For image processing
  - `cairosvg>=2.7.0` - For SVG to PNG conversion
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
├── tests/                   # Unit tests
├── requirements.txt         # Python dependencies
└── README.md               # This file
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

This plugin is inspired by and references:
- [easyeda2kicad.py](https://github.com/uPesy/easyeda2kicad.py) - CLI tool for converting LCSC components
- [easyeda2kicad_plugin](https://github.com/rasmushauschild/easyeda2kicad_plugin) - KiCad plugin wrapper
- [KiCAD-EasyEDA-Parts](https://github.com/Yanndroid/KiCAD-EasyEDA-Parts) - Alternative implementation

## License

MIT License - see LICENSE file for details

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

This plugin is primarily developed and tested with KiCad 9.0. It may work with KiCad 7.0+ but is not officially tested or supported. Some features (especially preview rendering) require KiCad 9.0.

### The previews are not showing. What should I do?

Make sure you have installed all Python dependencies, especially:
- `Pillow` - For image processing
- `cairosvg` - For SVG to PNG conversion

Also ensure that KiCad CLI is available at the standard location (`kicad-cli` command).

### Can I search for components without LCSC part numbers?

Yes! Version 0.2.0 introduced advanced search. You can search by:
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
