#!/usr/bin/env python3
"""
Assemble the IPC API plugin folder (#19): the plugin package plus
ipc/plugin.json and ipc/requirements.txt. This is what the IPC build puts
under plugins/ in its package zip.

Usage:
    python3 scripts/assemble-ipc-plugin.py <dest>

To try it in KiCad 10 (with the API server enabled), assemble into the user
plugin folder, e.g. ~/Documents/KiCad/10.0/plugins/lcsc-manager, and restart
KiCad.
"""
import json
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PACKAGE_DIR = REPO / "plugins" / "lcsc_manager"
IPC_DIR = REPO / "ipc"
IPC_FILES = ("plugin.json", "requirements.txt")


def missing_files(folder: Path):
    """Files the folder's plugin.json refers to that aren't there."""
    config = json.loads((folder / "plugin.json").read_text(encoding="utf-8"))
    wanted = set()
    for action in config["actions"]:
        wanted.add(action["entrypoint"])
        wanted.update(action.get("icons-light", []))
        wanted.update(action.get("icons-dark", []))
    return sorted(p for p in wanted if not (folder / p).is_file())


def assemble(dest: Path) -> Path:
    if dest.exists():
        raise SystemExit(f"{dest} already exists; remove it first")
    shutil.copytree(PACKAGE_DIR, dest,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store"))
    for name in IPC_FILES:
        shutil.copy2(IPC_DIR / name, dest / name)
    missing = missing_files(dest)
    if missing:
        shutil.rmtree(dest)
        raise SystemExit("plugin.json refers to missing files: " + ", ".join(missing))
    return dest


def main(argv) -> int:
    if len(argv) != 2:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    dest = assemble(Path(argv[1]).expanduser())
    print(f"Assembled the IPC plugin in {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
