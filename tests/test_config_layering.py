"""
Tests for layered config resolution: default < global < project.

Run with: python3 tests/test_config_layering.py
"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "plugins"))

from lcsc_manager.utils.config import Config, PROJECT_CONFIG_FILENAME


def _make_config(global_data, project_dir, project_data):
    """Create a Config with custom global + project files."""
    global_file = project_dir / "global_config.json"
    if global_data is not None:
        global_file.write_text(json.dumps(global_data))
    cfg = Config(config_path=global_file)
    if project_data is not None:
        (project_dir / PROJECT_CONFIG_FILENAME).write_text(json.dumps(project_data))
    cfg.load_project_overrides(project_dir)
    return cfg


def test_default_only():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        cfg = _make_config({}, tmp, None)
        assert cfg.get("library_path") == "libs/lcsc"
        assert cfg.get_value_source("library_path") == "default"
    print("test_default_only: PASS")


def test_global_overrides_default():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        cfg = _make_config({"library_path": "libs/from_global"}, tmp, None)
        assert cfg.get("library_path") == "libs/from_global"
        assert cfg.get_value_source("library_path") == "global"
        # Other keys still default
        assert cfg.get("symbol_lib_name") == "lcsc_imported.kicad_sym"
        assert cfg.get_value_source("symbol_lib_name") == "default"
    print("test_global_overrides_default: PASS")


def test_project_overrides_global():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        cfg = _make_config(
            {"library_path": "libs/from_global", "symbol_lib_name": "g.kicad_sym"},
            tmp,
            {"library_path": "libs/from_project"},
        )
        assert cfg.get("library_path") == "libs/from_project"
        assert cfg.get_value_source("library_path") == "project"
        # Project file omits symbol_lib_name → falls back to global
        assert cfg.get("symbol_lib_name") == "g.kicad_sym"
        assert cfg.get_value_source("symbol_lib_name") == "global"
    print("test_project_overrides_global: PASS")


def test_save_scope_global_creates_file():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        cfg = _make_config({}, tmp, None)
        cfg.save_scope("global", {"library_path": "custom/lib"})
        # Re-read from disk
        data = json.loads(cfg.config_path.read_text())
        assert data["library_path"] == "custom/lib"
    print("test_save_scope_global_creates_file: PASS")


def test_save_scope_project_creates_file():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        cfg = _make_config({}, tmp, None)
        cfg.save_scope("project", {"library_path": "custom/lib"}, project_path=tmp)
        proj_file = tmp / PROJECT_CONFIG_FILENAME
        assert proj_file.exists()
        data = json.loads(proj_file.read_text())
        assert data["library_path"] == "custom/lib"
        # And the config in-memory reflects it
        assert cfg.get("library_path") == "custom/lib"
        assert cfg.get_value_source("library_path") == "project"
    print("test_save_scope_project_creates_file: PASS")


def test_clear_scope_project_deletes_file():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        cfg = _make_config({}, tmp, {"library_path": "x"})
        proj_file = tmp / PROJECT_CONFIG_FILENAME
        assert proj_file.exists()
        cfg.clear_scope("project", project_path=tmp)
        assert not proj_file.exists()
        # Falls back to default
        assert cfg.get("library_path") == "libs/lcsc"
    print("test_clear_scope_project_deletes_file: PASS")


def test_resolve_paths_with_project():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        values = {
            "library_path": "libs/custom",
            "symbol_lib_name": "my.kicad_sym",
            "footprint_lib_name": "fp.pretty",
            "model_3d_path": "models",
        }
        resolved = Config.resolve_paths(values, tmp)
        assert resolved["library_root"] == (tmp / "libs/custom").resolve()
        assert resolved["symbol_lib"].name == "my.kicad_sym"
        assert resolved["symbol_lib"].parent.name == "symbols"
        assert resolved["footprint_lib"].name == "fp.pretty"
        assert resolved["model_3d_dir"].name == "models"
    print("test_resolve_paths_with_project: PASS")


def test_resolve_paths_no_project_returns_none():
    resolved = Config.resolve_paths({"library_path": "x"}, None)
    assert resolved["library_root"] is None
    assert resolved["symbol_lib"] is None
    print("test_resolve_paths_no_project_returns_none: PASS")


def test_resolve_for_scope_view_global_ignores_project():
    """Global view must not bleed Project values into the field."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        cfg = _make_config(
            {"library_path": "from_global"},
            tmp,
            {"library_path": "from_project"},
        )
        # Project view: project wins
        v, src = cfg.resolve_for_scope_view("library_path", "project")
        assert v == "from_project" and src == "project"
        # Global view: project is invisible — global wins
        v, src = cfg.resolve_for_scope_view("library_path", "global")
        assert v == "from_global" and src == "global"
    print("test_resolve_for_scope_view_global_ignores_project: PASS")


def test_resolve_for_scope_view_falls_through_to_default():
    """Project view falls back through Global to Default; Global view goes
    straight to Default when not stored."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        cfg = _make_config({}, tmp, None)
        # Neither scope stores library_path → both views see default
        v_g, s_g = cfg.resolve_for_scope_view("library_path", "global")
        v_p, s_p = cfg.resolve_for_scope_view("library_path", "project")
        assert v_g == "libs/lcsc" and s_g == "default"
        assert v_p == "libs/lcsc" and s_p == "default"
    print("test_resolve_for_scope_view_falls_through_to_default: PASS")


def test_resolve_for_scope_view_project_inherits_global():
    """Project view shows the Global value when Project doesn't override."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        cfg = _make_config({"library_path": "from_global"}, tmp, None)
        v, src = cfg.resolve_for_scope_view("library_path", "project")
        assert v == "from_global" and src == "global"
    print("test_resolve_for_scope_view_project_inherits_global: PASS")


def test_kiprjmod_uris_reflect_config():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        cfg = _make_config(
            {
                "library_path": "assets/lcsc",
                "symbol_lib_name": "imported.kicad_sym",
                "footprint_lib_name": "fp.pretty",
                "model_3d_path": "3d",
            },
            tmp,
            None,
        )
        uris = cfg.get_kiprjmod_uris()
        assert uris["symbol_lib"] == "${KIPRJMOD}/assets/lcsc/symbols/imported.kicad_sym"
        assert uris["footprint_lib"] == "${KIPRJMOD}/assets/lcsc/fp.pretty"
        assert uris["model_3d_dir"] == "${KIPRJMOD}/assets/lcsc/3d"
    print("test_kiprjmod_uris_reflect_config: PASS")


if __name__ == "__main__":
    test_default_only()
    test_global_overrides_default()
    test_project_overrides_global()
    test_save_scope_global_creates_file()
    test_save_scope_project_creates_file()
    test_clear_scope_project_deletes_file()
    test_resolve_paths_with_project()
    test_resolve_paths_no_project_returns_none()
    test_resolve_for_scope_view_global_ignores_project()
    test_resolve_for_scope_view_falls_through_to_default()
    test_resolve_for_scope_view_project_inherits_global()
    test_kiprjmod_uris_reflect_config()
    print("\nAll config layering tests passed.")
