"""Tests for the fixes that keep the user's libraries intact (0.9.1):

- A file that isn't a symbol library used to be emptied by an import; a
  description with a double quote made the whole library unloadable; and
  importing a part again added a second copy of its symbol.
- Two parts with the same description got the same symbol name.
- The project's library tables were edited by substring matching and
  written in place.
- A footprint that couldn't be written was reported as imported.

With KiCad installed, kicad-cli has to load what the plugin wrote.

Run with: python3 tests/test_symbol_library.py
"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).parent.parent
sys.path.insert(0, str(REPO / "plugins"))

import lcsc_manager.utils.config as cfgmod
from lcsc_manager.utils.config import Config
from lcsc_manager.utils.files import atomic_write_text, sexpr_escape
from lcsc_manager.utils.kicad_host import NullHost
from lcsc_manager.converters.footprint_converter import FootprintConverter
from lcsc_manager.converters.symbol_converter import SymbolConverter
from lcsc_manager.library import symbol_lib
from lcsc_manager.library.library_manager import LibraryManager
from lcsc_manager.library.symbol_lib import SymbolLibraryError

KICAD_CLI = Path("/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli")
PLUGIN_DIR = REPO / "plugins" / "lcsc_manager"


def _pin_line(number, name="NAME"):
    return (f"P~show~0~{number}~290~30~180~gge{number}~0^^290~30^^M290,30h10~#880000"
            f"^^1~0~0~0~{name}~start~~~#0000FF^^1~0~0~0~{number}~end~~~^^0~0~0^^0~")


def _easyeda(pin_name="NAME"):
    return {"dataStr": {"head": {"x": "400", "y": "300"},
                        "shape": ["R~390~290~~~20~20~#000~1~0~none~gge0~0",
                                  _pin_line("1", pin_name), _pin_line("2")]}}


def _info(lcsc_id="C1", description="PART", **extra):
    info = {"description": description, "prefix": "U?", "lcsc_id": lcsc_id,
            "package": "0603", "manufacturer": "ACME", "name": "X-" + lcsc_id}
    info.update(extra)
    return info


def _one(lcsc_id="C1", description="PART", name=None, **extra):
    """A converted one-symbol library."""
    return SymbolConverter().convert(_easyeda(), _info(lcsc_id, description, **extra),
                                     symbol_name=name)


def _names(path):
    return [s.name for s in symbol_lib.list_symbols(path)]


def _manager():
    root = Path(tempfile.mkdtemp())
    proj = root / "board"
    proj.mkdir()
    pcb = proj / "board.kicad_pcb"
    pcb.write_text("")
    cfgmod._config_instance = Config(config_path=root / "global.json")   # never the user's
    return LibraryManager(pcb, kicad_config_dir=root, host=NullHost()), proj


def _kicad_loads(path):
    """True/False from kicad-cli, or None without KiCad."""
    if not KICAD_CLI.exists():
        return None
    out = Path(tempfile.mkdtemp())
    run = subprocess.run([str(KICAD_CLI), "sym", "export", "svg", "-o", str(out), str(path)],
                         capture_output=True, text=True,
                         env=dict(os.environ, KICAD_CONFIG_HOME=str(out / "cfg")))
    return "Unable to load" not in run.stdout + run.stderr and any(out.glob("*.svg"))


# ─── escaping ─────────────────────────────────────────────────────────

def test_quotes_and_backslashes_are_escaped():
    assert sexpr_escape('10k "thick film"') == '10k \\"thick film\\"'
    assert sexpr_escape("a\\b") == "a\\\\b"
    assert sexpr_escape("two\nlines") == "two\\nlines"
    assert sexpr_escape(None) == "" and sexpr_escape(5) == "5"
    print("test_quotes_and_backslashes_are_escaped: PASS")


def test_a_quoted_description_no_longer_breaks_the_library():
    lib = Path(tempfile.mkdtemp()) / "lib.kicad_sym"
    conv = SymbolConverter()
    conv.save_to_library(_one("C1", "PLAIN"), lib)
    nasty = conv.convert(
        _easyeda(pin_name='A"B\\'),
        _info("C2", '10k "thick film" 1%', manufacturer='ACME "Co"\\',
              datasheet='http://x/"y"', prefix='R"?'))
    conv.save_to_library(nasty, lib)
    conv.save_to_library(_one("C3", "AFTER"), lib)
    symbols = symbol_lib.list_symbols(lib)           # parses: quotes are balanced
    assert [s.lcsc_id for s in symbols] == ["C1", "C2", "C3"], symbols
    text = lib.read_text(encoding="utf-8")
    assert '"10k \\"thick film\\" 1%"' in text and '(name "A\\"B\\\\"' in text
    loads = _kicad_loads(lib)
    assert loads is not False, "kicad-cli must be able to load the library"
    print("test_a_quoted_description_no_longer_breaks_the_library: PASS"
          + ("" if loads else " (kicad-cli check skipped)"))


# ─── the library file ─────────────────────────────────────────────────

def test_a_file_that_is_not_a_library_is_left_untouched():
    folder = Path(tempfile.mkdtemp())
    cases = {
        "notes.kicad_sym": "my notes, not a library\n",
        "table.kicad_sym": "(sym_lib_table\n\t(version 7)\n)\n",
        "open.kicad_sym": '(kicad_symbol_lib\n  (version 20241209)\n  (symbol "A"\n',
        "extra.kicad_sym": '(kicad_symbol_lib (version 1))\n(symbol "B")\n',
        "quote.kicad_sym": '(kicad_symbol_lib (symbol "A" (property "V" "x)))\n',
    }
    for name, content in cases.items():
        path = folder / name
        path.write_text(content, encoding="utf-8")
        try:
            SymbolConverter().save_to_library(_one(), path)
        except IOError as e:
            assert "left as it is" in str(e), e
        else:
            raise AssertionError(f"{name}: must be refused")
        assert path.read_text(encoding="utf-8") == content, f"{name} was modified"
    assert not list(folder.glob("*.tmp")), "no temporary files left behind"
    print("test_a_file_that_is_not_a_library_is_left_untouched: PASS")


def test_bom_marker_and_empty_files_are_handled():
    folder = Path(tempfile.mkdtemp())
    with_bom = folder / "bom.kicad_sym"
    with_bom.write_text("﻿" + _one("C1", "FIRST"), encoding="utf-8")
    SymbolConverter().save_to_library(_one("C2", "SECOND"), with_bom)
    assert _names(with_bom) == ["FIRST", "SECOND"], "0.9.0 emptied this file"
    # A file an older version emptied is simply a library with nothing in it.
    empty = folder / "empty.kicad_sym"
    empty.write_text("")
    SymbolConverter().save_to_library(_one("C2", "SECOND"), empty)
    assert _names(empty) == ["SECOND"]
    print("test_bom_marker_and_empty_files_are_handled: PASS")


def test_importing_again_replaces_the_symbol():
    lib = Path(tempfile.mkdtemp()) / "lib.kicad_sym"
    assert symbol_lib.put_symbol(lib, _one("C1", "FIRST")) == "created"
    assert symbol_lib.put_symbol(lib, _one("C2", "SECOND")) == "added"
    assert symbol_lib.put_symbol(lib, _one("C3", "THIRD")) == "added"
    updated = _one("C2", "SECOND", manufacturer="NEW MAKER")
    assert symbol_lib.put_symbol(lib, updated) == "replaced"
    assert _names(lib) == ["FIRST", "SECOND", "THIRD"], "order kept, no second copy"
    text = lib.read_text(encoding="utf-8")
    assert "NEW MAKER" in text and text.count("ACME") == 2
    assert text.count("(kicad_symbol_lib") == 1 and text.rstrip().endswith(")")
    print("test_importing_again_replaces_the_symbol: PASS")


def test_copies_left_by_older_versions_are_collapsed():
    """0.9.0 and earlier appended a copy on every re-import."""
    lib = Path(tempfile.mkdtemp()) / "lib.kicad_sym"

    def block(text):
        symbol = symbol_lib._scan(text, "test")[0][0]
        return text[symbol.start:symbol.end]
    dup, keep = block(_one("C1", "DUP")), block(_one("C2", "KEEP"))
    lib.write_text(f"(kicad_symbol_lib\n  (version 20241209)\n  {dup}\n  {dup}\n"
                   f"  {keep}\n  {dup}\n)\n", encoding="utf-8")
    assert _names(lib) == ["DUP", "DUP", "KEEP", "DUP"]
    assert symbol_lib.put_symbol(lib, _one("C1", "DUP")) == "replaced"
    assert _names(lib) == ["DUP", "KEEP"]
    print("test_copies_left_by_older_versions_are_collapsed: PASS")


def test_compact_formatting_survives():
    """The old code stripped every trailing ')', eating the last symbol's."""
    lib = Path(tempfile.mkdtemp()) / "lib.kicad_sym"
    lib.write_text('(kicad_symbol_lib (version 20241209) (symbol "A" (property "LCSC" "C9")))',
                   encoding="utf-8")
    symbol_lib.put_symbol(lib, _one("C1", "B"))
    assert _names(lib) == ["A", "B"]
    symbol_lib.put_symbol(lib, _one("C1", "B"))
    assert _names(lib) == ["A", "B"]
    print("test_compact_formatting_survives: PASS")


