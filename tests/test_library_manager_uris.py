"""
Tests that LibraryManager writes lib-table URIs derived from config,
not from the legacy hardcoded literals.

Run with: python3 tests/test_library_manager_uris.py
"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "plugins"))

# Force fresh Config so prior test state doesn't bleed in
from lcsc_manager.utils import config as _cfg_mod
from lcsc_manager.utils.config import Config, PROJECT_CONFIG_FILENAME


def _setup_project(tmp: Path, overrides: dict) -> Path:
    """Create a fake project dir with a .kicad_pro file and project overrides."""
    proj_dir = tmp / "myproj"
    proj_dir.mkdir()
    proj_file = proj_dir / "myproj.kicad_pro"
    proj_file.write_text("{}")  # KiCad project file (content doesn't matter here)
    (proj_dir / PROJECT_CONFIG_FILENAME).write_text(json.dumps(overrides))
    return proj_file


def _make_global_config(tmp: Path) -> Config:
    """Create a Config pointed at a tmp file so we don't touch ~/.kicad/."""
    global_file = tmp / "global.json"
    global_file.write_text("{}")
    cfg = Config(config_path=global_file)
    _cfg_mod._config_instance = cfg  # replace singleton
    return cfg


def test_symbol_lib_table_uses_config_uri():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        _make_global_config(tmp)
        proj_file = _setup_project(tmp, {
            "library_path": "assets/lcsc",
            "symbol_lib_name": "components.kicad_sym",
            "footprint_lib_name": "fp.pretty",
            "model_3d_path": "3d",
        })

        # Import after singleton replacement
        from lcsc_manager.library.library_manager import LibraryManager
        lm = LibraryManager(proj_file)

        notif = lm._update_symbol_lib_table()
        assert notif is None
        table = (proj_file.parent / "sym-lib-table").read_text()
        assert "${KIPRJMOD}/assets/lcsc/symbols/components.kicad_sym" in table
        # Legacy default must not leak in
        assert "libs/lcsc/symbols/lcsc_imported.kicad_sym" not in table
    print("test_symbol_lib_table_uses_config_uri: PASS")


def test_footprint_lib_table_uses_config_uri():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        _make_global_config(tmp)
        proj_file = _setup_project(tmp, {
            "library_path": "assets/lcsc",
            "footprint_lib_name": "fp.pretty",
        })

        from lcsc_manager.library.library_manager import LibraryManager
        lm = LibraryManager(proj_file)

        # Force the file-based fallback path
        notif = lm._update_footprint_lib_table_file("lcsc_footprints",
                                                   lm.config.get_kiprjmod_uris()["footprint_lib"])
        assert notif is None
        table = (proj_file.parent / "fp-lib-table").read_text()
        assert "${KIPRJMOD}/assets/lcsc/fp.pretty" in table
        assert "libs/lcsc/footprints.pretty" not in table
    print("test_footprint_lib_table_uses_config_uri: PASS")


def test_footprint_converter_3d_uri_reflects_config():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        _make_global_config(tmp)
        proj_file = _setup_project(tmp, {
            "library_path": "assets/lcsc",
            "model_3d_path": "3d",
        })

        from lcsc_manager.library.library_manager import LibraryManager
        lm = LibraryManager(proj_file)
        assert lm.footprint_converter.model_uri_base == "${KIPRJMOD}/assets/lcsc/3d"
    print("test_footprint_converter_3d_uri_reflects_config: PASS")


if __name__ == "__main__":
    test_symbol_lib_table_uses_config_uri()
    test_footprint_lib_table_uses_config_uri()
    test_footprint_converter_3d_uri_reflects_config()
    print("\nAll library_manager URI tests passed.")
