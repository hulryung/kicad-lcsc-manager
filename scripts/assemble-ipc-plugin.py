#!/usr/bin/env python3
"""
Assemble the IPC API plugin folder (#19): the plugin package plus
ipc/plugin.json and ipc/requirements.txt. This is what the IPC build puts
under plugins/ in its package zip (see build-packages.py).

Usage:
    python3 scripts/assemble-ipc-plugin.py <dest>

To try it in KiCad 10 (with the API server enabled), assemble into the user
plugin folder, e.g. ~/Documents/KiCad/10.0/plugins/lcsc-manager, and restart
KiCad.
"""
import sys
from pathlib import Path

from pcm_builds import assemble_ipc_plugin


def main(argv) -> int:
    if len(argv) != 2:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    try:
        dest = assemble_ipc_plugin(Path(argv[1]).expanduser())
    except (FileExistsError, ValueError) as e:
        raise SystemExit(str(e))
    print(f"Assembled the IPC plugin in {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