# ─── names ────────────────────────────────────────────────────────────

def test_two_parts_never_share_a_symbol_name():
    lib = Path(tempfile.mkdtemp()) / "lib.kicad_sym"
    choose = symbol_lib.choose_symbol_name
    assert choose(lib, "10k", "C1") == "10k"                 # no library yet
    symbol_lib.put_symbol(lib, _one("C1", "10k"))
    assert choose(lib, "10k", "C1") == "10k", "the same part keeps its name"
    assert choose(lib, "10k", "C2") == "10k_C2", "another part gets its own"
    symbol_lib.put_symbol(lib, _one("C2", "10k", name="10k_C2"))
    assert choose(lib, "10k", "C2") == "10k_C2"
    # Renamed by the user in KiCad: still found through its LCSC property.
    lib.write_text(lib.read_text().replace('"10k_C2', '"R_10k_0402'), encoding="utf-8")
    assert choose(lib, "10k", "C2") == "R_10k_0402"
    # A symbol the user drew, with no LCSC property, isn't taken over.
    lib.write_text('(kicad_symbol_lib (symbol "MINE" (property "Value" "x")))')
    assert choose(lib, "MINE", "C5") == "MINE_C5"
    print("test_two_parts_never_share_a_symbol_name: PASS")


def test_a_part_without_a_description_still_gets_a_name():
    name = SymbolConverter()._get_symbol_name
    assert name({"description": "", "name": "ABC 1", "lcsc_id": "C7"}) == "ABC_1"
    assert name({"description": None, "lcsc_id": "C7"}) == "C7"
    assert name({}) == "Unknown"
    print("test_a_part_without_a_description_still_gets_a_name: PASS")


