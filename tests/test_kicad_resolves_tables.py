"""Headless check, against KiCad itself, that the library-table rows the
plugin writes actually resolve.

No GUI and no network: KiCad's bundled Python builds a project, a test
footprint and — through the real LibraryManager — the table rows; a board
places the footprint by library nickname; then `kicad-cli pcb drc` has to
find it through the tables (its lib_footprint_issues check). A control run
with the row broken must be flagged, so the check can't pass vacuously.

KICAD_CONFIG_HOME points at a sandbox, so KiCad's global tables here are
throwaway ones — the user's real configuration is never read or written.

Skipped where KiCad isn't installed.

Run with: python3 tests/test_kicad_resolves_tables.py
"""
import json
import os
import subprocess
import tempfile
import textwrap
from pathlib import Path

REPO = Path(__file__).parent.parent
PLUGINS = REPO / "plugins"
APP = Path("/Applications/KiCad/KiCad.app/Contents")
KICAD_PYTHON = APP / "Frameworks/Python.framework/Versions/Current/bin/python3"
KICAD_CLI = APP / "MacOS/kicad-cli"

BUILD = textwrap.dedent(f"""
    import sys, logging
    from pathlib import Path
    sys.path.insert(0, {str(PLUGINS)!r})
    logging.disable(logging.CRITICAL)
    import pcbnew
    import lcsc_manager.utils.config as cfgmod
    from lcsc_manager.utils.config import Config
    from lcsc_manager.library.library_manager import LibraryManager

    root, mode, kicad_cfg = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3])
    proj = root / "board"; proj.mkdir(parents=True)
    pcb = proj / "board.kicad_pcb"
    pcbnew.NewBoard(str(pcb))
    cfg = Config(config_path=root / "lcsc_global.json")
    if mode == "shared":
        cfg.save_global_settings({{"library_location": "shared",
                                   "shared_library_path": str(root / "Shared")}})
    cfgmod._config_instance = cfg

    lm = LibraryManager(pcb, kicad_config_dir=kicad_cfg)
    # A minimal footprint, written directly: pcbnew.FootprintSave can't guess
    # the library format of an empty .pretty folder.
    lm.footprint_lib_path.mkdir(parents=True)
    (lm.footprint_lib_path / "TEST_FP.kicad_mod").write_text(
        '(footprint "TEST_FP" (version 20240108) (generator "lcsc_test") (layer "F.Cu")\\n'
        '  (pad "1" smd rect (at 0 0) (size 1 1) (layers "F.Cu" "F.Paste" "F.Mask"))\\n)\\n')

    # Only the library-table step: nothing to convert, no network.
    lm.import_component({{}}, {{"lcsc_id": "T"}}, False, False, False)

    nick = cfg.get_library_nicknames()["footprint"]
    board = pcbnew.LoadBoard(str(pcb))
    placed = pcbnew.FootprintLoad(str(lm.footprint_lib_path), "TEST_FP")
    placed.SetFPID(pcbnew.LIB_ID(nick, "TEST_FP"))
    placed.SetReference("U1")
    board.Add(placed)
    board.Save(str(pcb))
    table = (kicad_cfg if mode == "shared" else proj) / "fp-lib-table"
    print("NICK", nick)
    print("TABLE", table)
""")


def _sandbox():
    root = Path(tempfile.mkdtemp())
    cfg_home = root / "cfghome"
    (cfg_home / "10.0").mkdir(parents=True)
    for kind in ("fp", "sym"):
        (cfg_home / "10.0" / f"{kind}-lib-table").write_text(
            f"({kind}_lib_table\n\t(version 7)\n)\n")
    env = {k: v for k, v in os.environ.items()
           if k not in ("KICAD_API_TOKEN", "PYTHONPATH", "PYTHONHOME")}
    env["KICAD_CONFIG_HOME"] = str(cfg_home)
    return root, cfg_home / "10.0", env


def _library_issues(board, env, out):
    subprocess.run([str(KICAD_CLI), "pcb", "drc", "--format", "json",
                    "--severity-all", "-o", str(out), str(board)],
                   env=env, capture_output=True, timeout=180)
    report = json.loads(out.read_text())
    return [v["description"] for v in report.get("violations", [])
            if v["type"] == "lib_footprint_issues"]


def _check(mode):
    root, kicad_cfg, env = _sandbox()
    run = subprocess.run([str(KICAD_PYTHON), "-c", BUILD, str(root), mode, str(kicad_cfg)],
                         env=env, capture_output=True, text=True, timeout=300)
    assert "NICK" in run.stdout, run.stdout[-500:] + run.stderr[-1500:]
    nick = run.stdout.split("NICK ", 1)[1].split()[0]
    table = Path(run.stdout.split("TABLE ", 1)[1].strip())
    board = root / "board" / "board.kicad_pcb"
    out = root / "drc.json"

    issues = _library_issues(board, env, out)
    assert issues == [], f"KiCad couldn't resolve {nick}: {issues}"

    good = table.read_text()
    table.write_text(good.replace(f'(name "{nick}")', '(name "broken")'))
    issues = _library_issues(board, env, out)
    assert any(nick in i for i in issues), \
        f"control: a broken row must be flagged, got {issues}"
    return nick, table


def test_project_table_rows_resolve():
    if not (KICAD_PYTHON.exists() and KICAD_CLI.exists()):
        print("test_project_table_rows_resolve: SKIP (no KiCad)")
        return
    nick, table = _check("project")
    assert nick == "lcsc_footprints" and table.parent.name == "board"
    print("test_project_table_rows_resolve: PASS")


def test_shared_global_table_rows_resolve():
    if not (KICAD_PYTHON.exists() and KICAD_CLI.exists()):
        print("test_shared_global_table_rows_resolve: SKIP (no KiCad)")
        return
    nick, table = _check("shared")
    assert nick == "lcsc_shared_footprints" and table.parent.name == "10.0"
    print("test_shared_global_table_rows_resolve: PASS")


if __name__ == "__main__":
    test_project_table_rows_resolve()
    test_shared_global_table_rows_resolve()
    print("\nAll KiCad table-resolution tests passed.")
