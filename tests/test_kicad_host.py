"""Tests for utils/kicad_host.py: the one place that knows which KiCad the
plugin runs under (#19).

    SwigHost  inside pcbnew           NullHost  no KiCad session
    IpcHost   an IPC plugin process

Run with: python3 tests/test_kicad_host.py
"""
import json
import os
import re
import subprocess
import sys
import tempfile
import types
from pathlib import Path

REPO = Path(__file__).parent.parent
PLUGINS = REPO / "plugins"
sys.path.insert(0, str(PLUGINS))

import lcsc_manager.utils.kicad_host as kh
from lcsc_manager.utils.kicad_host import (
    IpcHost, NullHost, SwigHost, default_user_settings_dir, detect_host,
    get_host, set_host_for_tests, substitute_vars,
)

KICAD_PYTHON = Path("/Applications/KiCad/KiCad.app/Contents/Frameworks/"
                    "Python.framework/Versions/Current/bin/python3")


# ─── settings folder, computed as KiCad does ──────────────────────────

def test_user_settings_dir_per_platform():
    home = Path("/home/me")
    assert default_user_settings_dir(10, 0, env={}, platform="darwin", home=home) == \
        home / "Library/Preferences/kicad/10.0"
    assert default_user_settings_dir(10, 0, env={}, platform="linux", home=home) == \
        home / ".config/kicad/10.0"
    assert default_user_settings_dir(10, 0, env={"XDG_CONFIG_HOME": "/xdg"},
                                     platform="linux", home=home) == Path("/xdg/kicad/10.0")
    win = default_user_settings_dir(11, 0, env={"APPDATA": "C:/Users/me/AppData/Roaming"},
                                    platform="win32", home=home)
    assert str(win).replace("\\", "/") == "C:/Users/me/AppData/Roaming/kicad/11.0", win
    # Nightlies are "10.99".
    assert default_user_settings_dir(10, 99, env={}, platform="darwin", home=home).name == "10.99"
    print("test_user_settings_dir_per_platform: PASS")


def test_kicad_config_home_overrides_everything():
    """KICAD_CONFIG_HOME replaces the platform folder *and* the "kicad" part."""
    for platform in ("darwin", "linux", "win32"):
        got = default_user_settings_dir(10, 0, env={"KICAD_CONFIG_HOME": "/cfg"},
                                        platform=platform, home=Path("/h"))
        assert got == Path("/cfg/10.0"), (platform, got)
    print("test_kicad_config_home_overrides_everything: PASS")


def test_substitute_vars_keeps_unknown_names():
    assert substitute_vars("${A}/x/${B}", {"A": "/a"}) == "/a/x/${B}"
    print("test_substitute_vars_keeps_unknown_names: PASS")


# ─── NullHost ─────────────────────────────────────────────────────────

def test_null_host():
    host = NullHost()
    assert not host.session_running
    assert host.project_file() is None and host.user_settings_dir() is None
    assert host.footprint_library_loaded("x") is None
    assert not host.can_register_footprint_library_in_memory()
    os.environ["LCSC_HOST_T"] = "/env"
    try:
        assert host.expand_path_vars(" ${LCSC_HOST_T}/lcsc ") == "/env/lcsc"
    finally:
        del os.environ["LCSC_HOST_T"]
    assert host.expand_path_vars("~/k") == str(Path.home() / "k")
    print("test_null_host: PASS")


# ─── SwigHost over a stand-in pcbnew ──────────────────────────────────

class _Table:
    def __init__(self, names):
        self.names, self.inserted, self.saved = set(names), [], None
    def HasLibrary(self, name):
        return name in self.names
    def InsertRow(self, row):
        self.inserted.append(row)
    def Save(self, path):
        self.saved = path


class _Row:
    def __init__(self, *args):
        self.args, self.descr = args, None
    def SetDescr(self, d):
        self.descr = d


def _fake_pcbnew(board_file="/p/board.kicad_pcb", libraries=("A",), table=None,
                 kicad9=False, with_board=True):
    m = types.SimpleNamespace()
    table = table or _Table([])
    board = types.SimpleNamespace(
        GetFileName=lambda: board_file,
        GetProject=lambda: types.SimpleNamespace(PcbFootprintLibs=lambda: table))
    m.GetBoard = lambda: board if with_board else None
    m.GetFootprintLibraries = lambda: list(libraries)
    m.SETTINGS_MANAGER = types.SimpleNamespace(GetUserSettingsPath=lambda: "/settings/10.0")
    m.ExpandEnvVarSubstitutions = lambda text, project: text.replace("${KICAD_VAR}", "/kv")
    if kicad9:
        m.FP_LIB_TABLE_ROW = _Row
    return m, table


