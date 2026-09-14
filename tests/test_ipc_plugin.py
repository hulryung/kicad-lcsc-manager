"""Tests for the IPC API plugin (#19): ipc/plugin.json, the plugin folder
scripts/assemble-ipc-plugin.py builds, and the entry point KiCad runs
(plugins/lcsc_manager/ipc_main.py).

wx is replaced by a stub here, so these run with any Python 3; the real
wx.App is covered by running the plugin in KiCad (see TESTING.md).

Run with: python3 tests/test_ipc_plugin.py
"""
import json
import os
import re
import struct
import subprocess
import sys
import tempfile
import textwrap
import types
from pathlib import Path

REPO = Path(__file__).parent.parent
PLUGINS = REPO / "plugins"
PACKAGE_DIR = PLUGINS / "lcsc_manager"
IPC_DIR = REPO / "ipc"
ASSEMBLE = REPO / "scripts" / "assemble-ipc-plugin.py"
sys.path.insert(0, str(PLUGINS))

from lcsc_manager import ipc_main
from lcsc_manager.utils import kicad_host

# API_PLUGIN::IsValidIdentifier in KiCad, and the patterns in KiCad's
# plugin.json schema (https://go.kicad.org/api/schemas/v1).
KICAD_IDENTIFIER = re.compile(
    r"^[a-zA-Z]{2,}(\.([a-zA-Z0-9][a-zA-Z0-9-]*[a-zA-Z0-9]|[a-zA-Z0-9])){2,}$")
SCHEMA_PLUGIN_ID = re.compile(r"^[a-zA-Z][-_a-zA-Z0-9.]{0,98}[a-zA-Z0-9]$")
SCHEMA_ACTION_ID = re.compile(r"^[a-zA-Z][-_a-zA-Z0-9.]{0,48}[a-zA-Z0-9]$")
SCOPES = {"pcb", "schematic", "footprint", "symbol", "project_manager", "footprint_wizard"}

# Enough of wx for the entry point and the launcher. With $STUB_WX_LOG set,
# a subprocess reports MessageBox calls there, and sys.path as it was when
# the wx.App was created in $STUB_WX_LOG.path.
STUB_WX = textwrap.dedent("""
    import os, sys
    ID_OK, ID_CANCEL = 5100, 5101
    OK, ICON_WARNING, ICON_ERROR, ICON_INFORMATION = 4, 0x100, 0x200, 0x800
    APP_ASSERT_LOG = 2
    messages = []

    def MessageBox(message, caption="", style=0):
        messages.append((caption, message))
        if os.environ.get("STUB_WX_LOG"):
            with open(os.environ["STUB_WX_LOG"], "a", encoding="utf-8") as f:
                f.write(caption + ": " + message + "\\n")
        return OK

    class App:
        def __init__(self, redirect=False):
            global app
            app = self
            if os.environ.get("STUB_WX_LOG"):
                with open(os.environ["STUB_WX_LOG"] + ".path", "w", encoding="utf-8") as f:
                    f.write("\\n".join(sys.path))
                # What GTK tends to print when a wx.App starts on Linux.
                os.write(2, b"Gtk-Message: Failed to load module canberra-gtk-module\\n")
        def SetAssertMode(self, mode):
            self.assert_mode = mode

    class TextEntryDialog:
        def __init__(self, *args):
            pass
        def ShowModal(self):
            return ID_CANCEL
        def Destroy(self):
            pass
""")


def _plugin_json(folder=IPC_DIR):
    return json.loads((folder / "plugin.json").read_text(encoding="utf-8"))


def _assemble(name="lcsc-manager"):
    dest = Path(tempfile.mkdtemp()) / name
    run = subprocess.run([sys.executable, str(ASSEMBLE), str(dest)],
                         capture_output=True, text=True)
    assert run.returncode == 0, run.stderr
    return dest


def _png_size(path):
    head = path.read_bytes()[:24]
    assert head[:8] == b"\x89PNG\r\n\x1a\n", f"{path} is not a PNG"
    return struct.unpack(">II", head[16:24])


def _stub_dir():
    folder = Path(tempfile.mkdtemp())
    (folder / "wx.py").write_text(STUB_WX, encoding="utf-8")
    return folder


