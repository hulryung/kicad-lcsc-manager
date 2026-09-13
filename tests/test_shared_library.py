"""Unit tests for the shared library location (follow-up to issue #20):
one library folder for every project, registered in KiCad's global tables.

Run with: python3 tests/test_shared_library.py
"""
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "plugins"))

import lcsc_manager.utils.config as cfgmod
from lcsc_manager.utils.config import (
    Config, PROJECT_CONFIG_FILENAME, validate_shared_path, shared_uri_root,
)
from lcsc_manager.library.lib_table import (
    ensure_lib_entry, read_lib_uri, LibTableError, BACKUP_SUFFIX,
    ADDED, PRESENT, UPDATED, CONFLICT,
)

PLUGIN_DIR = Path(__file__).parent.parent / "plugins" / "lcsc_manager"

# The shape KiCad 10 writes for a fresh global table.
KICAD10_GLOBAL_SYM_TABLE = (
    '(sym_lib_table\n\t(version 7)\n'
    '\t(lib (name "KiCad") (type "Table") (uri "/Applications/KiCad/KiCad.app/'
    'Contents/SharedSupport/template/sym-lib-table") (options "") '
    '(descr "KiCad Default Libraries"))\n)\n'
)


def _tmp():
    return Path(tempfile.mkdtemp())


def _config(global_data=None, project_data=None):
    root = _tmp()
    proj = root / "board"
    proj.mkdir()
    (proj / "board.kicad_pcb").write_text("")
    gfile = root / "global.json"
    if global_data is not None:
        gfile.write_text(json.dumps(global_data))
    if project_data is not None:
        (proj / PROJECT_CONFIG_FILENAME).write_text(json.dumps(project_data))
    cfg = Config(config_path=gfile)
    cfg.load_project_overrides(proj)
    return cfg, proj, root


# ─── config: where files go and how KiCad refers to them ──────────────

def test_project_location_is_unchanged_by_default():
    cfg, proj, _ = _config()
    assert not cfg.is_shared_library()
    assert cfg.get_library_path(proj) == (proj / "libs/lcsc").resolve()
    assert cfg.get_library_uris()["symbol_lib"] == \
        "${KIPRJMOD}/libs/lcsc/symbols/lcsc_imported.kicad_sym"
    assert cfg.get_library_nicknames() == {"symbol": "lcsc_imported",
                                           "footprint": "lcsc_footprints"}
    print("test_project_location_is_unchanged_by_default: PASS")


def test_shared_absolute_folder():
    shared = _tmp() / "Shared" / "lcsc"
    cfg, proj, _ = _config({"library_location": "shared",
                            "shared_library_path": str(shared)})
    assert cfg.is_shared_library()
    assert cfg.get_library_path(proj) == shared.resolve()
    assert cfg.get_footprint_lib_path(proj) == shared.resolve() / "footprints.pretty"
    uris = cfg.get_library_uris()
    assert uris["symbol_lib"] == f"{shared.as_posix()}/symbols/lcsc_imported.kicad_sym"
    assert uris["model_3d_dir"] == f"{shared.as_posix()}/3dmodels"
    assert "KIPRJMOD" not in "".join(uris.values())
    assert cfg.get_library_nicknames() == {"symbol": "lcsc_shared",
                                           "footprint": "lcsc_shared_footprints"}
    assert "shared folder" in cfg.describe_destination(proj)
    # Paths don't depend on any project.
    assert cfg.get_library_path(None) == shared.resolve()
    print("test_shared_absolute_folder: PASS")


def test_shared_tilde_is_expanded_in_uris():
    cfg, _, _ = _config({"library_location": "shared",
                         "shared_library_path": "~/KiCad/lcsc"})
    root = cfg.get_library_uris()["library_root"]
    assert not root.startswith("~"), root          # KiCad doesn't expand ~
    assert root == (Path.home() / "KiCad/lcsc").as_posix()
    print("test_shared_tilde_is_expanded_in_uris: PASS")


