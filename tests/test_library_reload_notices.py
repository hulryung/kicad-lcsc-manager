"""Unit tests for library-table notices:

- KiCad 10 no longer wraps FP_LIB_TABLE / PROJECT for Python, so a project's
  new footprint library can only be written to fp-lib-table; the running
  session won't see it until the project is reopened. The plugin asks the
  KiCad host (pcbnew.GetFootprintLibraries inside pcbnew; over IPC, where that
  can't be asked, "was the row just added") and says so only when it's true.
- A restart/reopen notice makes the generic "reopen the schematic editor"
  hint redundant, and each notice appears once per dialog session.

Run with: python3 tests/test_library_reload_notices.py
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "plugins"))

import lcsc_manager.utils.config as cfgmod
from lcsc_manager.utils.config import Config
from lcsc_manager.utils.kicad_host import IpcHost, NullHost, SwigHost
from lcsc_manager.utils.session import ImportSession
from lcsc_manager.library.library_manager import LibraryManager
from lcsc_manager.bom.bom_importer import BomImporter, BomImportOptions
from lcsc_manager.bom.bom_parser import BomEntry

PLUGIN_DIR = Path(__file__).parent.parent / "plugins" / "lcsc_manager"
SYM_TABLE = ('(sym_lib_table\n\t(version 7)\n\t(lib (name "KiCad") (type "Table") '
             '(uri "/x/sym-lib-table") (options "") (descr "KiCad Default Libraries"))\n)\n')


class _FakePcbnew10:
    """pcbnew as KiCad 10 wraps it: no FP_LIB_TABLE_ROW; a live library
    listing. Wrapped in a real SwigHost by the tests."""
    def __init__(self, loaded=()):
        self._loaded = list(loaded)

    def GetFootprintLibraries(self):
        return list(self._loaded)


class _FakePcbnew9(_FakePcbnew10):
    """KiCad 9's shape: the in-memory table API exists."""
    FP_LIB_TABLE_ROW = object()


def _manager(global_data=None, host=None):
    root = Path(tempfile.mkdtemp())
    proj = root / "board"
    proj.mkdir()
    pcb = proj / "board.kicad_pcb"
    pcb.write_text("")
    kicad_dir = root / "kicad-config"
    kicad_dir.mkdir()
    (kicad_dir / "sym-lib-table").write_text(SYM_TABLE)
    cfg = Config(config_path=root / "global.json")
    if global_data:
        cfg.save_global_settings(global_data)
    cfgmod._config_instance = cfg                  # never the real user config
    host = host if host is not None else NullHost()
    return LibraryManager(pcb, kicad_config_dir=kicad_dir, host=host), proj


def _import_nothing(lm):
    """Run the import pipeline without converting anything, so only the
    library-table step does work (no network, no EasyEDA data)."""
    return lm.import_component({}, {"lcsc_id": "C1"}, False, False, False)


def _restore():
    cfgmod.reset_config_for_tests()


# ─── session ──────────────────────────────────────────────────────────

def test_each_notification_is_shown_once_per_session():
    s = ImportSession()
    assert s.new_notifications(["a", "b"]) == ["a", "b"]
    assert s.new_notifications(["b", "c"]) == ["c"]
    assert s.new_notifications(["a"]) == []
    print("test_each_notification_is_shown_once_per_session: PASS")


# ─── project location on KiCad 10 ─────────────────────────────────────

def test_kicad10_unloaded_library_is_reported():
    host = SwigHost(_FakePcbnew10(loaded=["KiCad_Footprints"]))
    lm, proj = _manager(host=host)
    lm.footprint_lib_path.mkdir(parents=True)        # a footprint was imported
    called = []
    host.register_footprint_library_in_memory = lambda *a: called.append(a)
    result = _import_nothing(lm)
    assert called == [], "KiCad 10 has no FP_LIB_TABLE_ROW; the API path must be skipped"
    assert (proj / "fp-lib-table").exists()
    assert result["restart_required"] is True
    assert any("hasn't loaded the LCSC footprint library" in n
               for n in result["notifications"]), result["notifications"]
    print("test_kicad10_unloaded_library_is_reported: PASS")


def test_kicad10_symbol_only_import_says_nothing_about_footprints():
    """No footprint folder means nothing to place — and KiCad 10 leaves such
    a library out even after a reopen, so the notice would mislead."""
    lm, _ = _manager(host=SwigHost(_FakePcbnew10(loaded=[])))
    assert not lm.footprint_lib_path.exists()
    result = _import_nothing(lm)
    assert result["restart_required"] is False
    assert result["notifications"] == [], result["notifications"]
    print("test_kicad10_symbol_only_import_says_nothing_about_footprints: PASS")