def test_swig_host():
    pcb, _ = _fake_pcbnew(libraries=["lcsc_footprints"])
    host = SwigHost(pcb)
    assert host.session_running
    assert host.project_file() == Path("/p/board.kicad_pcb")
    assert host.user_settings_dir() == Path("/settings/10.0")
    assert host.expand_path_vars("${KICAD_VAR}/lcsc") == "/kv/lcsc"
    assert host.footprint_library_loaded("lcsc_footprints") is True
    assert host.footprint_library_loaded("other") is False
    assert not host.can_register_footprint_library_in_memory()     # KiCad 10
    print("test_swig_host: PASS")


def test_swig_host_cannot_tell_without_the_listing():
    pcb, _ = _fake_pcbnew()
    del pcb.GetFootprintLibraries
    assert SwigHost(pcb).footprint_library_loaded("x") is None
    pcb, _ = _fake_pcbnew()
    pcb.GetFootprintLibraries = lambda: (_ for _ in ()).throw(RuntimeError("boom"))
    assert SwigHost(pcb).footprint_library_loaded("x") is None
    print("test_swig_host_cannot_tell_without_the_listing: PASS")


def test_swig_host_registers_in_memory_on_kicad9():
    pcb, table = _fake_pcbnew(kicad9=True)
    host = SwigHost(pcb)
    assert host.can_register_footprint_library_in_memory()
    assert host.register_footprint_library_in_memory("lcsc_footprints", "${KIPRJMOD}/x",
                                                     Path("/p/fp-lib-table")) is True
    assert table.inserted[0].args == ("lcsc_footprints", "${KIPRJMOD}/x", "KiCad", "")
    assert table.saved == "/p/fp-lib-table"
    pcb, table = _fake_pcbnew(kicad9=True, table=_Table(["lcsc_footprints"]))
    assert SwigHost(pcb).register_footprint_library_in_memory(
        "lcsc_footprints", "u", Path("/t")) is False
    assert table.inserted == []
    pcb, _ = _fake_pcbnew(kicad9=True, with_board=False)
    try:
        SwigHost(pcb).register_footprint_library_in_memory("n", "u", Path("/t"))
    except RuntimeError:
        print("test_swig_host_registers_in_memory_on_kicad9: PASS")
        return
    raise AssertionError("no board must raise")


# ─── IpcHost over a stand-in kipy ─────────────────────────────────────

def _install_fake_kipy():
    """Just enough of kipy for IpcHost: the DocumentType enum."""
    DocumentType = types.SimpleNamespace(DOCTYPE_SCHEMATIC=1, DOCTYPE_PCB=3)
    for name in ("kipy", "kipy.proto", "kipy.proto.common", "kipy.proto.common.types"):
        sys.modules.setdefault(name, types.ModuleType(name))
    sys.modules["kipy.proto.common.types"].DocumentType = DocumentType
    return DocumentType


class _FakeKiCad:
    def __init__(self, docs=None, version=(10, 0)):
        self.docs, self.version = docs or {}, version
    def get_open_documents(self, kind):
        return self.docs.get(kind, [])
    def get_version(self):
        return types.SimpleNamespace(major=self.version[0], minor=self.version[1])


def _doc(path, name, board=""):
    return types.SimpleNamespace(project=types.SimpleNamespace(path=path, name=name),
                                 board_filename=board)


def test_ipc_host_project_file():
    dt = _install_fake_kipy()
    pcb_doc = _doc("/proj", "board", "board.kicad_pcb")
    sch_doc = _doc("/proj", "board")
    assert IpcHost(_FakeKiCad({dt.DOCTYPE_PCB: [pcb_doc]})).project_file() == \
        Path("/proj/board.kicad_pcb")
    # Launched from the Schematic Editor: no board, use the project file.
    assert IpcHost(_FakeKiCad({dt.DOCTYPE_SCHEMATIC: [sch_doc]})).project_file() == \
        Path("/proj/board.kicad_pro")
    assert IpcHost(_FakeKiCad()).project_file() is None
    print("test_ipc_host_project_file: PASS")


def test_ipc_host_settings_and_path_variables():
    _install_fake_kipy()
    cfg_home = Path(tempfile.mkdtemp())
    (cfg_home / "11.0").mkdir()
    (cfg_home / "11.0" / "kicad_common.json").write_text(json.dumps(
        {"environment": {"vars": {"MY_LIBS": "/shared/libs"}}}))
    env = {"KICAD_CONFIG_HOME": str(cfg_home), "FROM_ENV": "/e"}
    host = IpcHost(_FakeKiCad(version=(11, 0)), env=env)
    assert host.session_running
    assert host.user_settings_dir() == cfg_home / "11.0"
    assert host.expand_path_vars("${MY_LIBS}/lcsc") == "/shared/libs/lcsc"   # Configure Paths
    assert host.expand_path_vars("${FROM_ENV}/x") == "/e/x"                  # environment
    assert host.expand_path_vars("${NOPE}/x") == "${NOPE}/x"                 # left for validation
    assert host.footprint_library_loaded("lcsc_footprints") is None          # no IPC command
    assert not host.can_register_footprint_library_in_memory()
    # kicad_common.json with no user variables ("vars": null) is fine.
    (cfg_home / "11.0" / "kicad_common.json").write_text('{"environment": {"vars": null}}')
    assert IpcHost(_FakeKiCad(version=(11, 0)), env=env).expand_path_vars("${NOPE}") == "${NOPE}"
    print("test_ipc_host_settings_and_path_variables: PASS")