def test_shared_path_variable_is_kept_in_uris():
    target = _tmp() / "via-var"
    os.environ["LCSC_TEST_SHARED"] = str(target)
    try:
        cfg, proj, _ = _config({"library_location": "shared",
                                "shared_library_path": "${LCSC_TEST_SHARED}/lcsc"})
        # Files go to the expanded folder...
        assert cfg.get_library_path(proj) == (target / "lcsc").resolve()
        # ...but tables keep the variable, so they survive a move.
        assert cfg.get_library_uris()["footprint_lib"] == \
            "${LCSC_TEST_SHARED}/lcsc/footprints.pretty"
    finally:
        del os.environ["LCSC_TEST_SHARED"]
    print("test_shared_path_variable_is_kept_in_uris: PASS")


def test_undefined_variable_or_unset_folder_is_not_resolved():
    for raw in ("${LCSC_SURELY_UNDEFINED}/lcsc", ""):
        cfg, proj, _ = _config({"library_location": "shared",
                                "shared_library_path": raw})
        assert cfg.get_library_path(proj) is None, raw
        assert "not set" in cfg.describe_destination(proj), raw
    print("test_undefined_variable_or_unset_folder_is_not_resolved: PASS")


def test_windows_folder_uri_uses_forward_slashes():
    assert shared_uri_root("C:\\KiCadLibs\\lcsc\\") == "C:/KiCadLibs/lcsc"
    print("test_windows_folder_uri_uses_forward_slashes: PASS")


def test_validate_shared_path():
    assert validate_shared_path(str(_tmp())) is None
    assert validate_shared_path("~/KiCad/lcsc") is None
    assert "choose a folder" in validate_shared_path("")
    assert "full path" in validate_shared_path("libs/lcsc")
    if os.name != "nt":
        # Not a full path *here*: it would land relative to KiCad's cwd.
        assert "full path" in validate_shared_path("C:\\KiCadLibs\\lcsc")
    err = validate_shared_path("${LCSC_SURELY_UNDEFINED}/x")
    assert "LCSC_SURELY_UNDEFINED" in err and "Configure Paths" in err, err
    print("test_validate_shared_path: PASS")


def test_shared_folder_is_never_written_to_a_project_file():
    """A project file may be committed and opened elsewhere — a folder on this
    computer must not end up in it."""
    cfg, proj, _ = _config()
    cfg.save_project_settings({"library_location": "shared",
                               "shared_library_path": "/Users/me/lcsc"}, proj)
    on_disk = json.loads((proj / PROJECT_CONFIG_FILENAME).read_text())
    assert on_disk == {"library_location": "shared"}, on_disk
    print("test_shared_folder_is_never_written_to_a_project_file: PASS")


def test_hand_edited_project_file_cannot_set_the_shared_folder():
    elsewhere = _tmp()
    cfg, proj, _ = _config({"library_location": "shared",
                            "shared_library_path": str(elsewhere)},
                           {"shared_library_path": "/somebody/elses/machine"})
    assert cfg.get("shared_library_path") == str(elsewhere)
    assert cfg.get_value_source("shared_library_path") == "global"
    assert cfg.get_library_path(proj) == elsewhere.resolve()
    print("test_hand_edited_project_file_cannot_set_the_shared_folder: PASS")


def test_a_project_can_opt_out_of_the_shared_folder():
    """e.g. a team repo that commits its own libraries."""
    cfg, proj, _ = _config({"library_location": "shared",
                            "shared_library_path": str(_tmp())},
                           {"library_location": "project"})
    assert not cfg.is_shared_library()
    assert cfg.get_library_path(proj) == (proj / "libs/lcsc").resolve()
    assert cfg.get_active_scope_summary() == "mixed"
    assert cfg.default_edit_scope(project_open=True) == "project"
    assert "library_location" in cfg.project_override_keys()
    print("test_a_project_can_opt_out_of_the_shared_folder: PASS")


def test_scope_summary_counts_location_only_when_set():
    cfg, _, _ = _config()
    assert cfg.get_active_scope_summary() == "default"
    cfg, _, _ = _config({"library_location": "shared",
                         "shared_library_path": str(_tmp())})
    assert cfg.get_active_scope_summary() == "global"
    print("test_scope_summary_counts_location_only_when_set: PASS")


# ─── global library table editing ─────────────────────────────────────

