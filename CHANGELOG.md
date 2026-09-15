# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed
- **README rewritten for the current plugin.** Changes:
  - A new screenshot of today's search dialog.
  - Installation now covers the KiCad 11 build.
  - Usage covers both editors and when KiCad needs a reopen or restart.
  - The FAQ, requirements and project layout are up to date.
  - The credits were checked against the code. The table listed a `footprint_handlers.py` that no longer exists and 3D functions under names that don't.
  - Release notes now live only in CHANGELOG.md; the README's version banners are gone.
  - The stale instructions are gone: the uninstall script (it only knows KiCad 6–9's old plugin folders), `pip install -r requirements.txt` and `pytest`.
- INSTALL.md:
  - It covers the KiCad 11 build.
  - Installing from a git clone now runs `scripts/bundle-dependencies.sh` first. `lib/` isn't in git, so that install relied on KiCad's Python happening to include `requests`.
  - Its link to the README's usage section is fixed.

## [0.9.0] - 2026-09-15

Published as **0.9.0** (SWIG build, KiCad 9 and 10) and **1.9.0** (IPC build, KiCad 11 and its 10.99 nightlies); see *Two builds per release* below.

### Fixed
- **Release workflow: a rejected metadata push went unnoticed.** The last step pushed the tag's tree to `main` with `git push origin HEAD:main || echo "Nothing to push"`. When the tag lagged behind `main` — v0.7.1 was tagged before the v0.7.0 metadata commit had been pulled — the push was rejected, the run still went green, and the PCM never listed the release until the metadata was fixed by hand. The metadata step now lives in `scripts/publish-metadata.sh`: it updates a fresh worktree of the latest `main` (so entries already on `main` are never lost), retries if `main` moves during the run, fails the job if it still can't publish, and does nothing when re-run for a release that's already recorded. The workflow's three inline copies of `scripts/update-metadata.py` are gone, and releases run one at a time.
- **Release workflow: the `__pycache__` check never failed.** `grep … || echo "✓ No pycache files found"` printed any offending entries and carried on. It now fails the run.
- The workflow warns when the tagged commit's `__version__` doesn't match the tag, instead of silently committing the corrected `__init__.py` to `main`.
- **The search dialog tripped a wx assertion** ([#19](https://github.com/hulryung/kicad-lcsc-manager/issues/19) prep). Its Search button was added to a horizontal sizer with `wxALIGN_RIGHT`, which wx ignores and asserts on. Inside pcbnew KiCad swallows the assertion; in a standalone wxPython app — which is what an IPC API plugin runs in — it is an exception, and the dialog failed to open. The flag is gone; the button is still right-aligned by the enclosing sizer. Every dialog and the main runtime paths are now assertion-free.

### Changed
- **Importing the package no longer registers the SWIG action plugin in an IPC plugin process** ([#19](https://github.com/hulryung/kicad-lcsc-manager/issues/19) prep). KiCad launches IPC plugins as a separate Python process with `KICAD_API_TOKEN` set, and `pcbnew` is importable there, because the plugin's venv sees KiCad's site-packages. Registering an `ActionPlugin` outside the pcbnew process raises once a `wx.App` exists, so `import lcsc_manager` failed. Registration is now skipped when `KICAD_API_TOKEN` is set (`utils/runtime.py`). Only the per-launch token counts: a `KICAD_API_SOCKET` exported by someone who scripts KiCad from a terminal doesn't disable the plugin. Checked in pcbnew 10.0.6 with the API server both on and off: the plugin still registers and appears under *Tools → External Plugins*.

- **Everything that talked to pcbnew now goes through a KiCad host** ([#19](https://github.com/hulryung/kicad-lcsc-manager/issues/19)). New `utils/kicad_host.py` puts the plugin's three possible homes behind one interface: `SwigHost` (inside pcbnew), `IpcHost` (an IPC plugin process) and `NullHost` (no KiCad session). The host answers where KiCad keeps its settings, how `${VARS}` expand, whether a footprint library is loaded, and whether one can be registered in memory. `library_manager.py` and `config.py` no longer import pcbnew; only the SWIG entry point (`plugin.py`) and the host do.
  - The host is chosen from the launch context, not from `import pcbnew` succeeding: `KICAD_API_TOKEN` means IPC; pcbnew with an open board means SWIG; anything else means no session. So a standalone KiCad Python — scripts, tests — now counts as "no session" and never picks up the real KiCad settings folder, which previously let a shared-location import from such a script edit the user's actual global library tables.
  - `IpcHost` works out the user settings folder the way KiCad does (`KICAD_CONFIG_HOME`, else the platform folder plus `kicad`, then `major.minor`), and expands `${VARS}` from `kicad_common.json` plus the environment. It doesn't rely on IPC calls that only exist in newer builds (`GetPaths` is master-only; `ExpandTextVariables(expand_env_vars=…)` is 10.0.7+).
  - The "reopen the project" notice asks the host whether the new footprint library is loaded. The IPC API can't answer that, so over IPC a row written just now counts as not loaded. Behaviour inside pcbnew is unchanged — confirmed in pcbnew 10.0.6: the host is `swig`, in-memory registration is correctly unavailable, the settings folder is correct, and a real footprint import still produces the notice.
  - `IpcHost.project_file()` now lets a lost connection reach the caller instead of reporting "nothing open", and returns nothing for a board that was never saved. Only KiCad's "editor not open" answer is skipped. `set_host_for_tests()` is now `set_host()`, since the IPC entry point uses it too.
- **The dialog choice moved from `plugin.py` to `launcher.py`**, so the SWIG plugin and the IPC entry point share it: the search dialog, else the basic dialog with the limited-mode notice, else the part-number prompt. No behaviour change. `plugin.py` keeps only what's SWIG-specific.
- `utils/logger.py` exposes `log_file()` and `log_to_file_only()`.
- **`scripts/publish-metadata.sh` takes every package of a release and writes the entries with the tag's own `update-metadata.py`**, not the copy on the latest `main` it updates. The entries belong with the code that built the packages; a newer `main` can't change how they're described. `update-metadata.py` takes `<version> <package.zip>...`, wants exactly the release's builds, and records one entry per build (an existing entry is replaced in place; new ones go first). `install_size` is now what the PCM actually extracts, not a fixed 250000. `repository.json`'s `update_timestamp` is taken from an aware UTC time: a naive one was read as local time, which put it off by the UTC offset outside CI.

### Added
- **Two builds per release: SWIG for KiCad 9 and 10, IPC for KiCad 11** ([#19](https://github.com/hulryung/kicad-lcsc-manager/issues/19)). A tag `vX.Y.Z` now publishes two packages of the same code: the SWIG build `X.Y.Z` (`runtime: swig`, KiCad 9.0 to 10.99) and the IPC build `(X+1).Y.Z` (`runtime: ipc`, KiCad 10.99 and later), both as `stable` entries of the same package. Each KiCad is offered exactly one.
  - The version numbers have to differ: KiCad finds a package version by its version string alone, when installing, updating and deciding compatibility. With two entries under one string, KiCad 11 could reject its own IPC build, because it turns down every SWIG version it finds under that string. The IPC build is the release with the major number raised by one, so `v0.9.0` gives `0.9.0` and `1.9.0`. Tags therefore stay on major 0 while both builds exist. A release whose version is already published under the other runtime (`v1.9.0`'s SWIG build after `v0.9.0`'s IPC build) is refused by `build-packages.py` before anything is uploaded, and by `update-metadata.py` on `main`.
  - The IPC build starts at 10.99 (KiCad 11's nightlies), not 10.0: on KiCad 10 it would replace the SWIG build, and it needs the API server switched on. It's `stable` rather than `testing` because KiCad never offers an update less stable than what's installed, so a KiCad 11 that still lists a stable SWIG install wouldn't be offered it.
  - New `scripts/build-packages.py` (on top of `scripts/pcm_builds.py`) builds both ZIPs and checks each one: no bytecode, bundled dependencies present, the right `metadata.json` and `__version__`, and `plugin.json`/`requirements.txt` plus the files `plugin.json` refers to in the IPC ZIP only. A `plugin.json` in the SWIG ZIP would switch its SWIG plugin off, so that fails the build. Each ZIP's `metadata.json` is built from the repository's `metadata.json`, not a second copy inlined in the workflow. `scripts/package.sh` now runs the same build locally.
  - The release workflow builds with it, attaches both ZIPs to the GitHub release (the notes say which is for which KiCad), and records both entries.
  - Verified: the generated `metadata.json`, `packages.json` and `repository.json` and each ZIP's `metadata.json` pass KiCad 10.0.6's own PCM schemas (v1 and v2). The updated `packages.json` also passes KiCad 9.0's and 8.0's, so older KiCads keep loading the repository. The workflow's shell steps ran locally under both `bash -e` and `bash -eo pipefail`. In KiCad 10.0.6 (sandboxed), each ZIP was unpacked the way the PCM does. The IPC build loaded from `3rdparty`: KiCad built its environment, installed kicad-python and showed one button, with nothing under *Tools → External Plugins*. The SWIG build in the same place registered as before (one button, listed under *External Plugins*).
- `tests/test_build_packages.py` — the two builds' versions, ZIP names and URLs; that KiCad 9.0, 9.0.7 and 10.0.6 are each offered only the SWIG build and 10.99, 11.0 and 11.1 only the IPC build (KiCad's own compatibility rule); a version never being reused for the other runtime (the build and the metadata update both refuse it, and a refused update writes neither file); both ZIPs' contents and metadata; unpacking them the way the PCM does; a set of broken ZIPs that `check_package` must refuse; building without bundled dependencies failing; and `update-metadata.py` recording both entries, keeping history and order, re-running cleanly, and refusing an incomplete or mismatched release.
- **The IPC API plugin: entry point and `plugin.json`** ([#19](https://github.com/hulryung/kicad-lcsc-manager/issues/19)). KiCad 11 removes the SWIG API; this is the same plugin running as an IPC plugin. It ships as the IPC build above.
  - `ipc/plugin.json` declares one toolbar action for the PCB and Schematic Editors, under the Plugin and Content Manager package's identifier, with 24 px and 48 px icons (KiCad puts IPC icons on the toolbar unscaled). `ipc/requirements.txt` has KiCad install `kicad-python>=0.8.0,<0.9` into the plugin's environment; everything else stays bundled. Both live outside `plugins/lcsc_manager/`, and `scripts/assemble-ipc-plugin.py` combines them with the package into the IPC plugin folder.
  - `plugins/lcsc_manager/ipc_main.py` is what KiCad runs. It loads the plugin folder as the `lcsc_manager` package (a PCM install folder like `com_github_hulryung_kicad-lcsc-manager` can't be imported by name) and takes that folder off `sys.path`, so its subpackages can't shadow other modules. It then asks KiCad over IPC for the open board, or for the project when only the Schematic Editor is open, and opens the same dialog as the SWIG plugin. If kicad-python is missing, KiCad can't be reached, nothing is open, or the project was never saved, it says so in a dialog.
  - **The IPC process keeps KiCad's pipes clean.** KiCad 10 reads a plugin's stdout/stderr only after the process exits, and shows whatever it finds as an error in the editor. The plugin's usual console logging would therefore have shown up as errors, and a long session would block once the pipe filled. `ipc_main.py` points stdout and stderr (at the file-descriptor level, so output from wx/GTK too) at the log file and turns console logging off.
  - A package that ships `plugin.json` doesn't register the SWIG plugin, so KiCad 10, which loads a PCM-installed package both ways, wouldn't show two buttons if it got the IPC build.
  - Verified without the KiCad app: a venv built the way KiCad builds one (KiCad 10's Python 3.9, `pip install --only-binary :all:` with KiCad's flags), and a stand-in API server (`tests/fake_kicad_api.py`). With these, the entry point opens the real search dialog and exits 0 with nothing on stdout/stderr, and an import through `IpcHost` writes the project tables. kicad-cli then renders the imported symbol and footprint. Verified in KiCad 10.0.6 with a sandboxed config, documents and cache: KiCad accepts the plugin, builds its environment, installs kicad-python and shows the button. Run against that KiCad, the entry point gets the open board and imports work. `TESTING.md` has the steps.
- `tests/test_ipc_plugin.py` — `plugin.json` against KiCad's identifier rule and schema, the IPC files staying out of the SWIG package, bounded requirements, the assembled folder (entry point, 24/48 px icons, no bytecode, no overwriting), SWIG registration skipped for the IPC build, and the entry point run the way KiCad runs it: from a PCM-style folder, with nothing on stdout/stderr even when C code writes there, and with the plugin folder off `sys.path`. Also covers each "can't start" message, the dialog opening for the open project with the host shared with the library code, and the dialog fallback chain (search dialog → basic dialog with a one-time notice → part-number prompt), which had no tests before. Uses a stub wx, so it runs anywhere.
- `tests/test_kicad_resolves_tables.py` — a headless check against KiCad itself that the table rows the plugin writes actually resolve. KiCad's bundled Python builds a project and a test footprint and, through the real `LibraryManager`, the table rows; a board places the footprint by nickname; `kicad-cli pcb drc` then has to find it through the tables. It covers both the project table and the shared location's global table. A control run with the row broken must be flagged, and so must a plugin that writes a wrong URI (checked by mutating it). `KICAD_CONFIG_HOME` is sandboxed, so the user's real configuration is never touched; offline, a few seconds. `TESTING.md` now describes this approach and what still needs a running KiCad.
- `tests/test_kicad_host.py` — the settings-folder rules per platform and for `KICAD_CONFIG_HOME`; each host against a stand-in pcbnew or kicad-python (project file from a PCB or a schematic, path variables, KiCad 9's in-memory registration, a missing library listing); host detection; only session hosts being remembered; `config` expanding through the host; and a source guard that pcbnew stays confined to the host and `plugin.py`. On a machine with KiCad it also checks that KiCad's standalone Python is detected as no session, and that the computed settings folder matches `SETTINGS_MANAGER.GetUserSettingsPath()`. The reload-notice tests now inject hosts, including the IPC case.
- `tests/test_ipc_prep.py` — the IPC-process conditions: only the token marks an IPC process; importing the package there skips SWIG registration (also under KiCad's own Python with a `wx.App` already created, where it used to raise); and every dialog, plus the main runtime paths, builds with no wx assertions in a standalone app. The KiCad-Python checks are skipped where KiCad isn't installed; with either fix reverted, the matching test fails.
- `tests/test_publish_metadata.py` — exercises the publish step against real git repositories (a bare origin and clones): publishing on top of `main`, a tag that lags behind `main` keeping `main`'s entries, a rejected push being retried, a persistent failure failing loudly without touching `main`, an idempotent re-run, no leftover worktree, and checks that the workflow no longer swallows failures.

## [0.8.1] - 2026-09-13

### Fixed
- **KiCad 10: a project's newly imported footprints couldn't be placed, and nothing said why.** KiCad 10 no longer wraps `FP_LIB_TABLE` / `PROJECT` for Python, so the in-memory registration used on KiCad 9 always failed (logging a warning on every import) and the plugin fell back to writing `fp-lib-table` — which the running session doesn't reread. Verified on KiCad 10.0.6: straight after an import `pcbnew.GetFootprintLibraries()` doesn't list `lcsc_footprints`; after reopening the project it does. The plugin now skips the doomed API call on KiCad 10, checks whether the session actually sees the library, and only if it doesn't says: *"This KiCad session hasn't loaded the LCSC footprint library yet. Reopen this project (or restart KiCad) to place the imported footprints."* KiCad 9 keeps its immediate in-memory registration. No notice is shown when there are no footprints to place (a symbol-only import) — KiCad 10 leaves a library with no folder out of its list even after a reopen — or when the plugin can't tell (outside KiCad).
- **No more doubled "reopen/restart" advice.** When an import already carries a restart or reopen notice, the generic *"Reopen the schematic editor for imported symbols to appear"* line is dropped — restarting KiCad or reopening the project covers the schematic editor too. Applies to the search dialog, the basic dialog and BOM summaries.
- **Each library notice appears once per dialog visit.** A library the session hasn't loaded stays unloaded until a reopen, so its notice would otherwise repeat on every import.

### Added
- `tests/test_library_reload_notices.py` — KiCad 10's shape (no table API; library loaded or not; symbol-only import), KiCad 9's in-memory route, no false alarm outside KiCad, the shared location's one-time restart notice, BOM aggregation, once-per-session notices, and source-level checks that every dialog drops the redundant hint.

## [0.8.0] - 2026-09-13

Adds a shared library location — the feature requested in [#20](https://github.com/hulryung/kicad-lcsc-manager/issues/20): import every part into one folder that all projects use.

### Added
- **One shared library folder for all projects.** The Settings dialog has a new **Library location** choice: *Inside each project* (the existing behaviour, still the default) or *One shared folder for all projects*. In the shared location every import lands in a single folder, and its libraries are registered in KiCad's **global** library tables, so parts imported from one project are available in every other one — no per-project copies.
  - The folder may be a full path (`~/KiCad/lcsc`, `C:\KiCadLibs\lcsc`) or use a KiCad path variable (`${MY_LIBS}/lcsc`). A variable is kept verbatim in the library tables and in footprints' 3D model references, so they survive the folder moving or the project being opened elsewhere; `~` is expanded, since KiCad doesn't expand it. An undefined variable is rejected with a pointer to *Preferences → Configure Paths*.
  - Shared libraries use their own nicknames, `lcsc_shared` and `lcsc_shared_footprints`, so a project that still has per-project `lcsc_imported` / `lcsc_footprints` entries can't shadow them (project tables win over global on a name clash). Symbols' Footprint fields point at `lcsc_shared_footprints:`.
  - A project can override the location, e.g. a team repository that commits its own libraries. The shared folder itself is always saved to Global — it is a location on this computer and must not end up in a committed project file.
  - The dialog disables whichever field the chosen location doesn't use, validates the folder, has a **Browse…** button, and the preview shows the resolved paths and where the libraries get registered. The import dialogs' destination line says when the shared folder is in use.
- **Careful edits to KiCad's global library tables** (`library/lib_table.py`). Only a file that already is a library table of the right kind is edited; an entry with our nickname that LCSC Manager didn't create is never modified (the user is told instead); the first edit leaves `sym-lib-table.lcsc_manager.bak` / `fp-lib-table.lcsc_manager.bak` beside the table; writes replace the file atomically; and our own entry follows the shared folder if it moves. Registration is idempotent and runs on every import, so an entry KiCad drops — it rewrites its global tables from memory when libraries are edited in the same session — is restored by the next import.
- `tests/test_shared_library.py` — 24 offline tests: paths, URIs and nicknames in both locations, `~` and `${VAR}` handling, rejection of unusable folders, the shared folder never reaching a project file, per-project opt-out, the table editor (create, add beside KiCad 10's default rows, idempotence, following a moved folder, leaving foreign rows and non-table files alone, one-time backup, escaping), and LibraryManager's global registration, conflict reporting and manual-setup fallback.

### Fixed
- **BOM import dropped library-table messages.** The batch importer discarded each part's `notifications`, so warnings about registering the libraries never reached the user — and with the shared location, a first import done as a BOM batch would never say that KiCad needs restarting, or that a name clash blocked registration. They are now collected (once each) and shown in the BOM summary.
- A shared folder typed in another OS's form (e.g. `C:\KiCadLibs\lcsc` on macOS) is rejected instead of being taken as relative to KiCad's working directory, and a hand-edited project file can't set the shared folder.

### Notes
- KiCad reads its global library tables at startup, so the shared library appears in other projects after KiCad is restarted once; the first shared import says so.
- Verified by importing parts from two projects into one shared folder against the live API: both land in the folder, the global tables get one entry each (the second project changes nothing), and neither project gets a `libs/` folder or table entries. KiCad's own parsers accept the result: `pcbnew.FootprintLoad` loads the shared footprint with its absolute 3D path, and `kicad-cli sym export svg` plots the shared symbols.
- Verified end to end in KiCad 10.0.6: importing C25804 through the plugin in one project wrote it to the shared folder, registered `lcsc_shared` / `lcsc_shared_footprints` in the real global tables and asked for a restart; after restarting, a *different* project's footprint chooser listed `lcsc_shared_footprints:C25804_R0603`, and eeschema's symbol chooser listed it under `lcsc_shared` with its Footprint field resolving to that footprint.

## [0.7.2] - 2026-09-13

Resolves [#20](https://github.com/hulryung/kicad-lcsc-manager/issues/20): Global settings looked unsaved and could be silently overridden by the project.

### Fixed
- **Global settings looked lost after saving** ([#20](https://github.com/hulryung/kicad-lcsc-manager/issues/20)). The Settings dialog always opened on *This project only* whenever a project was open, whatever had been saved. After a Global save, reopening therefore showed the project view — with the Global value resolved to an absolute path inside the project — so the save appeared to have been discarded. The dialog now opens on the scope that actually supplies the settings in effect: *This project only* when the project overrides something, *Global* otherwise.
- **A project Save no longer shadows every Global setting.** Saving at project scope wrote all four fields into `.lcsc_manager.json`, inherited values included, so that project ignored any later Global change for good — the other half of #20. Project saves now store only the values that differ from Global, and remove the file when nothing differs. Global saves likewise store only values that differ from the built-in defaults.
- **Projects already pinned by older versions are called out.** When the Global view is open on a project that overrides Global, the dialog says which fields are overridden, and after a Global save it offers to remove those overrides so the project follows Global.
- **Windows drive paths slipped past validation.** Only a leading `/` or `~` was rejected, so `C:\libs` was accepted and produced a broken `${KIPRJMOD}/C:\libs/...` library-table URI. Drive letters, UNC and `\`-rooted paths are now rejected too, and `..` is caught with either separator.

### Changed
- The scope box is now titled **Save these settings to**, with *Global — the default for every project* and *This project only — overrides Global for this project*, plus a note that paths are relative to each project's folder. "Global (all projects)" read as "one shared library folder", which is not what the option does.
- Field badges read `[from global]` / `[from default]` for inherited values, since a Save no longer copies them into the edited scope.

### Added
- `Config.default_edit_scope()`, `save_project_settings()`, `save_global_settings()`, `project_override_keys()` and the module-level `validate_path_value()` — wx-free, so the dialog's decisions are unit-tested.
- `tests/test_issue20_settings_scope.py` — which scope the dialog opens on, diff-only project and global saves, a later Global change reaching a project that was saved once, removal of an emptied project file, preservation of non-path keys, detection of old fully-pinned projects, and path validation across OSes.

## [0.7.1] - 2026-08-23

Resolves [#17](https://github.com/hulryung/kicad-lcsc-manager/issues/17): some parts showed a blank LCSC ID in the search results and could not be imported.

### Fixed
- **Search results could lose the LCSC part number, blocking import** ([#17](https://github.com/hulryung/kicad-lcsc-manager/issues/17)). The part number was recovered from JLCPCB's `urlSuffix`, which comes in two shapes — `"RaspberryPi-RP2040/C2040"` (brand-model slug + code) and `"C5142652"` (bare code). The extraction required a `/` and returned an empty string otherwise, so affected parts (e.g. C5142652 / CM8V-T1A-32.768KHZ-9PF-20PPM) appeared with an empty **LCSC ID** column, a preview stuck on *"Loading..."*, and **Import Selected** refusing to start with *"No LCSC ID found for selected component."* The number is now read from the `componentCode` field, which carries it verbatim, falling back to the last segment of `urlSuffix`. Only the search-result mapping was affected — the parts themselves were always importable, which is why BOM import worked for them.
- **A result with no part number no longer leaves the preview spinning.** The preview loader returned silently after the caller had already painted *"Loading..."*. It now replaces that placeholder with an explanation, so an unusable row says so instead of appearing to hang.

### Added
- `tests/test_issue17_search_lcsc_id.py` — offline coverage for both `urlSuffix` shapes, `componentCode` precedence, fallback when the field is absent, the no-id-anywhere case (empty string, not an exception), and source-level guards against the slash-only extraction returning.

## [0.7.0] - 2026-08-08

Resolves [#16](https://github.com/hulryung/kicad-lcsc-manager/issues/16): importing a part no longer closes the dialog, so several parts can be searched for and added in one visit.

### Changed
- **The import dialogs stay open after a successful import** ([#16](https://github.com/hulryung/kicad-lcsc-manager/issues/16)). Both the Search & Import dialog and the basic fallback dialog ended themselves the moment a part landed, so adding *n* parts meant reopening the plugin *n* times — BOM import only helps when you already know every LCSC part number, not when you're searching for parts one at a time. Now the search text, results list, previews and import options all survive an import: pick the next part from the same result list and click **Import Selected** again. The dialog closes only when you ask it to, and still reports success to the caller if anything was imported during the visit.
  - A green **"Imported this session (n): …"** line above the buttons tracks what has landed (oldest entries elided after 6; re-importing a part doesn't double-count it), since the dialog closing is no longer the confirmation that the import worked. Parts brought in via **Import BOM…** count toward the same tally.
  - The **Cancel** button is now labelled **Close** in both dialogs — it is the ordinary way out of a successful session, not just an abort. ESC and the window close button behave the same.
  - The *"reopen the schematic editor for imported symbols to appear"* note is shown once per session — on the first import that actually writes a symbol — instead of after every single import.
  - In the basic dialog the part number is re-selected after an import, so the next one can simply be typed over it.

### Fixed
- **A failed import in the search dialog was reported as a success.** `import_component()` collects per-artifact failures into `result["errors"]` and reports them via `result["success"]`, but the search dialog ignored both and always said *"Import completed!"*. It now gates on `success`, lists the errors in the result box, and keeps failed parts out of the session tally — which matters more than before, since that tally is now the user's confirmation that a part landed. The basic dialog and BOM import already checked `success`.
- **"Import Selected" could silently re-import the previous search's part.** A new search rebuilds the results list but left `selected_component` pointing at the old pick, so with nothing visibly selected the button imported the earlier part again. Searching now clears the selection. This only became reachable in practice because search → import → search → import is now the normal flow.
- **Basic dialog could fail to open on assertion-enabled wxPython builds.** Its LCSC part-number field bound `EVT_TEXT_ENTER` without the required `wx.TE_PROCESS_ENTER` style, which wx asserts on at `Bind()` time (fatal under KiCad's bundled wx when constructed outside pcbnew). Found while verifying the #16 change against KiCad 9's own wxPython.

### Added
- `utils/session.py` — wx-free `ImportSession` shared by both dialogs: the tally, the status-line wording, and the one-shot reopen hint (the BOM dialog now takes its reopen wording from the same constant instead of its own copy).
- `tests/test_issue16_stay_open.py` — offline coverage for session tracking (ordering, re-import de-duplication, long-session elision, hint-once-per-session, hint-requires-a-symbol) plus source-level regression guards that neither dialog ends itself after an import.

## [0.6.0] - 2026-07-17

Adds BOM file import ([#13](https://github.com/hulryung/kicad-lcsc-manager/issues/13), requested in [discussion #11](https://github.com/hulryung/kicad-lcsc-manager/discussions/11)), fixes the Linux degraded-mode experience ([#14](https://github.com/hulryung/kicad-lcsc-manager/issues/14), follow-up to [#6](https://github.com/hulryung/kicad-lcsc-manager/issues/6)), and restores KiCad 9 compatibility ([#15](https://github.com/hulryung/kicad-lcsc-manager/issues/15)).

### Fixed
- **Plugin works again on KiCad 9 (Python 3.9)** ([#15](https://github.com/hulryung/kicad-lcsc-manager/issues/15)). The bundled `lib/urllib3` was v2.7.0, which requires Python ≥ 3.10 (`bytes | str` at import time), so on KiCad 9 — whose bundled Python is 3.9 — every dialog import died with `TypeError`, and because `lib/` sits first on `sys.path` it also shadowed any working urllib3 the user had installed. Root cause: `scripts/bundle-dependencies.sh` resolved packages unpinned under the maintainer's modern Python. The bundler now passes `--python-version 3.9` (KiCad 9's Python) so pip only selects compatible releases, `lib/` was regenerated (urllib3 2.7.0 → 2.6.3, requests 2.33.1 → 2.32.5), and `scripts/package.sh` re-runs the bundler before every packaging so releases can't ship a stale `lib/`. Verified by importing the bundled stack and constructing the full search dialog with KiCad 9's own Python 3.9.13.
- **Full search dialog now works on Linux without the WebView package** ([#14](https://github.com/hulryung/kicad-lcsc-manager/issues/14), [#6](https://github.com/hulryung/kicad-lcsc-manager/issues/6)). `wx.html2` is a separate system package on most distros (Debian/Ubuntu: `python3-wxgtk-webview4.0`, Fedora: `python3-wxpython4-webview`); when missing, the plugin silently fell back to the basic LCSC-ID-only dialog. The WebView import is now optional: the full search dialog loads regardless, showing an install hint in the preview tabs instead of SVG previews (search, specifications, import, and BOM import are unaffected). Also survives wx.html2 importing but the browser backend failing at runtime (some Linux/Flatpak builds).
- **Degraded mode is now announced in the GUI** ([#14](https://github.com/hulryung/kicad-lcsc-manager/issues/14)). If the full dialog genuinely can't load, a message box (once per KiCad session) names the actual missing dependency with per-distro install commands, instead of a console-only warning that guessed the wrong cause ("missing Pillow?"). The whole fallback chain now also survives non-`ImportError` import-time failures (e.g. a bundled dependency incompatible with KiCad's Python raises `TypeError`), which previously aborted with a generic "Dialog error": full dialog → basic dialog → last-resort prompt. The last-resort prompt now performs a real import (it previously reported success without importing anything).
- **Basic dialog no longer misreports importable-part status** ([#14](https://github.com/hulryung/kicad-lcsc-manager/issues/14)). Searching a real catalog part that has no EasyEDA CAD data (e.g. C6056597) said *"Component not found — check the part number / your connection"*. The basic dialog now checks the JLCPCB catalog and reports *"exists … but has no symbol/footprint in EasyEDA's library, so it can't be imported"* (with stock/datasheet/product links), matching the v0.5.1 fix that previously covered only the full dialog. Rate-limiting is likewise reported calmly instead of as a scary error box.

### Added
- `LCSCAPIClient.get_jlcpcb_info()` — public, never-raising JLCPCB catalog lookup (exact part match with stock/price/datasheet), used by the basic dialog to distinguish "no CAD data" from "no such part".
- `tests/test_issue14_fallback.py` — offline coverage for the degraded-mode message builder (webview-vs-other causes, real exception named, no more "Pillow" guess), install-hint completeness, the public JLCPCB lookup delegate, and source-level guard invariants of the optional-WebView import.
- **Import BOM files** — a new **Import BOM…** button in the Search & Import dialog batch-imports every component referenced in a JLCPCB / EasyEDA / KiCad BOM file. The parser auto-detects the LCSC part-number column (tolerating header variants such as `LCSC Part #`, `LCSC Part Number`, `LCSC`, and value-based fallback when no such header exists), de-duplicates repeated part numbers (aggregating designators and quantities), and skips rows with no LCSC number. A preview dialog lets you tick which parts and which of symbol / footprint / 3D model to import; a progress dialog reports each part and can be cancelled mid-run; a summary lists what imported and what failed (and why). CSV is supported natively; `.xlsx` when the optional `openpyxl` package is present. Non-ASCII exports (e.g. GBK from Chinese tooling) are decoded via the bundled `charset_normalizer`.
  - New modules: `bom/bom_parser.py` (wx/pcbnew-free, unit-tested), `bom/bom_importer.py` (batch orchestration over the existing single-part import path), and `dialog_bom.py` (the wx UI).
- `tests/test_bom_parser.py` — offline coverage for JLCPCB parsing/dedup/skip, delimiter & BOM/encoding detection, header variants, value-based column detection, the footprint-not-mistaken-for-LCSC guard, metadata rows above the header, and importer orchestration (happy path, missing part, cancellation).
- `tests/test_bundled_libs_py39.py` — regression guards for [#15](https://github.com/hulryung/kicad-lcsc-manager/issues/15): bundled urllib3/requests stay on Python-3.9-compatible lines, the bundler keeps its `--python-version` pin, and (on machines with KiCad installed) the bundled stack actually imports under KiCad's own Python.

## [0.5.2] - 2026-06-09

Resolves [#8](https://github.com/hulryung/kicad-lcsc-manager/issues/8): multi-unit symbols (parts whose schematic symbol is split across several pieces) failed to import.

### Fixed
- **Multi-unit symbols now import every unit** ([#8](https://github.com/hulryung/kicad-lcsc-manager/issues/8)). Parts whose schematic symbol is split across several units/gates (e.g. C3216634 / MIMXRT685SFVKB) imported as an empty symbol. EasyEDA delivers each unit as an entry in `subparts` and leaves the top-level `dataStr.shape` empty, but the symbol converter only read the top-level shape. It now emits one KiCad sub-symbol (`<name>_<unit>_1`) per unit, using the shared canvas origin so units stay aligned. Single-unit parts are unchanged; a part with no drawable geometry anywhere still falls back to the placeholder symbol.

### Added
- `tests/test_symbol_multi_unit.py` — offline coverage for multi-unit fan-out (one sub-symbol per unit, all pins preserved), single-unit no-regression, and the empty-geometry placeholder fallback.

## [0.5.1] - 2026-06-01

Resolves [#5](https://github.com/hulryung/kicad-lcsc-manager/issues/5) (3D models not linked to footprints) and addresses [#7](https://github.com/hulryung/kicad-lcsc-manager/issues/7) (macOS install friction and confusing search errors).

### Fixed
- **3D model reference now matches the file on disk** ([#5](https://github.com/hulryung/kicad-lcsc-manager/issues/5)). The generated `.kicad_mod` referenced the EasyEDA model *title* (e.g. `DP9-TH_ZHOUR_DP-9P.wrl`), but the model is saved as `<lcsc_id>.wrl` / `<lcsc_id>.step`, so KiCad couldn't find it and users had to fix the path by hand. The footprint converter now overrides the 3D model name to the LCSC id before export. Sharing the `<lcsc_id>` basename also lets KiCad's STEP exporter locate the sibling `.step`. Regression introduced in 0.5.0 by the switch to vendored upstream `easyeda2kicad`.
- **Confusing "not found in EasyEDA database" message** ([#7](https://github.com/hulryung/kicad-lcsc-manager/issues/7)). Transient API rate-limiting and a part that genuinely has no EasyEDA CAD model were reported identically. They're now distinguished: rate-limiting shows *"EasyEDA is rate-limiting requests — wait a few seconds and click the component again,"* while a missing part says it *"has no symbol/footprint in EasyEDA's library, so it can't be imported."*

### Added
- **`LCSCRateLimitError`** (subclass of `LCSCAPIError`), raised when HTTP 403/429 retries are exhausted; HTTP 429 is now treated as rate-limiting alongside 403. `search_component` preserves typed API errors instead of flattening them, so the UI can react to rate-limiting specifically.
- `tests/test_api_error_classification.py` — offline, mocked coverage for the rate-limit subclass, persistent-403 raising, type preservation through `search_component`, and genuinely-missing parts returning `None`.

### Documentation
- **Install instructions** ([#7](https://github.com/hulryung/kicad-lcsc-manager/issues/7)): Method 1 rewritten with where to find the Plugin and Content Manager on macOS (the main KiCad launcher window, not always under *Tools*), the repository-dropdown step, **Apply Pending Changes**, and full restart / reboot guidance.
- **Usage callout** that the plugin runs in the **PCB Editor** only — KiCad's Python action-plugin API is pcbnew-only, so **Search and Import** isn't available from the Schematic Editor. Imported symbols are still added to the project's symbol library and remain available in the schematic.

### Notes
- The 3D-model URI is now an explicit allowed delta in `tests/test_footprint_matches_upstream.py` (we rename the reference to `<lcsc_id>.wrl`; upstream uses the title).

## [0.5.0] - 2026-05-11

Resolves [#2](https://github.com/hulryung/kicad-lcsc-manager/issues/2): footprint imports now produce correct geometry on stock KiCad installs. Previously, the converter depended on the third-party `KicadModTree` package, which ships with neither KiCad 9 nor 10; on installs without it the plugin silently fell back to a 2-pad placeholder for every component.

### Changed
- **Footprint converter** rewritten as a thin wrapper around a vendored subset of [easyeda2kicad.py v1.0.1](https://github.com/uPesy/easyeda2kicad.py). The vendored code lives under `plugins/lcsc_manager/vendor/easyeda2kicad/` and emits the `.kicad_mod` text directly via string templates. No external Python dependencies remain on the footprint path.

### Removed
- **`KicadModTree` dependency** on the footprint path. Symbol and 3D-model conversion never used it.
- **Placeholder fallback footprint**: the 2-pad fallback that masked import failures is gone. Bad data now raises a real error instead of silently producing the wrong geometry.
- Dead files: `plugins/lcsc_manager/converters/jlc2kicad/footprint_handlers.py`, `…/model3d.py`, and the unit test `tests/test_footprint_handlers_patches.py` (superseded by the upstream-comparison test below).

### Added
- `tests/test_footprint_matches_upstream.py` — runs both pipelines (ours and a direct upstream call) on the same EasyEDA JSON and asserts byte-for-byte equivalence after normalizing the three intentional deltas (footprint name, generator string, configurable 3D-model URI). Covers Domigome's reporter case (C2939726, 5-pad SS12D07VG4) plus a generic 0603.

### Notes
- The vendored upstream code is AGPL-3.0. See [NOTICE.md](NOTICE.md) for attribution and redistribution implications. The plugin itself remains MIT.
- Existing post-v0.3.0 fixes that we ported into our `jlc2kicad/footprint_handlers.py` (layer mapping, h_VIA THT, SOLIDREGION filter, etc.) are all present in vendored upstream and continue to apply. Our extra `NAME(N)` → `N` pad-number normalization is preserved via a small post-processing step in the converter.

## [0.4.0] - 2026-05-11

Resolves [#1](https://github.com/hulryung/kicad-lcsc-manager/issues/1): library paths are now user-customizable at two scopes (global and per-project), via a new in-plugin Settings dialog. No more editing JSON by hand to change where imports land.

### Added
- **Settings dialog** reachable from the ⚙ button in the import dialog. Edits four path values — library root, symbol file name, footprint folder, 3D model folder — with live path preview, input validation, and a per-field source badge (`[global]`, `[project]`, `[default]`, `[edited]`, `[source → scope]`).
- **Per-project overrides** via `<project>/.lcsc_manager.json`. Layered resolution: `default < global (~/.kicad/lcsc_manager/config.json) < project`. Each layer may store any subset of keys.
- **Scope-aware preview** in the Settings dialog: Global view shows `${KIPRJMOD}/…` template paths (project-agnostic), Project view shows the resolved absolute path against the currently open project, with `✓ exists` / `(will create)` indicators.
- **Import destination panel** in the main search dialog showing where the next import will land and which scope's settings are active (`This project only`, `Global`, `Default`, or `Project override + Global/Default for the rest`).
- Unit tests for config layering (`test_config_layering.py`, 13 tests), lib-table URI generation (`test_library_manager_uris.py`, 3 tests), and footprint converter 3D URI plumbing (`test_footprint_converter_3d_uri.py`, 3 tests).

### Fixed
- **Hardcoded library paths**: `sym-lib-table` URI, `fp-lib-table` URI, and the 3D model reference inside generated `.kicad_mod` files were embedded as string literals (`${KIPRJMOD}/libs/lcsc/...`). They now flow from the user's config so customization actually takes effect end-to-end.

### Changed
- Global config file is no longer seeded with defaults on first run. `~/.kicad/lcsc_manager/config.json` starts empty so the Settings UI can accurately mark which keys are real user overrides vs. inherited defaults.

## [0.3.0] - 2026-04-08

Major integration of fixes ported from [easyeda2kicad.py v1.0.1](https://github.com/uPesy/easyeda2kicad.py) upstream. Improves correctness for footprint layer assignment, multi-unit symbol pin numbers, 3D model placement, and via handling. Several latent bugs in the JLC2KiCad_lib fork are fixed.

### Fixed
- **Footprint layer mapping**: corrected 7 EasyEDA layers that were miswired to wrong KiCad layers. TopAssembly (13) now lands on `F.Fab` instead of the wrong-side `B.Fab`; BottomAssembly (14) on `B.Fab` instead of `F.CrtYd`. Component Shape (99), Lead Shape (100), and Component Polarity (101) now map to `F.CrtYd`, `F.Fab`, and `F.SilkS` instead of being dumped on User.1/2/3.
- **Multi-unit symbol pin numbers**: canonical KiCad pin numbers are now extracted from the `^^num` segment (segment 4, field 4) instead of `spice_pin_number`. Multi-unit ICs (gates, dual op-amps, drivers) now show correct pin numbers.
- **3D model placement**: models are now XY-centered and Z bottom-aligned on the footprint origin, with EasyEDA `c_origin` translation offset applied (including upstream's Y axis negation and Z-axis canvas-unit scaling). Previously imported models were offset from the footprint reference.
- **Vias (`h_VIA`)**: implemented as plated through-hole (THT) pads matching upstream's `KI_VIA` template. Previously vias were silently dropped via a warning-only stub, breaking thermal relief and ground via connectivity.
- **SOLIDREGION H/V commands**: SVG path parser now handles horizontal (`H`) and vertical (`V`) commands. Rectangular silkscreen/edge-cut outlines are no longer silently truncated.
- **Pad number normalization**: `NAME(NUMBER)`-style EasyEDA pad numbers (e.g. `"A(1)"`, `"VCC(3)"`) are now normalized to the bare number. Fixes BGA/connector imports.
- **macOS KiCad SSL certificate verification**: API client now detects KiCad's bundled `certifi` inside `KiCad.app` (sorted by mtime for newest install) and falls back to the `certifi` package. Prevents `SSL: CERTIFICATE_VERIFY_FAILED` inside KiCad's embedded Python.
- **3D model OBJ→WRL conversion**: removed a corrupt-vertex-ordering `points.insert(-1, points[-1])` line, fixed transparency parser collision with `Kd` lines, added Rec.601 luminance-based `ambientIntensity` computation, and protected `material_id` against unbound variable on malformed OBJ.
- **SOLIDREGION filter**: decorative SOLIDREGIONs on layers 100/101 (lead solder indicators, pin-1 markers) are now dropped via an allow-list, matching upstream. Import output is significantly cleaner.

### Added
- **Opt-in disk cache** for EasyEDA component JSON responses. Gated on `api_cache_enabled` config flag (default `false`). Cache directory: `~/.kicad_lcsc_manager_cache/`. Atomic writes, corrupt-file cleanup, and opt-in-by-default design preserve existing behaviour.
- **Unit test infrastructure** under `tests/`: `test_3d_centering.py` (6), `test_lcsc_cache.py` (7), `test_footprint_handlers_patches.py` (20), `test_symbol_pin_numbers.py` (4), `test_regression_components.py` (2 E2E). Plugin `__init__.py` now guards the KiCad plugin registration so submodules can be imported for testing outside KiCad.

### Notes
- **Backward compatibility**: Footprints imported with previous versions have graphics on the old (wrong) layers. Already-placed footprints in existing projects are unchanged — only new imports use the corrected mappings.
- **Attribution**: Conversion logic adapted from [easyeda2kicad.py v1.0.1](https://github.com/uPesy/easyeda2kicad.py). Each ported function carries a `"Ported from easyeda2kicad.py v1.0.1"` docstring for traceability.

## [0.2.0] - 2026-01-17

### Added
- Advanced component search dialog with multi-parameter filtering
  - Search by component name, value, package type, and manufacturer
  - Support for LCSC ID direct search
  - Enter key support for quick search
- Real-time component search results with detailed information
  - LCSC ID, component name, package type
  - Pricing information from JLCPCB
  - Stock quantity with formatted display
  - Library type indicator (Basic/Extended)
- Sortable search results table
  - Click column headers to sort by any field
  - Ascending/descending order toggle
- Component preview functionality
  - Symbol preview using KiCad native rendering
  - Footprint preview using KiCad native rendering
  - High-quality preview images with 5x supersampling
  - Intelligent footprint cropping and scaling
- Asynchronous preview loading
  - Non-blocking UI for smooth navigation
  - Loading placeholder for immediate feedback
  - Auto-cancel previous requests when selecting new items
  - Preview caching for better performance
- JLCPCB API integration
  - Component search via JLCPCB API
  - Rate limiting with exponential backoff (10s, 20s, 30s)
  - Fresh session per request to avoid 403 errors
  - Enhanced browser headers for reliability
- Responsive dialog layout
  - 1400x900 default size with 1200x800 minimum
  - Balanced splitter layout for results and previews
  - Tab-based preview organization

### Changed
- Improved search workflow with preview before import
- Enhanced user experience with non-blocking UI operations
- Better API reliability with aggressive rate limiting

### Dependencies
- Added `Pillow>=10.0.0` for image processing
- Added `cairosvg>=2.7.0` for SVG to PNG conversion

## [0.1.0] - 2026-01-14

### Added
- Initial release
- Basic component import functionality
  - Import symbols from EasyEDA
  - Import footprints from EasyEDA
  - Import 3D models (WRL and STEP formats)
- LCSC/EasyEDA API integration
- JLCPCB API integration for component information
- Project-specific library management
  - Automatic creation of symbol libraries
  - Automatic creation of footprint libraries
  - Automatic creation of 3D model directories
- Symbol conversion from EasyEDA format to KiCad format
  - Support for rectangles, circles, polygons, polylines, arcs, ellipses
  - Pin conversion with proper electrical types
  - Text elements (reference, value, properties)
- Footprint conversion from EasyEDA format to KiCad format
  - PAD conversion (SMD and through-hole)
  - Copper shapes (tracks, circles, arcs, polygons)
  - Silkscreen and fabrication layers
  - 3D model references
- Configuration management
  - User preferences stored in ~/.kicad/lcsc_manager/
  - Logging system with file output
- KiCad 9.0 compatibility
- KiCad Plugin and Content Manager (PCM) support

### Dependencies
- `requests>=2.31.0`
- `pydantic>=2.5.0`

[0.2.0]: https://github.com/hulryung/kicad-lcsc-manager/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/hulryung/kicad-lcsc-manager/releases/tag/v0.1.0