def test_library_manager_reimport_and_same_description():
    lm, proj = _manager()
    first = lm._import_symbol(_easyeda(), _info("C100", "10KΩ ±1%"))
    again = lm._import_symbol(_easyeda(), _info("C100", "10KΩ ±1%"))
    other = lm._import_symbol(_easyeda(), _info("C200", "10KΩ ±1%"))
    assert first == again == "10KΩ_±1%" and other == "10KΩ_±1%_C200"
    symbols = symbol_lib.list_symbols(lm.symbol_lib_path)
    assert [(s.name, s.lcsc_id) for s in symbols] == \
        [("10KΩ_±1%", "C100"), ("10KΩ_±1%_C200", "C200")]
    # Unit sub-symbols follow the chosen name.
    assert '(symbol "10KΩ_±1%_C200_1_1"' in lm.symbol_lib_path.read_text(encoding="utf-8")
    loads = _kicad_loads(lm.symbol_lib_path)
    assert loads is not False
    print("test_library_manager_reimport_and_same_description: PASS")


def test_find_existing_reports_what_an_import_would_replace():
    lm, proj = _manager()
    assert lm.find_existing("C100") == {"symbol": False, "footprint": False, "model_3d": False}
    lm._import_symbol(_easyeda(), _info("C100", "PART"))
    lm.footprint_lib_path.mkdir(parents=True)
    (lm.footprint_lib_path / "C100_0603.kicad_mod").write_text("")
    (lm.footprint_lib_path / "C1000_0603.kicad_mod").write_text("")
    lm.model_3d_path.mkdir(parents=True)
    (lm.model_3d_path / "C100.step").write_text("")
    assert lm.find_existing("C100") == {"symbol": True, "footprint": True, "model_3d": True}
    assert lm.find_existing("C10") == {"symbol": False, "footprint": False, "model_3d": False}
    assert lm.find_existing("C1000") == {"symbol": False, "footprint": True, "model_3d": False}
    assert lm.imported_symbol_ids() == {"C100"}
    lm.symbol_lib_path.write_text("not a library")
    assert lm.find_existing("C100")["symbol"] is False       # unreadable: no crash
    print("test_find_existing_reports_what_an_import_would_replace: PASS")


# ─── footprints ───────────────────────────────────────────────────────

def test_a_footprint_that_cannot_be_written_is_an_error():
    folder = Path(tempfile.mkdtemp())
    blocker = folder / "footprints.pretty"
    blocker.write_text("a file where the library folder should be")
    try:
        FootprintConverter().save_to_library("(footprint)", "C1_0603", blocker)
    except IOError:
        pass
    else:
        raise AssertionError("0.9.0 returned False here and the import said OK")
    lm, _ = _manager()
    lm.footprint_lib_path.parent.mkdir(parents=True)
    lm.footprint_lib_path.write_text("blocked")
    lm.footprint_converter.convert = lambda *a: "(footprint)"
    result = lm.import_component({}, _info("C1"), False, True, False)
    assert result["success"] is False and result["footprint"] is None
    assert any("Footprint import failed" in e for e in result["errors"])
    print("test_a_footprint_that_cannot_be_written_is_an_error: PASS")