def _clean_env(**extra):
    env = {k: v for k, v in os.environ.items()
           if k not in ("KICAD_API_TOKEN", "KICAD_API_SOCKET", "PYTHONPATH", "PYTHONHOME")}
    env.update(extra)
    return env


# ─── plugin.json ──────────────────────────────────────────────────────

def test_plugin_json_is_valid_for_kicad():
    config = _plugin_json()
    for key in ("identifier", "name", "description", "runtime", "actions"):
        assert key in config, f"plugin.json needs {key}"
    ident = config["identifier"]
    assert KICAD_IDENTIFIER.match(ident), f"KiCad rejects the identifier {ident!r}"
    assert SCHEMA_PLUGIN_ID.match(ident)
    assert config["runtime"]["type"] == "python"
    assert len(config["name"]) <= 200 and len(config["description"]) <= 500
    # One package in the Plugin and Content Manager, whichever build.
    metadata = json.loads((REPO / "metadata.json").read_text(encoding="utf-8"))
    assert ident == metadata["identifier"]

    actions = config["actions"]
    assert len({a["identifier"] for a in actions}) == len(actions)
    for action in actions:
        for key in ("identifier", "name", "description", "entrypoint"):
            assert key in action, f"an action needs {key}"
        assert SCHEMA_ACTION_ID.match(action["identifier"])
        assert len(action["name"]) <= 200 and len(action["description"]) <= 500
        # KiCad skips actions whose entrypoint is an absolute path.
        assert not Path(action["entrypoint"]).is_absolute()
        assert set(action["scopes"]) <= SCOPES
        for icon in action["icons-light"] + action["icons-dark"]:
            assert icon.endswith(".png"), icon
    [action] = actions
    assert set(action["scopes"]) == {"pcb", "schematic"}
    assert action["show-button"] is True
    print("test_plugin_json_is_valid_for_kicad: PASS")


def test_ipc_files_stay_out_of_the_swig_package():
    """The SWIG build ships plugins/lcsc_manager as-is. plugin.json there
    would turn its SWIG plugin off (see __init__.py)."""
    for name in ("plugin.json", "requirements.txt"):
        assert not (PACKAGE_DIR / name).exists(), f"{name} belongs in ipc/"
    print("test_ipc_files_stay_out_of_the_swig_package: PASS")


def test_requirements_are_bounded():
    """KiCad installs the newest match each time it loads the plugin, so an
    open-ended requirement could break every install at once."""
    lines = [line.strip() for line in
             (IPC_DIR / "requirements.txt").read_text(encoding="utf-8").splitlines()
             if line.strip() and not line.strip().startswith("#")]
    assert any(line.startswith("kicad-python") for line in lines), lines
    for line in lines:
        assert ">=" in line and re.search(r"<(?!=)", line), f"unbounded: {line}"
    print("test_requirements_are_bounded: PASS")


# ─── the assembled folder ─────────────────────────────────────────────

def test_assembled_folder_is_a_complete_plugin():
    dest = _assemble()
    [action] = _plugin_json(dest)["actions"]
    assert (dest / action["entrypoint"]).is_file()
    assert (dest / "__init__.py").is_file() and (dest / "requirements.txt").is_file()
    # KiCad puts the icons on the toolbar unscaled: 24 px, and 48 px for HiDPI.
    for key in ("icons-light", "icons-dark"):
        assert sorted(_png_size(dest / p) for p in action[key]) == [(24, 24), (48, 48)]
    assert not list(dest.rglob("__pycache__")) and not list(dest.rglob("*.pyc"))
    again = subprocess.run([sys.executable, str(ASSEMBLE), str(dest)],
                           capture_output=True, text=True)
    assert again.returncode != 0 and "already exists" in again.stderr, \
        "must not write over an existing folder"
    print("test_assembled_folder_is_a_complete_plugin: PASS")