def test_table_is_created_when_missing():
    table = _tmp() / "fp-lib-table"
    assert ensure_lib_entry(table, "fp", "lcsc_shared_footprints",
                            "/x/footprints.pretty", "shared footprints") == ADDED
    text = table.read_text()
    assert text.startswith("(fp_lib_table\n\t(version 7)\n")
    assert read_lib_uri(table, "lcsc_shared_footprints") == "/x/footprints.pretty"
    assert "LCSC Manager shared footprints" in text
    print("test_table_is_created_when_missing: PASS")


def test_entry_added_to_kicad10_table_keeps_existing_rows():
    table = _tmp() / "sym-lib-table"
    table.write_text(KICAD10_GLOBAL_SYM_TABLE)
    assert ensure_lib_entry(table, "sym", "lcsc_shared", "/x/s.kicad_sym",
                            "shared symbols") == ADDED
    text = table.read_text()
    assert read_lib_uri(table, "KiCad").endswith("template/sym-lib-table")
    assert read_lib_uri(table, "lcsc_shared") == "/x/s.kicad_sym"
    assert text.rstrip().endswith(")") and text.count("(lib ") == 2
    assert '\t(lib (name "lcsc_shared") (type "KiCad")' in text   # KiCad style
    print("test_entry_added_to_kicad10_table_keeps_existing_rows: PASS")


def test_registration_is_idempotent():
    table = _tmp() / "sym-lib-table"
    table.write_text(KICAD10_GLOBAL_SYM_TABLE)
    ensure_lib_entry(table, "sym", "lcsc_shared", "/x/s.kicad_sym", "d")
    before = table.read_text()
    assert ensure_lib_entry(table, "sym", "lcsc_shared", "/x/s.kicad_sym", "d") == PRESENT
    assert table.read_text() == before
    print("test_registration_is_idempotent: PASS")


def test_own_row_follows_a_moved_folder():
    table = _tmp() / "sym-lib-table"
    ensure_lib_entry(table, "sym", "lcsc_shared", "/old/s.kicad_sym", "d")
    assert ensure_lib_entry(table, "sym", "lcsc_shared", "/new/s.kicad_sym", "d") == UPDATED
    assert read_lib_uri(table, "lcsc_shared") == "/new/s.kicad_sym"
    assert table.read_text().count("(lib ") == 1
    print("test_own_row_follows_a_moved_folder: PASS")


def test_someone_elses_row_is_never_touched():
    table = _tmp() / "sym-lib-table"
    foreign = ('(sym_lib_table\n\t(version 7)\n\t(lib (name "lcsc_shared") '
               '(type "KiCad") (uri "/theirs.kicad_sym") (options "") '
               '(descr "my own library"))\n)\n')
    table.write_text(foreign)
    assert ensure_lib_entry(table, "sym", "lcsc_shared", "/ours.kicad_sym", "d") == CONFLICT
    assert table.read_text() == foreign
    assert not table.with_name(table.name + BACKUP_SUFFIX).exists()
    print("test_someone_elses_row_is_never_touched: PASS")


def test_unexpected_file_is_refused_untouched():
    table = _tmp() / "sym-lib-table"
    table.write_text("not a library table")
    try:
        ensure_lib_entry(table, "sym", "lcsc_shared", "/x", "d")
    except LibTableError:
        assert table.read_text() == "not a library table"
        print("test_unexpected_file_is_refused_untouched: PASS")
        return
    raise AssertionError("expected LibTableError")


def test_backup_is_taken_once_before_the_first_edit():
    table = _tmp() / "sym-lib-table"
    table.write_text(KICAD10_GLOBAL_SYM_TABLE)
    backup = table.with_name(table.name + BACKUP_SUFFIX)
    ensure_lib_entry(table, "sym", "lcsc_shared", "/a", "d")
    assert backup.read_text() == KICAD10_GLOBAL_SYM_TABLE
    ensure_lib_entry(table, "sym", "lcsc_shared", "/b", "d")      # updated
    assert backup.read_text() == KICAD10_GLOBAL_SYM_TABLE          # not replaced
    print("test_backup_is_taken_once_before_the_first_edit: PASS")


def test_quotes_and_backslashes_round_trip():
    table = _tmp() / "sym-lib-table"
    uri = 'C:\\odd "name"\\s.kicad_sym'
    ensure_lib_entry(table, "sym", "lcsc_shared", uri, "d")
    assert read_lib_uri(table, "lcsc_shared") == uri
    assert ensure_lib_entry(table, "sym", "lcsc_shared", uri, "d") == PRESENT
    print("test_quotes_and_backslashes_round_trip: PASS")


