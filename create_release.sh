#!/bin/bash
# Create a release package for KiCad PCM distribution

set -e

VERSION="0.1.0"
PACKAGE_NAME="kicad-lcsc-manager-${VERSION}"
RELEASE_DIR="release"
PACKAGE_DIR="${RELEASE_DIR}/${PACKAGE_NAME}"

echo "Creating KiCad PCM release package: ${PACKAGE_NAME}"
echo "================================================"

# Clean previous build
if [ -d "${RELEASE_DIR}" ]; then
    echo "Cleaning previous build..."
    rm -rf "${RELEASE_DIR}"
fi

# Create package directory
echo "Creating package directory..."
mkdir -p "${PACKAGE_DIR}"

# Copy plugin files
echo "Copying plugin files..."
cp -r plugins "${PACKAGE_DIR}/"

# Copy resources
echo "Copying resources..."
cp -r resources "${PACKAGE_DIR}/"

# Copy metadata
echo "Copying metadata..."
cp metadata.json "${PACKAGE_DIR}/"

# Copy documentation
echo "Copying documentation..."
cp README.md "${PACKAGE_DIR}/"
cp LICENSE "${PACKAGE_DIR}/"
cp INSTALL.md "${PACKAGE_DIR}/"

# Clean Python cache files
echo "Cleaning Python cache..."
find "${PACKAGE_DIR}" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find "${PACKAGE_DIR}" -type f -name "*.pyc" -delete 2>/dev/null || true
find "${PACKAGE_DIR}" -type f -name "*.pyo" -delete 2>/dev/null || true

# Create ZIP archive
echo "Creating ZIP archive..."
cd "${RELEASE_DIR}"
zip -r "${PACKAGE_NAME}.zip" "${PACKAGE_NAME}" -x "*.DS_Store"
cd ..

# Calculate SHA256
echo "Calculating SHA256 hash..."
if [[ "$OSTYPE" == "darwin"* ]]; then
    SHA256=$(shasum -a 256 "${RELEASE_DIR}/${PACKAGE_NAME}.zip" | cut -d' ' -f1)
else
    SHA256=$(sha256sum "${RELEASE_DIR}/${PACKAGE_NAME}.zip" | cut -d' ' -f1)
fi

echo ""
echo "================================================"
echo "Release package created successfully!"
echo "================================================"
echo "Package: ${RELEASE_DIR}/${PACKAGE_NAME}.zip"
echo "SHA256:  ${SHA256}"
echo ""
echo "Next steps:"
echo "1. Update metadata.json with the SHA256 hash above"
echo "2. Create a GitHub release and upload the ZIP file"
echo "3. Update the download_url in metadata.json"
echo "4. (Optional) Submit to KiCad PCM repository:"
echo "   https://gitlab.com/kicad/addons/metadata"
echo ""