def test_atomic_write_leaves_the_old_file_on_failure():
    path = Path(tempfile.mkdtemp()) / "f.txt"
    path.write_text("old")
    try:
        atomic_write_text(path, 5)                  # not text: write() fails
    except TypeError:
        pass
    assert path.read_text() == "old" and not list(path.parent.glob("*.tmp"))
    atomic_write_text(path, "new")
    assert path.read_text() == "new"
    print("test_atomic_write_leaves_the_old_file_on_failure: PASS")


# ─── the project's library tables ─────────────────────────────────────

def test_project_tables_match_rows_not_substrings():
    lm, proj = _manager()
    table = proj / "sym-lib-table"
    table.write_text('(sym_lib_table\n\t(version 7)\n'
                     '\t(lib (name "lcsc_imported_old") (type "KiCad") '
                     '(uri "${KIPRJMOD}/old.kicad_sym") (options "") '
                     '(descr "see lcsc_imported"))\n)\n')
    assert lm._update_symbol_lib_table() is None
    text = table.read_text()
    assert '(name "lcsc_imported")' in text, "0.9.0 skipped this: the nickname was a substring"
    assert text.count("(lib ") == 2 and text.rstrip().endswith(")")
    assert lm._update_symbol_lib_table() is None and table.read_text() == text
    assert not list(proj.glob("*.bak")), "no backup files in the project folder"
    print("test_project_tables_match_rows_not_substrings: PASS")


def test_project_table_rows_from_older_versions_are_accepted():
    lm, proj = _manager()
    old_row = ('(fp_lib_table\n  (version 7)\n  (lib (name "lcsc_footprints")(type "KiCad")'
               '(uri "${KIPRJMOD}/libs/lcsc/footprints.pretty")(options "")'
               '(descr "LCSC imported footprints"))\n)\n')
    (proj / "fp-lib-table").write_text(old_row)
    notice, added = lm._update_footprint_lib_table_file(
        "lcsc_footprints", "${KIPRJMOD}/libs/lcsc/footprints.pretty")
    assert (notice, added) == (None, False) and (proj / "fp-lib-table").read_text() == old_row
    # The same place written as an absolute path: still fine, still untouched.
    absolute = old_row.replace("${KIPRJMOD}", str(proj))
    (proj / "fp-lib-table").write_text(absolute)
    assert lm._update_footprint_lib_table_file(
        "lcsc_footprints", "${KIPRJMOD}/libs/lcsc/footprints.pretty") == (None, False)
    print("test_project_table_rows_from_older_versions_are_accepted: PASS")


def test_a_row_pointing_elsewhere_is_reported_not_overwritten():
    lm, proj = _manager()
    theirs = ('(fp_lib_table\n\t(version 7)\n\t(lib (name "lcsc_footprints") (type "KiCad") '
              '(uri "${KIPRJMOD}/somewhere/else.pretty") (options "") (descr "mine"))\n)\n')
    (proj / "fp-lib-table").write_text(theirs)
    notice, added = lm._update_footprint_lib_table_file(
        "lcsc_footprints", "${KIPRJMOD}/libs/lcsc/footprints.pretty")
    assert added is False and "left alone" in notice and "somewhere/else.pretty" in notice
    assert (proj / "fp-lib-table").read_text() == theirs
    # Not a table at all: refused, with instructions.
    (proj / "sym-lib-table").write_text("garbage")
    notice = lm._update_symbol_lib_table()
    assert "Couldn't update the project's sym-lib-table" in notice
    assert (proj / "sym-lib-table").read_text() == "garbage"
    print("test_a_row_pointing_elsewhere_is_reported_not_overwritten: PASS")


# ─── dialogs (need wx to import, so inspect the source) ───────────────