def test_ipc_build_does_not_register_the_swig_plugin():
    """KiCad 10 loads a package installed by the Plugin and Content Manager
    both ways: as a SWIG plugin and, because of plugin.json, over IPC."""
    stubs = Path(tempfile.mkdtemp())
    (stubs / "wx.py").write_text("", encoding="utf-8")
    (stubs / "pcbnew.py").write_text(textwrap.dedent("""
        class ActionPlugin:
            def register(self):
                print("SWIG plugin registered")
    """), encoding="utf-8")
    dest = _assemble("com_github_hulryung_kicad-lcsc-manager")

    def import_package(folder):
        # How KiCad's SWIG loader imports a plugin folder.
        code = (f"import sys; sys.path.insert(0, {str(folder.parent)!r}); "
                f"__import__({folder.name!r})")
        return subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                              env=_clean_env(PYTHONPATH=str(stubs)))

    swig = import_package(PACKAGE_DIR)
    assert swig.returncode == 0 and "SWIG plugin registered" in swig.stdout, swig
    ipc = import_package(dest)
    assert ipc.returncode == 0, ipc.stderr
    assert "SWIG plugin registered" not in ipc.stdout
    print("test_ipc_build_does_not_register_the_swig_plugin: PASS")


# ─── the entry point ──────────────────────────────────────────────────

def test_entry_point_runs_from_a_pcm_folder_and_keeps_kicads_pipes_clean():
    """What KiCad does: run ipc_main.py by path from a folder named after the
    package identifier. No KiCad is listening, so the plugin must say so in
    a dialog, write nothing to stdout/stderr (KiCad would show it as an
    error) and log to the file instead."""
    dest = _assemble("com_github_hulryung_kicad-lcsc-manager")
    home = Path(tempfile.mkdtemp())
    shown = home / "messages.txt"
    stubs = _stub_dir()
    run = subprocess.run(
        [sys.executable, str(dest / "ipc_main.py")], cwd=str(dest),
        capture_output=True, text=True, timeout=120,
        env=_clean_env(HOME=str(home), USERPROFILE=str(home), PYTHONPATH=str(stubs),
                       STUB_WX_LOG=str(shown), KICAD_API_TOKEN="t",
                       KICAD_API_SOCKET="ipc://" + str(home / "no-kicad.sock")))
    assert run.returncode == 0, (run.returncode, run.stderr)
    assert run.stdout == "" and run.stderr == "", (run.stdout, run.stderr)
    message = shown.read_text(encoding="utf-8")
    # Without kicad-python installed it says so; with it, that KiCad isn't there.
    assert "kicad-python package is missing" in message or "couldn't reach KiCad" in message, message
    log = (home / ".kicad" / "lcsc_manager" / "logs" / "lcsc_manager.log").read_text(encoding="utf-8")
    assert "LCSC Manager" in log
    assert "Gtk-Message" in log, "stray output from C code belongs in the log too"
    path_at_start = Path(f"{shown}.path").read_text(encoding="utf-8").splitlines()
    assert str(dest.resolve()) not in path_at_start, \
        "the plugin folder must not stay on sys.path (its subpackages would shadow modules)"
    print("test_entry_point_runs_from_a_pcm_folder_and_keeps_kicads_pipes_clean: PASS")


def test_redirect_output_catches_c_level_writes():
    log = Path(tempfile.mkdtemp()) / "logs" / "out.log"
    code = textwrap.dedent(f"""
        import os, sys, warnings
        from pathlib import Path
        sys.path.insert(0, {str(PLUGINS)!r})
        from lcsc_manager.ipc_main import redirect_output
        redirect_output(Path({str(log)!r}))
        print("print ✓")
        sys.stderr.write("stderr\\n")
        os.write(1, b"fd 1\\n")
        os.write(2, b"fd 2\\n")
        warnings.warn("a warning")
    """)
    run = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                         env=_clean_env())
    assert run.returncode == 0, run.stderr
    assert run.stdout == "" and run.stderr == "", (run.stdout, run.stderr)
    text = log.read_text(encoding="utf-8")
    for expected in ("print ✓", "stderr", "fd 1", "fd 2", "a warning"):
        assert expected in text, (expected, text)
    print("test_redirect_output_catches_c_level_writes: PASS")


class _Host:
    """project_file() returns `result`, or raises it."""
    def __init__(self, result):
        self.result = result

    def project_file(self):
        if isinstance(self.result, BaseException):
            raise self.result
        return self.result


