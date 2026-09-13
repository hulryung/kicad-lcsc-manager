"""Unit tests for issue #20: Global settings looked unsaved and were
shadowed by project overrides.

Run with: python3 tests/test_issue20_settings_scope.py
"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "plugins"))

from lcsc_manager.utils.config import (
    Config, PATH_KEYS, PROJECT_CONFIG_FILENAME, validate_path_value,
)

PLUGIN_DIR = Path(__file__).parent.parent / "plugins" / "lcsc_manager"
DEFAULTS = {k: Config.DEFAULT_CONFIG[k] for k in PATH_KEYS}


def _project(global_data=None, project_data=None):
    """A fresh (Config, project_dir) pair backed by temp files."""
    root = Path(tempfile.mkdtemp())
    proj = root / "board"
    proj.mkdir()
    gfile = root / "global.json"
    if global_data is not None:
        gfile.write_text(json.dumps(global_data))
    if project_data is not None:
        (proj / PROJECT_CONFIG_FILENAME).write_text(json.dumps(project_data))
    cfg = Config(config_path=gfile)
    cfg.load_project_overrides(proj)
    return cfg, proj


# ─── (a) open on the scope that supplies the settings ─────────────────

def test_opens_on_global_when_nothing_is_overridden():
    cfg, _ = _project()
    assert cfg.default_edit_scope(project_open=True) == "global"
    print("test_opens_on_global_when_nothing_is_overridden: PASS")


def test_opens_on_global_after_a_global_save():
    """The reported sequence: save at Global, reopen — it must come back on
    Global instead of looking as if the save was discarded."""
    cfg, _ = _project()
    cfg.save_global_settings(dict(DEFAULTS, library_path="team/lcsc"))
    assert cfg.default_edit_scope(project_open=True) == "global"
    print("test_opens_on_global_after_a_global_save: PASS")


def test_opens_on_project_when_the_project_overrides():
    cfg, _ = _project(project_data={"library_path": "p"})          # mixed
    assert cfg.default_edit_scope(project_open=True) == "project"
    cfg, _ = _project(project_data=dict(DEFAULTS, library_path="p"))  # full
    assert cfg.default_edit_scope(project_open=True) == "project"
    print("test_opens_on_project_when_the_project_overrides: PASS")


def test_opens_on_global_without_a_project():
    cfg, _ = _project(project_data={"library_path": "p"})
    assert cfg.default_edit_scope(project_open=False) == "global"
    print("test_opens_on_global_without_a_project: PASS")


# ─── (b) project saves store only what differs ────────────────────────

def test_project_save_stores_only_changed_values():
    cfg, proj = _project(global_data={"library_path": "team/lcsc"})
    stored = cfg.save_project_settings(
        dict(DEFAULTS, library_path="team/lcsc", model_3d_path="models"), proj)
    assert stored == {"model_3d_path": "models"}, stored
    on_disk = json.loads((proj / PROJECT_CONFIG_FILENAME).read_text())
    assert on_disk == {"model_3d_path": "models"}, on_disk
    print("test_project_save_stores_only_changed_values: PASS")


def test_project_save_no_longer_shadows_later_global_changes():
    """The trap behind #20: a first Save at project scope used to pin all
    four keys, so a later Global change never reached this project."""
    cfg, proj = _project()
    cfg.save_project_settings(dict(DEFAULTS), proj)           # untouched Save
    cfg.save_global_settings(dict(DEFAULTS, library_path="team/lcsc"))
    assert cfg.get("library_path") == "team/lcsc"
    assert cfg.get_library_path(proj) == (proj / "team/lcsc").resolve()
    print("test_project_save_no_longer_shadows_later_global_changes: PASS")


def test_project_save_with_nothing_changed_removes_the_file():
    cfg, proj = _project(project_data={"library_path": "old"})
    stored = cfg.save_project_settings(dict(DEFAULTS), proj)
    assert stored == {}
    assert not (proj / PROJECT_CONFIG_FILENAME).exists()
    assert cfg.get_active_scope_summary() == "default"
    print("test_project_save_with_nothing_changed_removes_the_file: PASS")


def test_project_save_keeps_non_path_keys():
    cfg, proj = _project(project_data={"library_path": "p", "api_timeout": 99})
    cfg.save_project_settings(dict(DEFAULTS), proj)
    on_disk = json.loads((proj / PROJECT_CONFIG_FILENAME).read_text())
    assert on_disk == {"api_timeout": 99}, on_disk
    print("test_project_save_keeps_non_path_keys: PASS")


def test_global_save_drops_values_equal_to_default():
    cfg, _ = _project(global_data={"library_path": "x", "model_3d_path": "m"})
    cfg.save_global_settings(dict(DEFAULTS, library_path="team/lcsc"))
    assert cfg.get_scope_values("global") == {"library_path": "team/lcsc"}
    print("test_global_save_drops_values_equal_to_default: PASS")


def test_existing_full_override_is_reported():
    """Projects saved by older versions already pin all four keys; the dialog
    must be able to say so and offer to remove them."""
    cfg, proj = _project(project_data=dict(DEFAULTS))
    cfg.save_global_settings(dict(DEFAULTS, library_path="team/lcsc"))
    assert cfg.project_override_keys() == list(PATH_KEYS)
    assert cfg.get("library_path") == "libs/lcsc"                  # shadowed
    cfg.clear_scope("project", proj)                               # "Yes"
    assert cfg.project_override_keys() == []
    assert cfg.get("library_path") == "team/lcsc"
    print("test_existing_full_override_is_reported: PASS")


# ─── (d) absolute paths are rejected on every OS ──────────────────────

def test_validation():
    ok = ("libs/lcsc", "sub/dir", "3dmodels", "footprints.pretty", "a\\b")
    bad_absolute = ("/abs", "~/x", "\\root", "C:\\libs", "C:/libs", "C:libs",
                    "\\\\server\\share")
    bad_parent = ("a/../b", "a\\..\\b", "..")
    for raw in ok:
        assert validate_path_value("library_path", raw) is None, raw
    for raw in bad_absolute:
        err = validate_path_value("library_path", raw)
        assert err and "project-relative" in err, (raw, err)
    for raw in bad_parent:
        assert validate_path_value("library_path", raw) == "must not contain '..'.", raw
    assert validate_path_value("library_path", "") == "must not be empty."
    print("test_validation: PASS")


# ─── dialog wiring (needs wx to import, so inspect the source) ────────

def test_dialog_uses_the_new_behaviour():
    src = (PLUGIN_DIR / "dialog_settings.py").read_text(encoding="utf-8")
    assert 'self._set_scope("project" if project_path else "global")' not in src, \
        "dialog hard-codes the project scope again"
    assert "default_edit_scope(" in src
    assert "save_project_settings(" in src and "save_global_settings(" in src
    assert "project_override_keys()" in src
    assert "validate_path_value(" in src
    assert 'raw.startswith("/") or raw.startswith("~")' not in src, \
        "slash-only absolute-path check is back"
    assert 'label="Global (all projects)"' not in src
    print("test_dialog_uses_the_new_behaviour: PASS")


if __name__ == "__main__":
    test_opens_on_global_when_nothing_is_overridden()
    test_opens_on_global_after_a_global_save()
    test_opens_on_project_when_the_project_overrides()
    test_opens_on_global_without_a_project()
    test_project_save_stores_only_changed_values()
    test_project_save_no_longer_shadows_later_global_changes()
    test_project_save_with_nothing_changed_removes_the_file()
    test_project_save_keeps_non_path_keys()
    test_global_save_drops_values_equal_to_default()
    test_existing_full_override_is_reported()
    test_validation()
    test_dialog_uses_the_new_behaviour()
    print("\nAll issue-20 tests passed.")