def test_dialogs_ask_before_replacing():
    search = (PLUGIN_DIR / "dialog_search.py").read_text(encoding="utf-8")
    confirm = search.split("def _import_confirm")[1].split("def _import_run")[0]
    assert "find_existing(" in confirm and "wx.NO_DEFAULT" in confirm
    assert "import_component(" not in confirm, "nothing is written before the answer"
    fetch = search.split("def _import_async")[1].split("def _import_confirm")[0]
    assert "import_component(" not in fetch and "self._import_confirm" in fetch
    bom = (PLUGIN_DIR / "dialog_bom.py").read_text(encoding="utf-8")
    assert "_confirm_replacing(selected, options)" in bom and '"Skip those"' in bom
    basic = (PLUGIN_DIR / "dialog.py").read_text(encoding="utf-8")
    check = basic.split("def _check_existing_files")[1].split("def GetLCSCId")[0]
    assert "find_existing(" in check and 'get("description"' not in check
    print("test_dialogs_ask_before_replacing: PASS")


CONFIRM_SCRIPT = """
import sys, tempfile, threading, time
from pathlib import Path
sys.path.insert(0, {plugins!r})
import wx
app = wx.App(False)
app.SetAssertMode(wx.APP_ASSERT_LOG)
import lcsc_manager.utils.config as cfgmod
from lcsc_manager.utils.config import Config
root = Path(tempfile.mkdtemp()); pcb = root / "b.kicad_pcb"; pcb.write_text("")
cfgmod._config_instance = Config(config_path=root / "g.json")      # never the user's
from lcsc_manager.dialog_search import LCSCManagerSearchDialog

dlg = LCSCManagerSearchDialog(None, str(pcb))
lm = dlg.library_manager
asked, imported = [], []
answer = [wx.NO]
def message_box(message, caption="", style=0, parent=None):
    asked.append(caption)
    return answer[0]
wx.MessageBox = message_box
def fake_import(**kw):
    imported.append(kw["component_info"]["lcsc_id"])
    return {{"success": True, "symbol": "S", "footprint": None, "model_3d": None,
            "errors": [], "notifications": [], "restart_required": False}}
lm.import_component = fake_import
info = {{"lcsc_id": "C100", "description": "PART", "easyeda_data": {{"x": 1}}}}

def progress():
    dlg._import_progress = wx.GenericProgressDialog("t", "m", maximum=100, parent=dlg)

def wait_for_import():
    deadline = time.time() + 10
    while dlg._import_progress is not None and time.time() < deadline:
        wx.Yield(); time.sleep(0.02)

# 1. Not in the library: imported without a question.
progress(); dlg._import_confirm(info, "C100", True, True, True); wait_for_import()
print("new part:", asked, imported)

# 2. Already there, user says No: nothing written, progress dialog gone.
lm.find_existing = lambda lcsc_id, symbol_ids=None: {{"symbol": True, "footprint": True, "model_3d": False}}
progress(); dlg._import_confirm(info, "C100", True, True, True); wait_for_import()
print("declined:", asked, imported, dlg._import_progress is None)

# 3. Only the 3D model is wanted and there is none: no question.
progress(); dlg._import_confirm(info, "C100", False, False, True); wait_for_import()
print("3d only:", asked, imported)

# 4. Already there, user says Yes.
answer[0] = wx.YES
progress(); dlg._import_confirm(info, "C100", True, True, True); wait_for_import()
print("replaced:", asked, imported, dlg._import_progress is None)
dlg.Destroy()
"""


def test_search_dialog_confirm_flow_under_kicad_python():
    """The real dialog under KiCad's Python (skipped without KiCad)."""
    kicad_python = Path("/Applications/KiCad/KiCad.app/Contents/Frameworks/"
                        "Python.framework/Versions/Current/bin/python3")
    if not kicad_python.exists():
        print("test_search_dialog_confirm_flow_under_kicad_python: SKIP (no KiCad python)")
        return
    home = tempfile.mkdtemp()
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "PYTHONHOME")}
    env.update(HOME=home, KICAD_CONFIG_HOME=home, KICAD_API_TOKEN="t")   # no SWIG registration
    run = subprocess.run([str(kicad_python), "-c",
                          CONFIRM_SCRIPT.format(plugins=str(REPO / "plugins"))],
                         capture_output=True, text=True, env=env, timeout=300)
    out = run.stdout
    assert run.returncode == 0, run.stderr[-1500:]
    assert "new part: [] ['C100']" in out, out
    assert "declined: ['Already Imported'] ['C100'] True" in out, out
    assert "3d only: ['Already Imported'] ['C100', 'C100']" in out, out
    assert "replaced: ['Already Imported', 'Already Imported'] ['C100', 'C100', 'C100'] True" in out, out
    print("test_search_dialog_confirm_flow_under_kicad_python: PASS")


if __name__ == "__main__":
    try:
        for name, fn in list(globals().items()):
            if name.startswith("test_") and callable(fn):
                fn()
    finally:
        cfgmod.reset_config_for_tests()
    print("\nAll symbol-library tests passed.")