def test_kicad10_library_already_loaded_stays_quiet():
    lm, _ = _manager(host=SwigHost(_FakePcbnew10(loaded=["lcsc_footprints"])))
    lm.footprint_lib_path.mkdir(parents=True)        # footprints exist...
    result = _import_nothing(lm)                     # ...and are loaded
    assert result["restart_required"] is False
    assert result["notifications"] == [], result["notifications"]
    print("test_kicad10_library_already_loaded_stays_quiet: PASS")


def test_outside_kicad_no_false_alarm():
    lm, proj = _manager(host=NullHost())
    lm.footprint_lib_path.mkdir(parents=True)
    result = _import_nothing(lm)
    assert (proj / "fp-lib-table").exists()
    assert result["restart_required"] is False
    assert result["notifications"] == []
    print("test_outside_kicad_no_false_alarm: PASS")


def test_kicad9_keeps_the_in_memory_route():
    host = SwigHost(_FakePcbnew9(loaded=[]))
    lm, proj = _manager(host=host)
    calls = []
    host.register_footprint_library_in_memory = \
        lambda name, uri, table: calls.append(name) or True
    result = _import_nothing(lm)
    assert calls == ["lcsc_footprints"]
    assert not (proj / "fp-lib-table").exists(), "in-memory route saves via KiCad itself"
    assert result["restart_required"] is False and result["notifications"] == []
    print("test_kicad9_keeps_the_in_memory_route: PASS")


# ─── project location over IPC ────────────────────────────────────────

def test_ipc_reports_a_just_added_library_once():
    """The IPC API can't list loaded libraries. A row added just now wasn't
    in the table when the project opened, so it can't be loaded yet; a row
    that was already there is left alone."""
    lm, _ = _manager(host=IpcHost(kicad=object()))
    lm.footprint_lib_path.mkdir(parents=True)
    first = _import_nothing(lm)
    assert first["restart_required"] is True
    assert any("hasn't loaded the LCSC footprint library" in n
               for n in first["notifications"]), first["notifications"]
    second = _import_nothing(lm)
    assert second["restart_required"] is False
    assert second["notifications"] == [], second["notifications"]
    print("test_ipc_reports_a_just_added_library_once: PASS")


# ─── shared location ──────────────────────────────────────────────────

def test_shared_first_registration_requires_restart_once():
    lm, _ = _manager({"library_location": "shared",
                      "shared_library_path": str(Path(tempfile.mkdtemp()))},
                     host=SwigHost(_FakePcbnew10()))
    first = _import_nothing(lm)
    assert first["restart_required"] is True
    second = _import_nothing(lm)
    assert second["restart_required"] is False and second["notifications"] == []
    print("test_shared_first_registration_requires_restart_once: PASS")


# ─── BOM batches ──────────────────────────────────────────────────────

def test_bom_summary_carries_restart_required():
    class _Api:
        def search_component(self, lcsc_id):
            return {"lcsc_id": lcsc_id, "easyeda_data": {"stub": True}}

    class _Lib:
        def __init__(self):
            self.n = 0

        def import_component(self, *a, **k):
            self.n += 1
            return {"symbol": "S", "footprint": "F", "model_3d": {"w": 1},
                    "success": True, "errors": [],
                    "notifications": ["Reopen."] if self.n == 1 else [],
                    "restart_required": self.n == 1}

    summary = BomImporter(_Api(), _Lib()).import_entries(
        [BomEntry("C1"), BomEntry("C2")], BomImportOptions())
    assert summary.restart_required is True
    assert summary.notifications == ["Reopen."]
    print("test_bom_summary_carries_restart_required: PASS")


# ─── dialog wiring (needs wx to import, so inspect the source) ────────

def test_dialogs_gate_the_reopen_hint_on_restart_notices():
    search = (PLUGIN_DIR / "dialog_search.py").read_text(encoding="utf-8")
    basic = (PLUGIN_DIR / "dialog.py").read_text(encoding="utf-8")
    bom = (PLUGIN_DIR / "dialog_bom.py").read_text(encoding="utf-8")
    assert "self.session.new_notifications(" in search
    assert "self.session.new_notifications(" in basic
    assert "and not restart_required" in search
    assert 'and not results.get("restart_required")' in basic
    assert "and not summary.restart_required" in bom
    # Notifications are no longer baked into the message on the worker thread.
    worker = search.split("def _import_async")[1].split("def _import_progress_update")[0]
    assert "lines.extend(notifications)" not in worker
    print("test_dialogs_gate_the_reopen_hint_on_restart_notices: PASS")


if __name__ == "__main__":
    try:
        for name, fn in list(globals().items()):
            if name.startswith("test_") and callable(fn):
                fn()
    finally:
        _restore()
    print("\nAll reload-notice tests passed.")