# ─── LibraryManager wiring (offline) ──────────────────────────────────

def _manager(global_data, with_config_dir=True):
    from lcsc_manager.library.library_manager import LibraryManager
    root = _tmp()
    proj = root / "board"
    proj.mkdir()
    pcb = proj / "board.kicad_pcb"
    pcb.write_text("")
    kicad_dir = root / "kicad-config"
    kicad_dir.mkdir()
    (kicad_dir / "sym-lib-table").write_text(KICAD10_GLOBAL_SYM_TABLE)
    cfg = Config(config_path=root / "global.json")
    cfg.save_global_settings(global_data)
    cfgmod._config_instance = cfg                 # never the real user config
    lm = LibraryManager(pcb, kicad_config_dir=kicad_dir if with_config_dir else None)
    if not with_config_dir:
        lm.kicad_config_dir = lambda: None
    return lm, proj, kicad_dir


def test_manager_registers_globally_once_and_leaves_the_project_alone():
    shared = _tmp() / "lcsc"
    lm, proj, kicad_dir = _manager({"library_location": "shared",
                                    "shared_library_path": str(shared)})
    first = lm._update_library_tables()
    assert any("Restart KiCad" in n for n in first), first
    assert read_lib_uri(kicad_dir / "sym-lib-table", "lcsc_shared") == \
        f"{shared.as_posix()}/symbols/lcsc_imported.kicad_sym"
    assert read_lib_uri(kicad_dir / "fp-lib-table", "lcsc_shared_footprints") == \
        f"{shared.as_posix()}/footprints.pretty"
    assert lm._update_library_tables() == []                  # nothing new
    assert not (proj / "sym-lib-table").exists()
    assert not (proj / "fp-lib-table").exists()
    assert lm._get_footprint_lib_nickname() == "lcsc_shared_footprints"
    print("test_manager_registers_globally_once_and_leaves_the_project_alone: PASS")


def test_manager_reports_a_foreign_nickname():
    lm, _, kicad_dir = _manager({"library_location": "shared",
                                 "shared_library_path": str(_tmp())})
    (kicad_dir / "fp-lib-table").write_text(
        '(fp_lib_table\n\t(version 7)\n\t(lib (name "lcsc_shared_footprints") '
        '(type "KiCad") (uri "/mine.pretty") (options "") (descr "mine"))\n)\n')
    notes = lm._update_library_tables()
    assert any("didn't create" in n for n in notes), notes
    assert read_lib_uri(kicad_dir / "fp-lib-table", "lcsc_shared_footprints") == "/mine.pretty"
    print("test_manager_reports_a_foreign_nickname: PASS")


def test_manager_without_kicad_settings_explains_manual_setup():
    lm, _, _ = _manager({"library_location": "shared",
                         "shared_library_path": str(_tmp())}, with_config_dir=False)
    notes = lm._update_library_tables()
    assert len(notes) == 1 and "Manage Symbol/Footprint Libraries" in notes[0], notes
    print("test_manager_without_kicad_settings_explains_manual_setup: PASS")


def test_import_refuses_an_unusable_shared_folder():
    lm, _, _ = _manager({"library_location": "shared",
                         "shared_library_path": "${LCSC_SURELY_UNDEFINED}/x"})
    try:
        lm.import_component({}, {"lcsc_id": "C1"})
    except RuntimeError as e:
        assert "Settings" in str(e), e
        print("test_import_refuses_an_unusable_shared_folder: PASS")
        return
    raise AssertionError("expected RuntimeError")


# ─── Settings dialog wiring (needs wx to import, so inspect the source) ─

def test_settings_dialog_offers_the_shared_location():
    src = (PLUGIN_DIR / "dialog_settings.py").read_text(encoding="utf-8")
    assert "One shared folder for all projects" in src
    assert "wx.DirDialog" in src
    assert "validate_shared_path(" in src
    assert '"shared_library_path": values["shared_library_path"]' in src, \
        "the shared folder must always be saved to Global"
    print("test_settings_dialog_offers_the_shared_location: PASS")


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
    cfgmod.reset_config_for_tests()
    print("\nAll shared-library tests passed.")
