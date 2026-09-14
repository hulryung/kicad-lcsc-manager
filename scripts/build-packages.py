#!/usr/bin/env python3
"""
Build a release's package zips (#19): the SWIG build for KiCad 9 and 10 and
the IPC build for KiCad 11. See pcm_builds.py for how they're versioned.

Usage:
    python3 scripts/build-packages.py <version> [<outdir>]     (default: release)

Writes each zip and <outdir>/builds.json, which lists every build's PCM
entry and zip. Each zip is checked after it's built. Run
scripts/bundle-dependencies.sh first to fill plugins/lcsc_manager/lib, as the
release workflow does.
"""
import sys
from pathlib import Path

from pcm_builds import build_packages


def main(argv) -> int:
    if len(argv) not in (2, 3):
        print(__doc__.strip(), file=sys.stderr)
        return 2
    outdir = Path(argv[2] if len(argv) == 3 else "release")
    try:
        described = build_packages(argv[1], outdir)
    except ValueError as e:
        raise SystemExit(f"error: {e}")
    for build in described:
        kicad = f"KiCad {build['kicad_version']}" + (
            f" to {build['kicad_version_max']}" if build.get("kicad_version_max") else " and later")
        print(f"{build['zip']}: {build['runtime']} build {build['version']} for {kicad}, "
              f"{build['download_size']:,} bytes, sha256 {build['download_sha256']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
