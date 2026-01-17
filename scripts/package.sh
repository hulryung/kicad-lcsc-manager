#!/bin/bash
#
# KiCad PCM Package Builder
#
# This script creates a properly formatted package ZIP for KiCad PCM distribution.
# It handles the correct directory structure, excludes cache files, and calculates
# checksums.
#
# Usage:
#   ./scripts/package.sh <version>
#
# Example:
#   ./scripts/package.sh 0.3.0
#

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Functions
print_error() {
    echo -e "${RED}ERROR: $1${NC}" >&2
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_info() {
    echo -e "${YELLOW}→ $1${NC}"
}

# Check arguments
if [ $# -ne 1 ]; then
    print_error "Version number required"
    echo "Usage: $0 <version>"
    echo "Example: $0 0.3.0"
    exit 1
fi

VERSION=$1
PACKAGE_NAME="kicad-lcsc-manager"
STAGING_DIR="release/${PACKAGE_NAME}-${VERSION}"
ZIP_FILE="release/${PACKAGE_NAME}-${VERSION}.zip"

# Validate version format (semantic versioning)
if ! [[ $VERSION =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    print_error "Invalid version format. Use semantic versioning (e.g., 1.0.0)"
    exit 1
fi

print_info "Building package ${PACKAGE_NAME} version ${VERSION}"
echo ""

# Clean up any existing build
if [ -d "$STAGING_DIR" ]; then
    print_info "Cleaning up existing staging directory"
    rm -rf "$STAGING_DIR"
fi

if [ -f "$ZIP_FILE" ]; then
    print_info "Removing existing ZIP file"
    rm -f "$ZIP_FILE"
fi

# Create staging directory
print_info "Creating staging directory structure"
mkdir -p "${STAGING_DIR}"/{plugins,resources}
print_success "Directory structure created"

# Copy plugin files (excluding cache)
print_info "Copying plugin files"
if ! rsync -av \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='.pytest_cache' \
    --exclude='*.egg-info' \
    --exclude='.DS_Store' \
    plugins/ "${STAGING_DIR}/plugins/" > /dev/null; then
    print_error "Failed to copy plugin files"
    exit 1
fi
print_success "Plugin files copied"

# Copy icon
print_info "Copying resources"
if [ ! -f "resources/icon.png" ]; then
    print_error "Icon file not found at resources/icon.png"
    exit 1
fi
cp resources/icon.png "${STAGING_DIR}/resources/"
print_success "Resources copied"

# Verify icon exists in plugin resources
if [ ! -f "plugins/lcsc_manager/resources/icon.png" ]; then
    print_error "Plugin icon not found at plugins/lcsc_manager/resources/icon.png"
    echo "The icon must exist in both locations:"
    echo "  - resources/icon.png (for PCM display)"
    echo "  - plugins/lcsc_manager/resources/icon.png (for toolbar)"
    exit 1
fi

# Create package metadata.json
print_info "Creating package metadata.json"
cat > "${STAGING_DIR}/metadata.json" << EOF
{
  "\$schema": "https://go.kicad.org/pcm/schemas/v1",
  "name": "LCSC Manager",
  "description": "Import components from LCSC/EasyEDA with symbols, footprints, and 3D models",
  "description_full": "A KiCad plugin that allows you to search and import electronic components from LCSC/EasyEDA and JLCPCB directly into your KiCad projects. Features include automatic download of symbols, footprints, and 3D models (both WRL and STEP formats), integration with JLCPCB API for real-time stock and pricing information, and seamless addition to project-specific libraries.",
  "identifier": "com.github.hulryung.kicad-lcsc-manager",
  "type": "plugin",
  "author": {
    "name": "hulryung",
    "contact": {
      "web": "https://github.com/hulryung/kicad-lcsc-manager"
    }
  },
  "license": "MIT",
  "resources": {
    "homepage": "https://github.com/hulryung/kicad-lcsc-manager",
    "repository": "https://github.com/hulryung/kicad-lcsc-manager"
  },
  "versions": [
    {
      "version": "${VERSION}",
      "status": "stable",
      "kicad_version": "9.0"
    }
  ]
}
EOF
print_success "Metadata created"

# Create ZIP archive
print_info "Creating ZIP archive"
cd "${STAGING_DIR}"
if ! zip -r "../${PACKAGE_NAME}-${VERSION}.zip" . > /dev/null 2>&1; then
    print_error "Failed to create ZIP archive"
    exit 1
fi
cd ../..
print_success "ZIP archive created"

# Verify package structure
print_info "Verifying package structure"
echo ""
echo "=== Package Contents (first 30 files) ==="
unzip -l "${ZIP_FILE}" | head -33

# Check for unwanted files
echo ""
if unzip -l "${ZIP_FILE}" | grep -q '__pycache__'; then
    print_error "Package contains __pycache__ directories!"
    exit 1
fi

if unzip -l "${ZIP_FILE}" | grep -q '\.pyc'; then
    print_error "Package contains .pyc files!"
    exit 1
fi

print_success "Package structure verified"

# Calculate checksums
echo ""
print_info "Calculating checksums"

# Detect OS for stat command
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    SIZE=$(stat -f%z "${ZIP_FILE}")
else
    # Linux
    SIZE=$(stat -c%s "${ZIP_FILE}")
fi

if command -v sha256sum &> /dev/null; then
    SHA256=$(sha256sum "${ZIP_FILE}" | awk '{print $1}')
elif command -v shasum &> /dev/null; then
    SHA256=$(shasum -a 256 "${ZIP_FILE}" | awk '{print $1}')
else
    print_error "No SHA256 tool found (need sha256sum or shasum)"
    exit 1
fi

echo ""
echo "════════════════════════════════════════════════════════════"
print_success "Package built successfully!"
echo "════════════════════════════════════════════════════════════"
echo ""
echo "Package: ${ZIP_FILE}"
echo "Version: ${VERSION}"
echo "Size:    ${SIZE} bytes"
echo "SHA256:  ${SHA256}"
echo ""
echo "Next steps:"
echo "  1. Upload package to GitHub release:"
echo "     gh release create v${VERSION} ${ZIP_FILE}"
echo ""
echo "  2. Update metadata.json with:"
echo "     - download_sha256: ${SHA256}"
echo "     - download_size: ${SIZE}"
echo ""
echo "  3. Update packages.json with the same values"
echo ""
echo "  4. Update repository.json with new packages.json SHA256"
echo ""
echo "  5. Commit and push changes"
echo ""
echo "Or use the automated GitHub Action by pushing a tag:"
echo "  git tag v${VERSION}"
echo "  git push origin v${VERSION}"
echo ""