def test_find_project_explains_every_dead_end():
    folder = Path(tempfile.mkdtemp())
    board = folder / "board.kicad_pcb"
    board.write_text("")
    assert ipc_main.find_project(_Host(board)) == (board, "")
    for result, expected in [
            (None, "No project is open"),
            (folder / "untitled.kicad_pcb", "save your project first"),
            (ModuleNotFoundError("No module named 'kipy'"), "kicad-python package is missing"),
            (ConnectionError("Failed to connect to KiCad"), "couldn't reach KiCad"),
            (TimeoutError("timed out"), "couldn't reach KiCad")]:
        project, message = ipc_main.find_project(_Host(result))
        assert project is None and expected in message, (result, message)
    print("test_find_project_explains_every_dead_end: PASS")


class _StubWx:
    """Swap the stub wx in for the tests below; import the launcher fresh."""
    def __enter__(self):
        self.saved = {name: sys.modules.get(name)
                      for name in ("wx", "lcsc_manager.launcher",
                                   "lcsc_manager.dialog_search", "lcsc_manager.dialog")}
        wx = types.ModuleType("wx")
        exec(STUB_WX, wx.__dict__)
        sys.modules["wx"] = wx
        sys.modules.pop("lcsc_manager.launcher", None)
        import lcsc_manager.launcher as launcher
        self.wx, self.launcher = wx, launcher
        return self

    def __exit__(self, *exc):
        for name, module in self.saved.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module
        kicad_host.set_host(None)


def test_run_opens_the_dialog_for_the_open_project():
    folder = Path(tempfile.mkdtemp())
    board = folder / "board.kicad_pcb"
    board.write_text("")
    with _StubWx() as ctx:
        opened, errors = [], []
        ctx.launcher.open_main_dialog = opened.append
        ctx.launcher.show_error = errors.append
        host = _Host(board)
        assert ipc_main.run(host) == 0
        assert opened == [board] and errors == []
        assert kicad_host.get_host() is host, "the library code must use the same host"
        assert ctx.wx.app.assert_mode == ctx.wx.APP_ASSERT_LOG

        opened.clear()
        assert ipc_main.run(_Host(None)) == 0
        assert opened == [] and errors == [ipc_main.NO_PROJECT]
    print("test_run_opens_the_dialog_for_the_open_project: PASS")


def _fake_dialog_module(name, cls_name, shown):
    module = types.ModuleType(name)

    class Dialog:
        def __init__(self, parent, project_path):
            shown.append((cls_name, project_path))
        def ShowModal(self):
            return 5100
        def Destroy(self):
            shown.append("destroyed")

    setattr(module, cls_name, Dialog)
    return module


def test_launcher_falls_back_step_by_step():
    """Search dialog, else the basic dialog (with a one-time notice), else
    the part-number prompt — the same in both entry points."""
    with _StubWx() as ctx:
        launcher, wx = ctx.launcher, ctx.wx
        shown = []
        sys.modules["lcsc_manager.dialog_search"] = _fake_dialog_module(
            "lcsc_manager.dialog_search", "LCSCManagerSearchDialog", shown)
        launcher.open_main_dialog(Path("/p/board.kicad_pcb"))
        assert shown == [("LCSCManagerSearchDialog", "/p/board.kicad_pcb"), "destroyed"]
        assert wx.messages == []

        shown.clear()
        sys.modules["lcsc_manager.dialog_search"] = None          # fails to import
        sys.modules["lcsc_manager.dialog"] = _fake_dialog_module(
            "lcsc_manager.dialog", "LCSCManagerDialog", shown)
        launcher.open_main_dialog(Path("/p/board.kicad_pcb"))
        launcher.open_main_dialog(Path("/p/board.kicad_pcb"))
        assert shown.count("destroyed") == 2 and shown[0][0] == "LCSCManagerDialog"
        notices = [m for m in wx.messages if "Limited Mode" in m[0]]
        assert len(notices) == 1, "the limited-mode notice is shown once per process"

        sys.modules["lcsc_manager.dialog"] = None
        wx.messages.clear()
        launcher.open_main_dialog(Path("/p/board.kicad_pcb"))    # prompt, cancelled
        assert wx.messages == []
    print("test_launcher_falls_back_step_by_step: PASS")


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
    print("\nAll IPC plugin tests passed.")
