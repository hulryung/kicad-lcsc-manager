# Debugging LCSC Manager

## The log

Everything the plugin does is logged to

```
~/.kicad/lcsc_manager/logs/lcsc_manager.log
```

on every platform (`~` is your home folder). Watch it while you use the
plugin with `tail -f ~/.kicad/lcsc_manager/logs/lcsc_manager.log`. The KiCad 11
build also sends its console output there, because KiCad would otherwise show
it as an error.

Settings live next to it in `~/.kicad/lcsc_manager/config.json`, and in
`<project>/.lcsc_manager.json` for a project that overrides them.

When you [open an issue](https://github.com/hulryung/kicad-lcsc-manager/issues),
please include:
- the relevant part of the log
- your KiCad version (**Help → About KiCad**) and operating system
- the plugin version (0.x or 1.x)
- what you did

## The plugin doesn't appear

### KiCad 9 and 10 (0.x build)

- It only appears in the **PCB Editor**: a toolbar button, and
  **Tools → External Plugins → LCSC Manager**.
- **Tools → External Plugins → Refresh Plugins** reloads plugins without
  restarting KiCad.
- If KiCad couldn't load the plugin, it keeps the Python traceback. Open
  **Preferences → Preferences… → PCB Editor → Action Plugins** and click
  **Show Plugin Errors**.
- **Tools → External Plugins → Reveal Plugin Folder** (**Open Plugin
  Directory** on Windows/Linux) shows where plugins are loaded from. A
  Plugin and Content Manager install is in
  `3rdparty/plugins/com_github_hulryung_kicad-lcsc-manager/`. A manual one
  must be a folder named `lcsc_manager` with `__init__.py` directly inside it
  (see [INSTALL.md](../INSTALL.md#troubleshooting)).

### KiCad 11 (1.x build)

- KiCad only runs IPC plugins with the API server on: **Preferences →
  Plugins → Enable KiCad API**. The button appears in both the PCB and the
  Schematic Editor.
- KiCad gives the plugin its own Python environment and installs
  `kicad-python` into it from the internet each time it loads the plugin. The
  environment lives in KiCad's cache folder, under
  `python-environments/com.github.hulryung.kicad-lcsc-manager`:
  `~/Library/Caches/kicad/<version>/` on macOS, `~/.cache/kicad/<version>/`
  on Linux. If that install failed (for example, offline), restart KiCad to
  retry.
- KiCad reports a plugin that fails to start (a non-zero exit code or
  output on its error stream) in the editor's warning messages, at the right
  of the status bar.
- You can start the entry point by hand against a running KiCad, as KiCad
  does, and watch the log. Use the environment's Python, from the plugin
  folder:

  ```bash
  cd <plugin folder>      # the folder that holds plugin.json
  <environment>/bin/python3 ipc_main.py
  ```

  Without `KICAD_API_SOCKET`, kicad-python connects to KiCad's default socket
  (`/tmp/kicad/api.sock` on macOS and Linux). To run it with no KiCad at all,
  see [TESTING.md](../TESTING.md#the-ipc-plugin-kicad-11-port-19).

## Searches or imports fail

The plugin talks to these services:

| What | Where |
| --- | --- |
| Search results, stock and prices | `jlcpcb.com` (JLCPCB's parts search) |
| Symbol and footprint data, previews | `easyeda.com/api/products/<LCSC number>/…` |
| 3D models (STEP and WRL) | `modules.easyeda.com` |

The log records every request and any error. Some parts exist in the LCSC
catalog but have no symbol or footprint in EasyEDA's library; the plugin
says so, and there's nothing to import for those.

To check a part without KiCad, from a checkout (after
`./scripts/bundle-dependencies.sh`):

```bash
python3 -c "
import sys; sys.path.insert(0, 'plugins')
from lcsc_manager.api.lcsc_api import get_api_client
part = get_api_client().search_component('C2040')
print('EasyEDA data:', bool(part and part.get('easyeda_data')))"
```

Behind a proxy, set `HTTPS_PROXY` (and `HTTP_PROXY`) in the environment KiCad
starts from; the plugin's HTTP library picks them up.

## Imported parts don't show up

KiCad doesn't always pick up a new library at once. The dialog tells you when
it hasn't:

- **Symbols:** reopen the Schematic Editor.
- **Footprints (KiCad 10 and 11):** reopen the project the first time it gets
  the footprint library.
- **Shared library folder:** restart KiCad after the first import.

The libraries are registered under these names:
- Inside a project: `lcsc_imported` (symbols) and `lcsc_footprints`
  (footprints) in the project's `sym-lib-table` and `fp-lib-table`.
- In the shared folder: `lcsc_shared` and `lcsc_shared_footprints` in
  KiCad's global tables (**Preferences → Manage Symbol/Footprint Libraries**).

If a row is missing or points somewhere unexpected, the log shows which
tables the plugin updated.

## Working on the plugin

- Run KiCad from your checkout: after `./scripts/bundle-dependencies.sh`,
  link `plugins/lcsc_manager` into the plugins folder as `lcsc_manager`, for
  example:

  ```bash
  ln -s "$PWD/plugins/lcsc_manager" ~/Documents/KiCad/10.0/3rdparty/plugins/lcsc_manager
  ```

  Then use **Refresh Plugins**, or restart KiCad, after a change. Remove any
  Plugin and Content Manager install first, or KiCad loads both.
- For the KiCad 11 build, assemble a plugin folder with
  `python3 scripts/assemble-ipc-plugin.py <dest>`; see [ipc/README.md](../ipc/README.md).
- Log through `get_logger()` (`utils/logger.py`). Debug-level messages go to
  the log file only.
- [TESTING.md](../TESTING.md) covers the automated tests and the headless
  checks against KiCad's own Python and `kicad-cli`.