# ─── which host ───────────────────────────────────────────────────────

def test_detect_host():
    saved_token = os.environ.pop("KICAD_API_TOKEN", None)
    saved_pcbnew = sys.modules.get("pcbnew")
    try:
        os.environ["KICAD_API_TOKEN"] = "t"
        assert isinstance(detect_host(), IpcHost)
        del os.environ["KICAD_API_TOKEN"]

        sys.modules["pcbnew"] = _fake_pcbnew()[0]
        assert isinstance(detect_host(), SwigHost)                # inside pcbnew
        sys.modules["pcbnew"] = _fake_pcbnew(with_board=False)[0]
        assert isinstance(detect_host(), NullHost), \
            "importable pcbnew without a board is not a KiCad session"
        sys.modules.pop("pcbnew")
        sys.modules["pcbnew"] = None                              # import fails
        assert isinstance(detect_host(), NullHost)
    finally:
        sys.modules.pop("pcbnew", None)
        if saved_pcbnew is not None:
            sys.modules["pcbnew"] = saved_pcbnew
        if saved_token is not None:
            os.environ["KICAD_API_TOKEN"] = saved_token
    print("test_detect_host: PASS")


def test_get_host_remembers_sessions_only():
    set_host_for_tests(None)
    saved = kh.detect_host
    try:
        kh.detect_host = lambda: NullHost()
        first = get_host()
        kh.detect_host = lambda: SwigHost(_fake_pcbnew()[0])
        assert isinstance(get_host(), SwigHost), "a no-session answer must not stick"
        kh.detect_host = lambda: NullHost()
        assert isinstance(get_host(), SwigHost), "a session host is kept"
        assert isinstance(first, NullHost)
    finally:
        kh.detect_host = saved
        set_host_for_tests(None)
    print("test_get_host_remembers_sessions_only: PASS")


def test_config_expands_through_the_host():
    from lcsc_manager.utils.config import expand_path_vars
    class Marker(NullHost):
        def expand_path_vars(self, text):
            return "via-host:" + text
    set_host_for_tests(Marker())
    try:
        assert expand_path_vars("${X}") == "via-host:${X}"
    finally:
        set_host_for_tests(None)
    print("test_config_expands_through_the_host: PASS")


def test_pcbnew_is_only_touched_by_the_host_and_the_swig_entry():
    code_uses = re.compile(r"^(?!\s*#).*\bpcbnew\.|^\s*import pcbnew", re.M)
    offenders = []
    for path in (PLUGINS / "lcsc_manager").rglob("*.py"):
        rel = path.relative_to(PLUGINS / "lcsc_manager").as_posix()
        if rel.startswith(("lib/", "vendor/")) or rel in ("plugin.py", "utils/kicad_host.py"):
            continue
        if code_uses.search(path.read_text(encoding="utf-8")):
            offenders.append(rel)
    assert offenders == [], f"pcbnew used outside the host: {offenders}"
    print("test_pcbnew_is_only_touched_by_the_host_and_the_swig_entry: PASS")


def test_against_real_kicad():
    """With KiCad installed: its standalone Python is not a session (so tests
    and scripts can't touch the real global tables by accident), and the
    computed settings folder is the one KiCad reports."""
    if not KICAD_PYTHON.exists():
        print("test_against_real_kicad: SKIP (no KiCad python)")
        return
    code = f"""
import sys; sys.path.insert(0, {str(PLUGINS)!r})
import pcbnew
from lcsc_manager.utils.kicad_host import detect_host, default_user_settings_dir
v = pcbnew.GetMajorMinorVersion().split(".")
print("HOST", detect_host().name)
print("MATCH", str(default_user_settings_dir(int(v[0]), int(v[1]))) ==
      pcbnew.SETTINGS_MANAGER.GetUserSettingsPath())
"""
    env = {k: v for k, v in os.environ.items()
           if k not in ("KICAD_API_TOKEN", "PYTHONPATH", "PYTHONHOME")}
    run = subprocess.run([str(KICAD_PYTHON), "-c", code], env=env,
                         capture_output=True, text=True, timeout=120)
    assert "HOST none" in run.stdout, run.stdout + run.stderr[-500:]
    assert "MATCH True" in run.stdout, run.stdout + run.stderr[-500:]
    print("test_against_real_kicad: PASS")


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
    print("\nAll kicad-host tests passed.")
