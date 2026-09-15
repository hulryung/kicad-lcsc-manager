# Testing LCSC Manager

## Automated tests

Every `tests/test_*.py` is a plain script: `python3 tests/<file>.py`. Run
`./scripts/bundle-dependencies.sh` once first; it fills
`plugins/lcsc_manager/lib/` with the libraries the plugin ships with. Most
tests need nothing else. A few talk to LCSC, EasyEDA or JLCPCB and need
network access (`test_api_*`, `test_full_import_with_3d`, …). Some drive
**KiCad's bundled Python** and `kicad-cli` directly — no KiCad window, no GUI
automation — and are skipped on machines without KiCad:

- `test_kicad_resolves_tables.py` — builds a project through the real
  `LibraryManager`, places a footprint by library nickname, and has
  `kicad-cli pcb drc` resolve it through the tables the plugin wrote (the
  `lib_footprint_issues` check). It covers both the per-project table and the
  shared location's global table. `KICAD_CONFIG_HOME` points at a sandbox, so
  your real KiCad configuration is never touched. Offline; takes a few seconds.
- `test_kicad_host.py`, `test_ipc_prep.py` — host detection, the settings path
  and dialog construction under KiCad's own Python.

The same approach works for ad-hoc checks:

```bash
KPY=/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3
KICAD_CONFIG_HOME=/tmp/sandbox "$KPY" my_check.py           # pcbnew, wx, the plugin code
KICAD_CONFIG_HOME=/tmp/sandbox kicad-cli pcb drc --format json -o out.json board.kicad_pcb
```

### The IPC plugin (KiCad 11 port, #19)

`tests/test_ipc_plugin.py` needs only Python 3: it checks `ipc/plugin.json`
against KiCad's own identifier rule and schema, assembles the plugin folder,
runs `ipc_main.py` the way KiCad does (from a folder named like a Plugin and
Content Manager install, with a stub wx), and requires it to write nothing to
stdout/stderr, which KiCad would show as an error.

To open the real dialog in an IPC process **without KiCad running**, build the
plugin's environment the way KiCad does and point the plugin at
`tests/fake_kicad_api.py`, which stands in for KiCad's API server:

```bash
KPY=/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3
W=$(mktemp -d)
"$KPY" -m venv --system-site-packages "$W/venv"
"$W/venv/bin/python3" -m pip install --only-binary :all: -r ipc/requirements.txt
python3 scripts/assemble-ipc-plugin.py "$W/plugin"
mkdir "$W/proj" && echo '(kicad_pcb (version 20241229) (generator "pcbnew"))' > "$W/proj/demo.kicad_pcb"
"$W/venv/bin/python3" tests/fake_kicad_api.py tcp://127.0.0.1:5555 "$W/proj/demo.kicad_pcb" tok &
cd "$W/plugin" && HOME="$W/home" KICAD_CONFIG_HOME="$W/kicad-config" \
  KICAD_API_SOCKET=tcp://127.0.0.1:5555 KICAD_API_TOKEN=tok \
  "$W/venv/bin/python3" ipc_main.py
```

`HOME` and `KICAD_CONFIG_HOME` keep the plugin's settings, log and any library
tables out of your real ones. The plugin logs to
`$HOME/.kicad/lcsc_manager/logs/lcsc_manager.log`.

In **KiCad 10** itself, with nothing of yours touched: copy
`~/Library/Preferences/kicad/10.0` to a sandbox, set `api.enable_server` to
`true` in the copy's `kicad_common.json`, assemble the plugin into
`<docs>/KiCad/10.0/plugins/lcsc-manager`, and start pcbnew with
`KICAD_CONFIG_HOME`, `KICAD_DOCUMENTS_HOME=<docs>` and `KICAD_CACHE_HOME`
pointing into the sandbox. KiCad builds the plugin's environment under
`<cache>/KiCad/10.0/python-environments/com.github.hulryung.kicad-lcsc-manager`
and adds the LCSC Manager button after the scripting console button. With KiCad
running, `ipc_main.py` can also be started by hand against it
(`KICAD_API_SOCKET=ipc:///tmp/kicad/api.sock`, empty `KICAD_API_TOKEN`).

### Release packages

`tests/test_build_packages.py` builds both release ZIPs (the SWIG build for
KiCad 9/10 and the IPC build for KiCad 11, see `docs/PACKAGING.md`) and
checks their contents and metadata. It also checks that KiCad's own
compatibility rule offers each KiCad exactly one of them. It uses a
stand-in for the bundled dependencies, so it runs anywhere.

To try real release ZIPs, build them with `./scripts/package.sh <version>`.
Then use **Install from File…** in the Plugin and Content Manager of a
sandboxed KiCad (as above), or unpack a ZIP's `plugins/` the way the PCM
does, into `<docs>/KiCad/10.0/3rdparty/plugins/com_github_hulryung_kicad-lcsc-manager/`.
KiCad 10 loads both from there: the SWIG build appears under
*Tools → External Plugins*, and the IPC build gets its button without
appearing there.

**What still needs a running KiCad:** anything about the *live session*.
`pcbnew.GetBoard()` only returns the PCB editor window's board, so from a
command line it is always `None`. That means a script can't see what an open
session has loaded (e.g. whether a newly registered footprint library shows up
before the project is reopened), and can't act as the `SwigHost`. For those,
use **Tools → Scripting Console** inside the PCB Editor.

## Checking a build in KiCad

Before a release, a quick pass in KiCad itself, with a throwaway project:

1. Open a saved project and start LCSC Manager: from the PCB Editor on KiCad
   9 and 10; on KiCad 11, from the Schematic Editor too.
2. Search for `C2040` (the RP2040). The results show price, stock and type;
   selecting one shows its symbol, footprint and specifications.
3. Import it with symbol, footprint and 3D model. The dialog reports success
   and stays open, the files appear under `<project>/libs/lcsc/`, and the
   project's `sym-lib-table` and `fp-lib-table` list `lcsc_imported` and
   `lcsc_footprints`.
4. Without closing the dialog, import a second part, such as `C1525` (100 nF
   0402 capacitor) or `C25804` (10 kΩ 0603 resistor). The status line lists
   both.
5. Place them: the symbol from `lcsc_imported` in the Schematic Editor, the
   footprint from `lcsc_footprints` in the PCB Editor, then check the 3D view.
   On KiCad 10 and 11, reopen the project first if the dialog said so.
6. **Import BOM…** with a small BOM that has an `LCSC Part #` column (a JLCPCB
   assembly BOM does).
7. In **⚙ Settings…**, switch to a shared folder and import a part. Restart
   KiCad and check that the part is available in another project.

When something goes wrong, see [docs/DEBUG.md](docs/DEBUG.md).
