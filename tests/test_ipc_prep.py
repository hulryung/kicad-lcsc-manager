"""Preparation for the IPC API port (#19): code that must already hold in an
IPC plugin process, where KiCad runs us as a separate Python process with
KICAD_API_TOKEN set, pcbnew importable (the venv sees KiCad's site-packages)
and a standalone wx.App in which wx assertions raise.

1. Importing the package must not register the SWIG ActionPlugin there —
   with a wx.App already created that registration raises SystemError and
   the import fails.
2. The dialogs must be free of wx assertions — inside pcbnew KiCad swallows
   them, but standalone they stop a dialog from opening.

The KiCad-Python checks run only where KiCad is installed (skipped elsewhere).

Run with: python3 tests/test_ipc_prep.py
"""
import os
import subprocess
import sys
import textwrap
from pathlib import Path

REPO = Path(__file__).parent.parent
PLUGINS = REPO / "plugins"
sys.path.insert(0, str(PLUGINS))

from lcsc_manager.utils.runtime import in_ipc_plugin_process

KICAD_PYTHON = Path(
    "/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework"
    "/Versions/Current/bin/python3"
)


def _env(**extra):
    env = {k: v for k, v in os.environ.items()
           if k not in ("KICAD_API_TOKEN", "KICAD_API_SOCKET",
                        "WXSUPPRESS_SIZER_FLAGS_CHECK", "PYTHONPATH", "PYTHONHOME")}
    env.update(extra)
    return env


def _run(python, code, **env):
    return subprocess.run([str(python), "-c", textwrap.dedent(code)],
                          env=_env(**env), capture_output=True, text=True,
                          timeout=300)


def test_only_the_token_marks_an_ipc_plugin_process():
    saved = {k: os.environ.pop(k, None) for k in ("KICAD_API_TOKEN", "KICAD_API_SOCKET")}
    try:
        assert not in_ipc_plugin_process()
        os.environ["KICAD_API_SOCKET"] = "ipc:///tmp/kicad/api.sock"
        assert not in_ipc_plugin_process(), \
            "a scripting user's exported socket must not disable the SWIG plugin"
        os.environ["KICAD_API_TOKEN"] = "abc"
        assert in_ipc_plugin_process()
    finally:
        for k, v in saved.items():
            os.environ.pop(k, None)
            if v is not None:
                os.environ[k] = v
    print("test_only_the_token_marks_an_ipc_plugin_process: PASS")


def test_package_import_skips_swig_registration_in_ipc_process():
    code = f"""
        import sys; sys.path.insert(0, {str(PLUGINS)!r})
        import lcsc_manager
        print("plugin loaded:", "lcsc_manager.plugin" in sys.modules)
    """
    run = _run(sys.executable, code, KICAD_API_TOKEN="t")
    assert run.returncode == 0, run.stderr
    assert "plugin loaded: False" in run.stdout, run.stdout
    print("test_package_import_skips_swig_registration_in_ipc_process: PASS")


def test_kicad_python_ipc_import_with_wx_app():
    if not KICAD_PYTHON.exists():
        print("test_kicad_python_ipc_import_with_wx_app: SKIP (no KiCad python)")
        return
    code = f"""
        import sys, wx
        app = wx.App()                        # an IPC entrypoint creates this first
        sys.path.insert(0, {str(PLUGINS)!r})
        import lcsc_manager
        print("plugin loaded:", "lcsc_manager.plugin" in sys.modules)
    """
    run = _run(KICAD_PYTHON, code, KICAD_API_TOKEN="t")
    assert run.returncode == 0, run.stderr[-800:]
    assert "plugin loaded: False" in run.stdout, run.stdout
    print("test_kicad_python_ipc_import_with_wx_app: PASS")


DIALOGS_SCRIPT = f"""
import sys, tempfile
from pathlib import Path
sys.path.insert(0, {str(PLUGINS)!r})
import wx
app = wx.App()
app.SetAssertMode(wx.APP_ASSERT_LOG)
class Collect(wx.Log):
    def __init__(self):
        super().__init__(); self.msgs = []
    def DoLogTextAtLevel(self, level, msg):
        self.msgs.append(msg)
col = Collect(); wx.Log.SetActiveTarget(col)

import lcsc_manager                                   # real package, token set
import lcsc_manager.utils.config as cfgmod
from lcsc_manager.utils.config import Config
root = Path(tempfile.mkdtemp()); pcb = root / "b.kicad_pcb"; pcb.write_text("")
cfgmod._config_instance = Config(config_path=root / "g.json")   # never the user's
wx.MessageBox = lambda *a, **k: wx.OK

from lcsc_manager.dialog_search import LCSCManagerSearchDialog
from lcsc_manager.dialog import LCSCManagerDialog, OverwriteConfirmDialog
from lcsc_manager.dialog_settings import SettingsDialog
from lcsc_manager.dialog_bom import BomImportDialog, _SummaryDialog
from lcsc_manager.bom.bom_parser import parse_bom

def search():
    d = LCSCManagerSearchDialog(None, str(pcb))
    d.search_results = [dict(lcsc={{"number": "C1"}}, uuid="C1", title="R", package="0603",
                             price=0.01, stockCount=5, libraryType="Basic")]
    d._populate_results_list(); d._sort_results(1)
    svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><rect width="5" height="5"/></svg>'
    d._display_previews(svg, svg, "specs")
    class P:
        def Update(self, v, m): pass
        def Destroy(self): pass
    d._import_progress = P()
    d._import_finish(True, "Import completed!", "C1", True, ["note"], False)
    return d

def settings():
    d = SettingsDialog(None, cfgmod._config_instance, pcb)
    d.EndModal = lambda code: None
    d.radio_loc_shared.SetValue(True); d._on_location_change(None)
    d.shared_path_ctrl.SetValue(str(root / "shared"))
    d._set_scope("project"); d._set_scope("global"); d._on_save(None)
    return d

bom = root / "bom.csv"
bom.write_text("Comment,Designator,Footprint,LCSC Part #\\n10k,R1,R0603,C25804\\n")
for label, build in (
        ("search", search),
        ("basic", lambda: LCSCManagerDialog(None, pcb)),
        ("overwrite", lambda: OverwriteConfirmDialog(None, {{"symbol": True}}, "R1")),
        ("settings", settings),
        ("bom", lambda: BomImportDialog(None, parse_bom(str(bom)), None, None)),
        ("bom summary", lambda: _SummaryDialog(None, "t", "x"))):
    w = build(); w.Layout(); w.Destroy()
    print("built", label)
print("ASSERTS", len(col.msgs))
for m in col.msgs:
    print("  ->", " ".join(m.split())[:200])
"""


def test_dialogs_are_assertion_clean_standalone():
    if not KICAD_PYTHON.exists():
        print("test_dialogs_are_assertion_clean_standalone: SKIP (no KiCad python)")
        return
    run = _run(KICAD_PYTHON, DIALOGS_SCRIPT, KICAD_API_TOKEN="t")
    assert run.returncode == 0, run.stdout[-800:] + run.stderr[-800:]
    assert "ASSERTS 0" in run.stdout, \
        "wx assertions (fatal outside pcbnew):\n" + run.stdout
    print("test_dialogs_are_assertion_clean_standalone: PASS")


if __name__ == "__main__":
    test_only_the_token_marks_an_ipc_plugin_process()
    test_package_import_skips_swig_registration_in_ipc_process()
    test_kicad_python_ipc_import_with_wx_app()
    test_dialogs_are_assertion_clean_standalone()
    print("\nAll IPC-prep tests passed.")
