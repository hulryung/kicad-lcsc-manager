#!/bin/bash
#
# KiCad PCM Package Builder
#
# Builds a release's packages locally exactly as the release workflow does:
# refreshes the bundled dependencies, then builds the SWIG zip (KiCad 9/10)
# and the IPC zip (KiCad 11) with scripts/build-packages.py, which checks
# both. See scripts/pcm_builds.py for how the two are versioned.
#
# Usage:
#   ./scripts/package.sh <version> [<outdir>]      (default outdir: release)
#
# Example:
#   ./scripts/package.sh 0.9.0
#
# To publish, push a tag instead (git tag v0.9.0 && git push origin v0.9.0):
# the release workflow builds, uploads and records the packages itself.

set -euo pipefail

if [ $# -lt 1 ] || [ $# -gt 2 ]; then
    echo "Usage: $0 <version> [<outdir>]" >&2
    exit 1
fi

cd "$(dirname "$0")/.."
echo "→ Bundling Python dependencies (scripts/bundle-dependencies.sh)"
./scripts/bundle-dependencies.sh > /dev/null
echo "→ Building packages"
python3 scripts/build-packages.py "$1" "${2:-release}"
