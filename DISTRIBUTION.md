# Distribution Guide for KiCad PCM

This guide explains how to package and distribute the LCSC Manager plugin through KiCad's Plugin and Content Manager (PCM).

## Overview

KiCad PCM uses a standardized package format with metadata to distribute plugins. This plugin is already configured for PCM distribution.

## Package Structure

```
kicad-lcsc-manager-0.1.0/
├── plugins/
│   └── lcsc_manager/          # Plugin code
├── resources/
│   └── icon.png               # 64x64 plugin icon
├── metadata.json              # PCM metadata
├── README.md                  # Documentation
├── LICENSE                    # MIT License
└── INSTALL.md                 # Installation guide
```

## Creating a Release Package

### 1. Update Version Number

Update the version in the following files:
- `plugins/lcsc_manager/__init__.py` - `__version__`
- `metadata.json` - `versions[0].version`

### 2. Generate Release Package

Run the release script:

```bash
./create_release.sh
```

This will:
- Create a clean package directory
- Copy all necessary files
- Remove Python cache files
- Create a ZIP archive
- Calculate SHA256 hash

### 3. Update metadata.json

After creating the release package, update `metadata.json` with:

```json
{
  "versions": [
    {
      "version": "0.1.0",
      "download_sha256": "PASTE_SHA256_HASH_HERE",
      "download_url": "https://github.com/hulryung/kicad-lcsc-manager/releases/download/v0.1.0/kicad-lcsc-manager-0.1.0.zip",
      "download_size": FILE_SIZE_IN_BYTES
    }
  ]
}
```

### 4. Create GitHub Release

1. Go to https://github.com/hulryung/kicad-lcsc-manager/releases
2. Click "Create a new release"
3. Tag version: `v0.1.0`
4. Release title: `LCSC Manager v0.1.0`
5. Description: List of features and changes
6. Upload the ZIP file: `release/kicad-lcsc-manager-0.1.0.zip`
7. Publish release

### 5. Test Installation

Test the package locally:

1. Copy ZIP to a test location
2. Extract and verify contents
3. Install in KiCad plugins directory
4. Test all functionality

## Submitting to Official KiCad Repository (Optional)

To make the plugin available in KiCad's official PCM:

### 1. Fork the Metadata Repository

```bash
git clone https://gitlab.com/kicad/addons/metadata.git
cd metadata/packages
```

### 2. Add Your Plugin Metadata

Create `com.github.hulryung.kicad-lcsc-manager.json`:

```bash
cp ../../metadata.json com.github.hulryung.kicad-lcsc-manager.json
```

### 3. Submit Merge Request

1. Commit your metadata file
2. Push to your fork
3. Create a merge request to the official repository
4. Wait for review and approval

## Metadata Schema

The `metadata.json` follows KiCad's PCM schema v1:
- Schema: https://go.kicad.org/pcm/schemas/v1
- Docs: https://dev-docs.kicad.org/en/addons/

### Required Fields

- `name`: Plugin name (shown in PCM)
- `description`: Short description (one line)
- `description_full`: Detailed description
- `identifier`: Unique identifier (reverse domain notation)
- `type`: "plugin" for Python plugins
- `author`: Author information
- `license`: License type (MIT)
- `versions`: Array of version objects

### Version Object Fields

- `version`: Semantic version (e.g., "0.1.0")
- `status`: "stable", "testing", or "deprecated"
- `kicad_version`: Minimum KiCad version
- `download_url`: Direct download link
- `download_sha256`: SHA256 hash of ZIP file
- `download_size`: File size in bytes
- `install_size`: Installed size in bytes

## Version Numbering

Follow [Semantic Versioning](https://semver.org/):

- **MAJOR.MINOR.PATCH** (e.g., 1.0.0)
- **MAJOR**: Breaking changes
- **MINOR**: New features (backward compatible)
- **PATCH**: Bug fixes

## Testing Checklist

Before releasing:

- [ ] All tests pass
- [ ] Plugin loads in KiCad
- [ ] All features work correctly
- [ ] Documentation is up to date
- [ ] Version numbers are consistent
- [ ] ZIP package structure is correct
- [ ] SHA256 hash matches
- [ ] Installation instructions tested

## Distribution Channels

1. **GitHub Releases**: Primary distribution
2. **KiCad PCM**: Official plugin repository (after approval)
3. **Manual Download**: Direct ZIP download from GitHub

## Support and Updates

- Issues: https://github.com/hulryung/kicad-lcsc-manager/issues
- Releases: https://github.com/hulryung/kicad-lcsc-manager/releases
- Documentation: https://github.com/hulryung/kicad-lcsc-manager

## License

This plugin is distributed under the MIT License. See LICENSE file.
