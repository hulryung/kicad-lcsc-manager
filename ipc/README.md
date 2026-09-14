# IPC API plugin files

KiCad 11 drops the SWIG Python API that `plugins/lcsc_manager/plugin.py`
uses; plugins run through the IPC API instead (#19). These files turn the
same plugin package into an IPC plugin:

- `plugin.json`: tells KiCad about the plugin and its toolbar action. The
  action runs `ipc_main.py` from the plugin folder.
- `requirements.txt`: what KiCad pip-installs into the plugin's own Python
  environment (just kicad-python; everything else is bundled under `lib/`).

They're kept out of `plugins/lcsc_manager/` on purpose. The SWIG build ships
that folder as-is, and a package with `plugin.json` next to its `__init__.py`
doesn't register the SWIG plugin, so KiCad 10 doesn't show two buttons for it.

Assemble the IPC plugin folder with:

    python3 scripts/assemble-ipc-plugin.py <dest>

Releases ship it as the IPC build: tag `vX.Y.Z` publishes it as version
`(X+1).Y.Z` for KiCad 11, next to the SWIG build `X.Y.Z` for KiCad 9 and 10
(`scripts/build-packages.py`; see `docs/PACKAGING.md`).

To try it with KiCad 10: enable the API server (Preferences → Plugins),
assemble into the user plugin folder (for example
`~/Documents/KiCad/10.0/plugins/lcsc-manager` on macOS), and restart KiCad.
KiCad creates the plugin's Python environment and installs `requirements.txt`
in the background; the LCSC Manager button appears in the PCB and Schematic
Editor toolbars. The plugin logs to `~/.kicad/lcsc_manager/logs/lcsc_manager.log`.
