# KiCad PCM Custom Repository Packaging Guide

This guide explains how to package and distribute KiCad plugins through a custom PCM (Plugin and Content Manager) repository.

## Table of Contents

1. [Overview](#overview)
2. [Package Structure](#package-structure)
3. [Required Files](#required-files)
4. [Manual Packaging Process](#manual-packaging-process)
5. [Automated Packaging with GitHub Actions](#automated-packaging-with-github-actions)
6. [Testing](#testing)
7. [Troubleshooting](#troubleshooting)

## Overview

KiCad PCM supports custom repositories that allow distribution of plugins outside the official KiCad repository. This is useful for:
- Plugins that integrate with commercial APIs
- Third-party plugins not accepted in the official repository
- Internal/private plugin distribution

### Key Components

- **Package ZIP**: Contains plugin code, resources, and metadata
- **repository.json**: Main repository index file
- **packages.json**: List of available packages and versions
- **resources.zip**: Plugin icons for the PCM interface
- **metadata.json**: Package metadata (in repository root)

## Package Structure

### ZIP Archive Layout

The package ZIP file must have files at the root level (no top-level folder):

```
kicad-plugin-name-x.x.x.zip
├── plugins/
│   └── plugin_name/
│       ├── __init__.py          # Plugin registration
│       ├── plugin.py            # Main plugin code
│       ├── resources/
│       │   └── icon.png         # Plugin toolbar icon
│       └── ...                  # Other plugin files
├── resources/
│   └── icon.png                 # PCM display icon (64x64)
└── metadata.json                # Package metadata
```

**Important Notes:**
- Files must be at ZIP root, not in a top-level folder
- No `__pycache__` or `.pyc` files
- No development files (tests, docs, etc.)
- Plugin icon must be in both locations:
  - `plugins/plugin_name/resources/icon.png` - for toolbar
  - `resources/icon.png` - for PCM display

### Plugin Code Structure

```python
# plugins/plugin_name/__init__.py
from .plugin import MyPlugin
MyPlugin().register()

# plugins/plugin_name/plugin.py
import pcbnew

class MyPlugin(pcbnew.ActionPlugin):
    def defaults(self):
        self.name = "My Plugin"
        self.category = "Library"
        self.description = "Plugin description"
        self.show_toolbar_button = True
        self.icon_file_name = str(Path(__file__).parent / "resources" / "icon.png")

    def Run(self):
        # Plugin logic here
        pass
```

## Required Files

### 1. metadata.json (in repository root)

Contains all package versions and download information:

```json
{
  "$schema": "https://go.kicad.org/pcm/schemas/v1",
  "name": "Plugin Name",
  "description": "Short description",
  "description_full": "Longer description with features",
  "identifier": "com.github.username.plugin-name",
  "type": "plugin",
  "author": {
    "name": "Your Name",
    "contact": {
      "web": "https://github.com/username/plugin-name"
    }
  },
  "license": "MIT",
  "resources": {
    "homepage": "https://github.com/username/plugin-name",
    "repository": "https://github.com/username/plugin-name"
  },
  "versions": [
    {
      "version": "1.0.0",
      "status": "stable",
      "kicad_version": "9.0",
      "download_url": "https://github.com/username/plugin-name/releases/download/v1.0.0/plugin-name-1.0.0.zip",
      "download_sha256": "sha256_hash_here",
      "download_size": 123456,
      "install_size": 500000
    }
  ]
}
```

### 2. metadata.json (in package ZIP)

Simplified version with only current version info:

```json
{
  "$schema": "https://go.kicad.org/pcm/schemas/v1",
  "name": "Plugin Name",
  "description": "Short description",
  "description_full": "Longer description",
  "identifier": "com.github.username.plugin-name",
  "type": "plugin",
  "author": {
    "name": "Your Name",
    "contact": {
      "web": "https://github.com/username/plugin-name"
    }
  },
  "license": "MIT",
  "resources": {
    "homepage": "https://github.com/username/plugin-name",
    "repository": "https://github.com/username/plugin-name"
  },
  "versions": [
    {
      "version": "1.0.0",
      "status": "stable",
      "kicad_version": "9.0"
    }
  ]
}
```

### 3. packages.json

Referenced by repository.json, contains package list:

```json
{
  "packages": [
    {
      "$schema": "https://go.kicad.org/pcm/schemas/v1",
      "name": "Plugin Name",
      "description": "Short description",
      "description_full": "Longer description",
      "identifier": "com.github.username.plugin-name",
      "type": "plugin",
      "author": {
        "name": "Your Name",
        "contact": {
          "web": "https://github.com/username/plugin-name"
        }
      },
      "maintainer": {
        "name": "Your Name",
        "contact": {
          "web": "https://github.com/username/plugin-name"
        }
      },
      "license": "MIT",
      "resources": {
        "homepage": "https://github.com/username/plugin-name",
        "repository": "https://github.com/username/plugin-name"
      },
      "versions": [
        {
          "version": "1.0.0",
          "status": "stable",
          "kicad_version": "9.0",
          "download_url": "https://github.com/username/plugin-name/releases/download/v1.0.0/plugin-name-1.0.0.zip",
          "download_sha256": "sha256_hash_here",
          "download_size": 123456,
          "install_size": 500000
        }
      ]
    }
  ]
}
```

### 4. repository.json

Main entry point for the custom repository:

```json
{
  "$schema": "https://gitlab.com/kicad/code/kicad/-/raw/master/kicad/pcm/schemas/pcm.v1.schema.json#/definitions/Repository",
  "name": "My Plugin Repository",
  "maintainer": {
    "name": "Your Name",
    "contact": {
      "web": "https://github.com/username/plugin-name"
    }
  },
  "packages": {
    "url": "https://raw.githubusercontent.com/username/plugin-name/main/packages.json",
    "sha256": "packages_json_sha256_here",
    "update_time_utc": "2026-01-17 12:00:00",
    "update_timestamp": 1737115200
  },
  "resources": {
    "url": "https://github.com/username/plugin-name/raw/main/resources.zip",
    "sha256": "resources_zip_sha256_here",
    "update_time_utc": "2026-01-17 12:00:00",
    "update_timestamp": 1737115200
  }
}
```

### 5. resources.zip

Contains plugin icons for PCM display:

```
resources.zip
└── com.github.username.plugin-name/
    └── icon.png (64x64 PNG)
```

Create resources.zip:

```bash
mkdir -p com.github.username.plugin-name
cp resources/icon.png com.github.username.plugin-name/
zip -r resources.zip com.github.username.plugin-name/
```

## Manual Packaging Process

### Step 1: Prepare Package Directory

```bash
VERSION="1.0.0"
PACKAGE_NAME="plugin-name"
STAGING_DIR="release/${PACKAGE_NAME}-${VERSION}"

# Create staging directory
mkdir -p ${STAGING_DIR}/{plugins,resources}

# Copy plugin files (excluding cache files)
rsync -av --exclude='__pycache__' --exclude='*.pyc' \
  plugins/ ${STAGING_DIR}/plugins/

# Copy icon
cp resources/icon.png ${STAGING_DIR}/resources/
```

### Step 2: Create Package Metadata

Create simplified `metadata.json` in staging directory:

```bash
cat > ${STAGING_DIR}/metadata.json << 'EOF'
{
  "$schema": "https://go.kicad.org/pcm/schemas/v1",
  "name": "Plugin Name",
  "description": "Short description",
  "identifier": "com.github.username.plugin-name",
  "type": "plugin",
  "author": {
    "name": "Your Name",
    "contact": {"web": "https://github.com/username/plugin-name"}
  },
  "license": "MIT",
  "versions": [
    {
      "version": "1.0.0",
      "status": "stable",
      "kicad_version": "9.0"
    }
  ]
}
EOF
```

### Step 3: Create ZIP Package

```bash
cd ${STAGING_DIR}
zip -r ../${PACKAGE_NAME}-${VERSION}.zip .
cd ../..
```

Verify package structure:

```bash
unzip -l release/${PACKAGE_NAME}-${VERSION}.zip | head -20
```

Should show:
```
plugins/
plugins/plugin_name/
resources/
resources/icon.png
metadata.json
```

### Step 4: Calculate SHA256

```bash
shasum -a 256 release/${PACKAGE_NAME}-${VERSION}.zip
stat -f%z release/${PACKAGE_NAME}-${VERSION}.zip  # macOS
# or
stat -c%s release/${PACKAGE_NAME}-${VERSION}.zip  # Linux
```

### Step 5: Upload to GitHub Release

```bash
gh release create v${VERSION} \
  release/${PACKAGE_NAME}-${VERSION}.zip \
  --title "v${VERSION}" \
  --notes "Release notes here"
```

### Step 6: Update metadata.json (repository root)

Add or update version entry:

```json
{
  "version": "1.0.0",
  "status": "stable",
  "kicad_version": "9.0",
  "download_url": "https://github.com/username/plugin-name/releases/download/v1.0.0/plugin-name-1.0.0.zip",
  "download_sha256": "calculated_sha256_here",
  "download_size": 123456,
  "install_size": 500000
}
```

### Step 7: Update packages.json

Update the same version information in packages.json.

### Step 8: Update repository.json

```bash
# Calculate packages.json SHA256
shasum -a 256 packages.json

# Update repository.json with new SHA256 and timestamp
# Update "update_time_utc" and "update_timestamp"
```

### Step 9: Commit and Push

```bash
git add metadata.json packages.json repository.json
git commit -m "Release v${VERSION}"
git push
```

## Automated Packaging with GitHub Actions

See `.github/workflows/release.yml` for automated packaging on version tag push.

### Usage

1. Update version in your code
2. Create and push a version tag:
   ```bash
   git tag v1.0.0
   git push origin v1.0.0
   ```
3. GitHub Actions will automatically:
   - Build the package ZIP
   - Calculate SHA256
   - Create GitHub Release
   - Update metadata files
   - Commit and push updates

### Workflow Features

- Triggered by `v*.*.*` tags
- Excludes `__pycache__` and `.pyc` files
- Validates package structure
- Updates all metadata files
- Creates GitHub Release with notes

## Testing

### Test Custom Repository Locally

1. Start a local HTTP server:
   ```bash
   python3 -m http.server 8000
   ```

2. Update repository.json URLs to point to `http://localhost:8000`

3. Test in KiCad PCM

### Test in KiCad PCM

1. Open KiCad PCB Editor
2. Go to **Tools → Plugin and Content Manager**
3. Click **Manage** (bottom-left)
4. Click **Add Repository**
5. Enter repository URL:
   ```
   https://raw.githubusercontent.com/username/plugin-name/main/repository.json
   ```
6. Search for your plugin and install
7. Restart KiCad
8. Verify plugin appears in toolbar or Tools menu

## Troubleshooting

### Plugin Not Appearing in PCM

- Check repository.json is accessible
- Verify packages.json SHA256 matches
- Check JSON schema validation
- Ensure all required fields are present

### Plugin Installed But No Icon

- Verify icon exists in `plugins/plugin_name/resources/icon.png`
- Check icon file size (should be 64x64 PNG)
- Ensure `icon_file_name` path is correct in plugin code

### Package ZIP Structure Wrong

Common mistakes:
- Top-level folder in ZIP (wrong!)
- Files should be at ZIP root
- Check with: `unzip -l package.zip | head -20`

### SHA256 Mismatch

- Recalculate SHA256 after any changes
- Use `shasum -a 256 file.zip` (macOS/Linux)
- Use `certutil -hashfile file.zip SHA256` (Windows)
- Update all metadata files with new hash

### Import Errors

- Check Python dependencies are documented
- Verify plugin code has no syntax errors
- Check KiCad version compatibility
- Review plugin logs in `~/.kicad/lcsc_manager/` (if using logger)

## References

- [KiCad PCM Documentation](https://dev-docs.kicad.org/en/addons/)
- [KiCad PCM Schema](https://go.kicad.org/pcm/schemas/v1)
- [Bouni's KiCad Repository](https://github.com/Bouni/bouni-kicad-repository) (reference implementation)

## Best Practices

1. **Version Management**
   - Use semantic versioning (MAJOR.MINOR.PATCH)
   - Keep all versions in metadata.json for user rollback
   - Never modify released package ZIPs

2. **Testing**
   - Test package installation in fresh KiCad instance
   - Verify all features work after installation
   - Test on different platforms if possible

3. **Documentation**
   - Include README.md in repository
   - Document installation requirements
   - Provide usage examples

4. **Automation**
   - Use GitHub Actions for consistent packaging
   - Automate SHA256 calculation
   - Validate package structure in CI

5. **Maintenance**
   - Keep repository.json updated
   - Monitor GitHub releases
   - Respond to user issues promptly
