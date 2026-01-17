#!/usr/bin/env python3
"""
Update metadata files for KiCad PCM custom repository.

This script updates metadata.json, packages.json, and repository.json
with information about a new package version.

Usage:
    python scripts/update-metadata.py <version> <package_file>

Example:
    python scripts/update-metadata.py 0.3.0 release/kicad-lcsc-manager-0.3.0.zip
"""

import sys
import json
import hashlib
from datetime import datetime
from pathlib import Path


def calculate_sha256(file_path: Path) -> str:
    """Calculate SHA256 hash of a file."""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def get_file_size(file_path: Path) -> int:
    """Get file size in bytes."""
    return file_path.stat().st_size


def update_metadata_json(version: str, sha256: str, size: int) -> None:
    """Update metadata.json in repository root."""
    metadata_file = Path("metadata.json")

    if not metadata_file.exists():
        print(f"ERROR: {metadata_file} not found")
        sys.exit(1)

    with open(metadata_file, 'r') as f:
        metadata = json.load(f)

    # Check if version already exists
    existing_versions = [v['version'] for v in metadata['versions']]

    # Create new version entry
    new_version = {
        "version": version,
        "status": "stable",
        "kicad_version": "9.0",
        "download_url": f"https://github.com/hulryung/kicad-lcsc-manager/releases/download/v{version}/kicad-lcsc-manager-{version}.zip",
        "download_sha256": sha256,
        "download_size": size,
        "install_size": 250000
    }

    # Update or add version
    if version in existing_versions:
        print(f"Updating existing version {version} in metadata.json")
        for i, v in enumerate(metadata['versions']):
            if v['version'] == version:
                metadata['versions'][i] = new_version
                break
    else:
        print(f"Adding new version {version} to metadata.json")
        metadata['versions'].insert(0, new_version)

    # Write updated metadata
    with open(metadata_file, 'w') as f:
        json.dump(metadata, f, indent=2)
        f.write('\n')

    print(f"✓ Updated {metadata_file}")


def update_packages_json(version: str, sha256: str, size: int) -> None:
    """Update packages.json."""
    packages_file = Path("packages.json")

    if not packages_file.exists():
        print(f"ERROR: {packages_file} not found")
        sys.exit(1)

    with open(packages_file, 'r') as f:
        packages_data = json.load(f)

    # Update first package (should only be one)
    package = packages_data['packages'][0]

    # Check if version exists
    existing_versions = [v['version'] for v in package['versions']]

    new_version = {
        "version": version,
        "status": "stable",
        "kicad_version": "9.0",
        "download_url": f"https://github.com/hulryung/kicad-lcsc-manager/releases/download/v{version}/kicad-lcsc-manager-{version}.zip",
        "download_sha256": sha256,
        "download_size": size,
        "install_size": 250000
    }

    if version in existing_versions:
        print(f"Updating existing version {version} in packages.json")
        for i, v in enumerate(package['versions']):
            if v['version'] == version:
                package['versions'][i] = new_version
                break
    else:
        print(f"Adding new version {version} to packages.json")
        package['versions'].insert(0, new_version)

    # Write updated packages
    with open(packages_file, 'w') as f:
        json.dump(packages_data, f, indent=2)
        f.write('\n')

    print(f"✓ Updated {packages_file}")


def update_repository_json() -> None:
    """Update repository.json with new packages.json hash."""
    packages_file = Path("packages.json")
    repository_file = Path("repository.json")

    if not repository_file.exists():
        print(f"ERROR: {repository_file} not found")
        sys.exit(1)

    # Calculate packages.json SHA256
    packages_sha256 = calculate_sha256(packages_file)

    # Get current UTC time
    now = datetime.utcnow()
    update_time = now.strftime('%Y-%m-%d %H:%M:%S')
    update_timestamp = int(now.timestamp())

    # Read repository.json
    with open(repository_file, 'r') as f:
        repo = json.load(f)

    # Update packages info
    repo['packages']['sha256'] = packages_sha256
    repo['packages']['update_time_utc'] = update_time
    repo['packages']['update_timestamp'] = update_timestamp

    # Write updated repository.json
    with open(repository_file, 'w') as f:
        json.dump(repo, f, indent=2)
        f.write('\n')

    print(f"✓ Updated {repository_file}")
    print(f"  packages.json SHA256: {packages_sha256}")
    print(f"  Update time: {update_time}")


def main():
    if len(sys.argv) != 3:
        print("Usage: python scripts/update-metadata.py <version> <package_file>")
        print("Example: python scripts/update-metadata.py 0.3.0 release/kicad-lcsc-manager-0.3.0.zip")
        sys.exit(1)

    version = sys.argv[1]
    package_file = Path(sys.argv[2])

    # Validate version format
    parts = version.split('.')
    if len(parts) != 3 or not all(p.isdigit() for p in parts):
        print(f"ERROR: Invalid version format '{version}'. Use semantic versioning (e.g., 1.0.0)")
        sys.exit(1)

    # Check if package file exists
    if not package_file.exists():
        print(f"ERROR: Package file not found: {package_file}")
        sys.exit(1)

    print(f"Updating metadata for version {version}")
    print(f"Package: {package_file}")
    print()

    # Calculate package hash and size
    print("Calculating package SHA256 and size...")
    sha256 = calculate_sha256(package_file)
    size = get_file_size(package_file)

    print(f"  SHA256: {sha256}")
    print(f"  Size: {size} bytes")
    print()

    # Update all metadata files
    update_metadata_json(version, sha256, size)
    update_packages_json(version, sha256, size)
    update_repository_json()

    print()
    print("=" * 60)
    print("✓ All metadata files updated successfully!")
    print("=" * 60)
    print()
    print("Next steps:")
    print("  1. Review the changes:")
    print("     git diff metadata.json packages.json repository.json")
    print()
    print("  2. Commit and push:")
    print(f"     git add metadata.json packages.json repository.json")
    print(f'     git commit -m "Release v{version}"')
    print("     git push")
    print()


if __name__ == "__main__":
    main()
