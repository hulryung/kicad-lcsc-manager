# Installation Guide

## Installation Methods

### Method 1: Custom Repository in the Plugin and Content Manager (Recommended)

This plugin is **not in the official KiCad PCM repository** and cannot be — KiCad's
[commercial services policy](https://dev-docs.kicad.org/en/addons/index.html#_commercial_services)
requires a formal contract for add-ons that integrate directly with a commercial
API such as LCSC/JLCPCB. Adding the project's own repository gives you the same
one-click install and update notifications.

1. Open the **Plugin and Content Manager**
   - From the **main KiCad window** (the project launcher), click the
     **Plugin and Content Manager** button, **or**
   - From an editor, go to **Tools → Plugin and Content Manager**
2. Click **Manage...** (bottom-left)
3. Click **Add Repository**, paste this URL, and click **OK**:
   ```
   https://raw.githubusercontent.com/hulryung/kicad-lcsc-manager/main/repository.json
   ```
4. Close the repository manager, then switch the **repository dropdown** at the
   top of the PCM to **LCSC Manager**
5. Select **LCSC Manager**, click **Install**, then **Apply Pending Changes**
6. Restart KiCad completely

Every release comes in two builds, and the repository offers the one that fits
your KiCad: KiCad 9 and 10 get the 0.x build, KiCad 11 (and its nightlies) the
1.x build, which runs through KiCad's IPC API. When you install that one, KiCad
offers to turn on its API server; say yes, or turn it on later under
**Preferences → Plugins**.

### Method 2: Manual Installation

These steps are for KiCad 9 and 10. For KiCad 11, download the release's
`-ipc.zip` and install it with the Plugin and Content Manager's
**Install from File…**.

#### Step 1: Locate Your KiCad Plugins Directory

Replace `<KICAD_VERSION>` with the version you run — `9.0`, `10.0`, and so on.
Either of these directories works; the PCM installs into the first.

**Windows:**
```
C:\Users\[USERNAME]\Documents\KiCad\<KICAD_VERSION>\3rdparty\plugins\
C:\Users\[USERNAME]\Documents\KiCad\<KICAD_VERSION>\scripting\plugins\
```

**macOS:**
```
~/Documents/KiCad/<KICAD_VERSION>/3rdparty/plugins/
~/Documents/KiCad/<KICAD_VERSION>/scripting/plugins/
```

**Linux:**
```
~/.local/share/kicad/<KICAD_VERSION>/3rdparty/plugins/
~/.local/share/kicad/<KICAD_VERSION>/scripting/plugins/
```

#### Step 2: Find Your Plugins Directory in KiCad

If you're unsure of the exact path:

1. Open KiCad PCB Editor
2. Go to **Tools → External Plugins → Reveal Plugin Folder in Finder**
   (**Open Plugin Directory** on Windows/Linux)

#### Step 3: Install the Plugin

Whichever option you use, the plugin must end up as a directory named
**`lcsc_manager`** sitting directly in your plugins directory, with
`__init__.py` inside it. KiCad loads plugin *packages* by directory name, so a
folder called anything else — `kicad-lcsc-manager`, or `plugins` — is ignored.

**Option A: From a Git clone**

Clone anywhere *outside* the plugins directory, then copy the module in.
Cloning straight into the plugins directory does **not** work: it produces a
`kicad-lcsc-manager/` folder with no `__init__.py` at its top level, which
KiCad skips.

```bash
git clone https://github.com/hulryung/kicad-lcsc-manager.git
cd kicad-lcsc-manager
./scripts/bundle-dependencies.sh    # fills lib/, which isn't in git
cp -R plugins/lcsc_manager [your-kicad-plugins-directory]/
```

**Option B: From a release ZIP**

The release ZIP is a **PCM package**, not a drop-in plugin folder: its
`plugins/` directory holds the module's *contents*, which the PCM unpacks into
`3rdparty/plugins/<package identifier>/`. Extracting the archive as-is into
your plugins directory leaves a folder literally named `plugins`, which KiCad
will not load ([#18](https://github.com/hulryung/kicad-lcsc-manager/issues/18)).

1. Download `kicad-lcsc-manager-x.x.x.zip` from
   [Releases](https://github.com/hulryung/kicad-lcsc-manager/releases)
2. Extract it somewhere temporary
3. Copy everything *inside* the ZIP's `plugins/` directory into a new
   `lcsc_manager` folder in your plugins directory

The archive's `metadata.json` and `resources/` are only used by the PCM; a
manual install doesn't need them.

**The final structure, either way:**
```
[kicad-plugins-directory]/
└── lcsc_manager/
    ├── __init__.py
    ├── plugin.py
    ├── dialog.py
    ├── dialog_search.py
    ├── dialog_bom.py
    ├── dialog_settings.py
    ├── api/
    ├── bom/
    ├── converters/
    ├── library/
    ├── utils/
    ├── vendor/
    ├── plugin_resources/
    └── lib/            ← bundled requests / urllib3
```

#### Step 4: Python Dependencies — Nothing to Install

`requests` and its dependencies ship inside the plugin under
`lcsc_manager/lib/`, pinned to versions that work with the Python bundled with
KiCad 9 and 10. There is nothing to `pip install`.

**Linux only — optional WebView backend.** Component previews need wxPython's
WebView component, which most distributions package separately. Without it the
search dialog works normally and only the previews are replaced by a
placeholder.

```bash
# Debian / Ubuntu
sudo apt install python3-wxgtk-webview4.0

# Fedora
sudo dnf install python3-wxpython4-webview

# Arch: python-wxpython bundles WebView; make sure webkit2gtk is installed
```

#### Step 5: Restart KiCad

Close and reopen KiCad for the plugin to be loaded.

## Verification

1. Open KiCad **PCB Editor** — on KiCad 9 and 10 the plugin runs there, not in
   the Schematic Editor, because their Python action-plugin API is pcbnew-only
   (the KiCad 11 build has a button in both editors)
2. Look for the LCSC Manager icon in the toolbar
3. Or go to **Tools → External Plugins** and check that **LCSC Manager** is
   listed

## Troubleshooting

### Plugin Not Showing Up

1. **Check the folder name**: the directory must be named `lcsc_manager`, with
   `__init__.py` and `plugin.py` directly inside it — not nested under another
   folder such as `plugins/` or `kicad-lcsc-manager/`
2. **Check the directory location**: see Step 1, and confirm the KiCad version
   in the path matches the KiCad you actually launched
3. **Refresh**: **Tools → External Plugins → Refresh Plugins**, or restart
   KiCad completely
4. **Check the logs**: see *Finding Logs* below, and KiCad's scripting console

### Import Errors

The plugin bundles its own dependencies, so import errors usually mean a
partial copy rather than a missing package:

1. Confirm `lcsc_manager/lib/` came along with the rest of the files
2. Check the log for the failing module name
3. On Linux, a missing `wx.html2` only disables previews — the dialog still
   opens and reports this itself

### Permission Errors

On Linux/macOS, you might need to set permissions:

```bash
chmod -R 755 [your-kicad-plugins-directory]/lcsc_manager
```

### Finding Logs

The plugin creates logs at:

**All Platforms:**
```
~/.kicad/lcsc_manager/logs/lcsc_manager.log
```

Check this file for detailed error messages.

## Uninstallation

**Installed via the PCM (Method 1):** open the Plugin and Content Manager, go
to the **Installed** tab, uninstall **LCSC Manager**, and click **Apply Pending
Changes**.

**Installed manually (Method 2):** delete the `lcsc_manager` directory from
your KiCad plugins folder.

Either way, to also remove the configuration and logs:

```bash
rm -rf ~/.kicad/lcsc_manager
```

Then restart KiCad.

## Next Steps

Once installed, check out the [Usage Guide](README.md#usage) to learn how to
import components.
