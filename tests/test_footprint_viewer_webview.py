"""
The footprint details window in a real WebView, under KiCad's own Python:
the page loads with the pads, the ruler measures the right distance from
real mouse events, the 3D model is pushed in and (where the engine has
WebGL) rendered. Offline: the OBJ download is stubbed.

This is the test the Windows CI job exists for. On Windows wx defaults to
the Internet Explorer engine, which has no WebGL; the dialog asks for Edge
(WebView2), and this test reports which one it got (the user agent says).
WebGL is required only on engines that have it (Edge, WebKit).

With LCSC_SHOT_DIR set, a screenshot of the 2D and 3D views is saved
there (the CI job uploads them), so a person can look at the result.

Skips without KiCad's Python. Run with: python3 tests/test_footprint_viewer_webview.py
"""
import json
import os
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

REPO = Path(__file__).parent.parent
sys.path.insert(0, str(REPO / "tests"))
from kicad_python import kicad_python, no_window_restore   # noqa: E402

PLUGINS = REPO / "plugins"

# An LQFN-ish footprint: four 0.4 mm-pitch pads (canvas units, 1 = 0.254 mm)
# and a 3D model reference; the "download" returns a 2 mm cube.
PADS = [
    "PAD~RECT~3970.768~3002.7565~3.3465~0.7874~1~~1~0~3969.0947 3002.3628 3972.4411 3002.3628 "
    "3972.4411 3003.1502 3969.0947 3003.1502~0~gge1~0~~Y~0~0~0.1969~3",
    "PAD~RECT~3970.768~3004.3315~3.3465~0.7874~1~~2~0~3969.0947 3003.9378 3972.4411 3003.9378 "
    "3972.4411 3004.7252 3969.0947 3004.7252~0~gge2~0~~Y~0~0~0.1969~3",
    "PAD~RECT~3970.768~3005.9065~3.3465~0.7874~1~~3~0~~0~gge3~0~~Y~0~0~0.1969~3",
    "PAD~RECT~3984.252~3012.9925~12.2047~12.2047~1~~57~0~~0~gge4~0~~Y~0~0~0.1969~3",
]
SVGNODE = ('SVGNODE~{"gId":"g1","nodeName":"g","nodeType":1,"layerid":"19","attrs":{"c_width":"8","c_height":"8",'
           '"z":"0","c_rotation":"0,0,0","uuid":"testcube000000000000000000000000","c_origin":"3984.252,3012.9925",'
           '"title":"CUBE"}}')
CUBE_OBJ = "\n".join([
    "v -1 -1 0", "v 1 -1 0", "v 1 1 0", "v -1 1 0", "v -1 -1 2", "v 1 -1 2", "v 1 1 2", "v -1 1 2",
    "newmtl 1", "Kd 0.2 0.2 0.8", "d 0.0", "endmtl", "usemtl 1",
    "f 1// 2// 3// 4//", "f 5// 6// 7// 8//", "f 1// 2// 6// 5//", "f 2// 3// 7// 6//",
    "f 3// 4// 8// 7//", "f 4// 1// 5// 8//", ""])
SVG = ('<svg xmlns="http://www.w3.org/2000/svg" width="13mm" height="12mm" viewBox="3958 2987.8 51.4 50.3">'
       '<rect x="3958" y="2987.8" width="51.4" height="50.3" fill="#000"/>'
       '<rect x="3969.09" y="3002.36" width="3.35" height="0.79" fill="#f00"/>'
       '<rect x="3969.09" y="3003.94" width="3.35" height="0.79" fill="#f00"/>'
       '<rect x="3969.09" y="3005.51" width="3.35" height="0.79" fill="#f00"/>'
       '<rect x="3978.15" y="3006.89" width="12.2" height="12.2" fill="#f00"/></svg>')

SCRIPT = """
import json, sys, time, tempfile, os, faulthandler
faulthandler.dump_traceback_later(200, exit=True)     # where it hangs, if it hangs
print("STAGE start", flush=True)
from pathlib import Path
sys.path.insert(0, {plugins!r})
import wx
app = wx.App()
app.SetAssertMode(wx.APP_ASSERT_LOG)
class Collect(wx.Log):
    def __init__(self): super().__init__(); self.msgs = []
    def DoLogTextAtLevel(self, level, msg): self.msgs.append(msg)
col = Collect(); wx.Log.SetActiveTarget(col)

import lcsc_manager
import lcsc_manager.utils.config as cfgmod
from lcsc_manager.utils.config import Config
cfgmod._config_instance = Config(config_path=Path(tempfile.mkdtemp()) / "g.json")
diag = {{}}
try:
    import wx.html2 as html2
    for name in ("WebViewBackendEdge", "WebViewBackendIE"):
        if hasattr(html2, name):
            try:
                vi = html2.WebView.GetBackendVersionInfo(getattr(html2, name))
                diag[name + "_version"] = str(vi.GetVersionString()) if hasattr(vi, "GetVersionString") else repr(vi)
            except Exception as e:
                diag[name + "_version"] = "? " + str(e)
except Exception as e:
    diag["html2"] = str(e)
from lcsc_manager.converters import model_3d_converter
model_3d_converter.Model3DConverter._download_obj = lambda self, url: {obj!r}
from lcsc_manager.dialog_footprint_detail import FootprintDetailDialog

data = {{"easyeda_data": {{"packageDetail": {{"dataStr": {{
    "head": {{"x": 3984.252, "y": 3012.9925}}, "shape": {pads!r} + [{svgnode!r}]}}}}}}}}
print("STAGE imports done", flush=True)
d = FootprintDetailDialog(None, "C1", "TEST", {svg!r},
                          {{"x": 3968, "y": 2997.8, "width": 31.4, "height": 30.3}},
                          component_data=data, mesh_cache={{}})
out = {{"webview": d.webview is not None, "wx": wx.version(), "events": [], "diag": diag,
       "user_data": os.environ.get("WEBVIEW2_USER_DATA_FOLDER")}}
try:
    import wx.html2 as html2
    out["backends"] = {{name: bool(html2.WebView.IsBackendAvailable(getattr(html2, name)))
                       for name in ("WebViewBackendEdge", "WebViewBackendIE", "WebViewBackendWebKit")
                       if hasattr(html2, name)}}
    out["html2_dir"] = sorted(p.name for p in Path(html2.__file__).parent.glob("*ebView2*"))
except Exception as e:
    out["backends"] = str(e)
if d.webview is None:
    print("RESULT " + json.dumps(out)); sys.exit(0)
for name in ("EVT_WEBVIEW_LOADED", "EVT_WEBVIEW_ERROR", "EVT_WEBVIEW_NAVIGATED"):
    d.webview.Bind(getattr(html2, name), lambda e, n=name: (out["events"].append(n + " " + e.GetURL()[:60] + " " + e.GetString()[:120]), e.Skip()))
print("STAGE dialog built", flush=True)
d.Show()
print("STAGE shown", flush=True)

def pump(sec):
    # Dispatch window messages for `sec` seconds: WebView2's asynchronous
    # start-up completes through the message loop. MainLoop never returned
    # on Windows, Yield() dispatched nothing to WebView2, and Dispatch()
    # blocks on macOS even after Pending(); DispatchTimeout does neither.
    loop = wx.GUIEventLoop()
    previous = wx.EventLoop.GetActive()
    wx.EventLoop.SetActive(loop)
    end = time.time() + sec
    while time.time() < end:
        for _ in range(100):
            if loop.DispatchTimeout(1) != 1:
                break
        loop.ProcessIdle()
        app.ProcessPendingEvents()
        time.sleep(0.005)
    wx.EventLoop.SetActive(previous)

def stage(name):
    print("STAGE " + name, flush=True)

_script = {{"bound": None, "result": None}}
def js(code):
    # RunScriptAsync where it exists: a synchronous RunScript blocks for
    # good on the Edge engine. The result arrives as an event.
    w = d.webview
    if not hasattr(w, "RunScriptAsync"):
        r = w.RunScript(code)
        return r if isinstance(r, tuple) else (True, r)
    if _script["bound"] is not w:
        w.Bind(html2.EVT_WEBVIEW_SCRIPT_RESULT,
               lambda e: _script.__setitem__("result", (not e.IsError(), e.GetString())))
        _script["bound"] = w
    _script["result"] = None
    w.RunScriptAsync(code)
    end = time.time() + 15
    while _script["result"] is None and time.time() < end:
        pump(0.05)
    return _script["result"] or (False, "no result in 15 s")

def shot(name):
    folder = os.environ.get("LCSC_SHOT_DIR")
    if not folder: return
    d.Raise(); pump(0.7)
    r = d.GetScreenRect()
    try:
        bmp = wx.ScreenDC().GetAsBitmap().GetSubBitmap(wx.Rect(r.x, r.y, r.width, r.height))
        Path(folder).mkdir(parents=True, exist_ok=True)
        bmp.SaveFile(str(Path(folder) / name), wx.BITMAP_TYPE_PNG)
    except Exception as e:
        out.setdefault("shot_errors", []).append(str(e))

pump(1.0)
try:
    out["user_agent"] = d.webview.GetUserAgent()
except Exception as e:
    out["user_agent"] = "? " + str(e)
# No RunScript before a page has loaded: on an Edge view that never loads it
# blocks for good. The dialog's own watchdog rebuilds with IE after 8 s.
val = None; ok = False
for _ in range(300):
    pump(0.1)
    if d._page_loaded or d._page_signalled:
        break
out["loaded_event"] = d._page_loaded or d._page_signalled
out["script_messages"] = d._has_messages
out["rebuilt_with_ie"] = not getattr(d.webview, "is_edge", False) and bool(out.get("backends", {{}}).get("WebViewBackendEdge"))
if out["loaded_event"]:
    try:
        out["user_agent"] = d.webview.GetUserAgent()
    except Exception as e:
        out["user_agent"] = "? " + str(e)
    for _ in range(600):
        pump(0.1)
        ok, val = js("JSON.stringify(window.lcscDebug ? window.lcscDebug() : null)")
        if ok and val and val != "null" and json.loads(val)["status"] in ("ready", "failed", "none"):
            break
stage("polled " + repr(val)[:80])
out["runscript"] = bool(ok)
out["loaded"] = json.loads(val) if ok and val and val != "null" else None
if not out["loaded_event"]:
    out["wx_log"] = [m for m in col.msgs if "PgmOrNull" not in m]
    print("RESULT " + json.dumps(out)); sys.exit(0)
out["ready_state"] = repr(js("document.readyState + ' ' + (typeof DATA) + ' ' + document.title"))

measure = '''(function(){{
  var svg = document.querySelector('#view2d svg.world');
  function ev(t, x, y, tg){{ var p = svg.createSVGPoint(); p.x = x; p.y = y; var c = p.matrixTransform(svg.getScreenCTM());
    var e = document.createEvent('MouseEvents');
    e.initMouseEvent(t, true, true, window, 0, c.x, c.y, c.x, c.y, false, false, false, false, 0, null);
    (tg || svg).dispatchEvent(e); }}
  document.getElementById('bmeasure').click();
  var a = DATA.pads[0], b = DATA.pads[1];
  ev('mousemove', a.cx + 0.3, a.cy + 0.3); ev('mousedown', a.cx + 0.3, a.cy + 0.3); ev('mouseup', a.cx + 0.3, a.cy + 0.3, window);
  ev('mousemove', b.cx - 0.3, b.cy + 0.2); ev('mousedown', b.cx - 0.3, b.cy + 0.2); ev('mouseup', b.cx - 0.3, b.cy + 0.2, window);
  return document.getElementById('status').textContent;
}})()'''
ok, val = js(measure); out["measure"] = val if ok else None
stage("measured")
shot("footprint-2d.png")
js("document.getElementById('b3d').click(); 'ok'"); pump(2.0)
ok, val = js("JSON.stringify(window.lcscDebug())"); out["view3d"] = json.loads(val) if ok else None
shot("footprint-3d.png")
out["wx_log"] = [m for m in col.msgs if "PgmOrNull" not in m]
d.Destroy()
stage("probes")
if sys.platform == "win32":
    from lcsc_manager.utils.webview import enable_ie11_emulation, webview2_runtime_installed
    out["webview2_runtime"] = webview2_runtime_installed()
    for label, backend in (("ie_probe", "WebViewBackendIE"), ("edge_probe", "WebViewBackendEdge")):
        if not hasattr(html2, backend):
            continue
        try:
            if backend == "WebViewBackendIE":
                enable_ie11_emulation()
            f = wx.Dialog(None, title=label); f.SetSize((400, 300))
            probe = {{"events": []}}
            w = html2.WebView.New(f, backend=getattr(html2, backend))
            for name in ("EVT_WEBVIEW_LOADED", "EVT_WEBVIEW_ERROR"):
                w.Bind(getattr(html2, name), lambda e, n=name: (probe["events"].append(n + " " + e.GetString()[:160]), e.Skip()))
            w.SetPage("<html><body><script>document.title='t' + (1+1);</script>ok</body></html>", "")
            f.Show(); pump(4.0)
            probe.update(title=w.GetCurrentTitle(), ua=w.GetUserAgent()[:90])
            if any(e.startswith("EVT_WEBVIEW_LOADED") for e in probe["events"]):
                probe["run"] = repr(w.RunScript("1+1"))      # never on a view that didn't load
            out[label] = probe
            f.Destroy()
        except Exception as e:
            out[label] = "error " + str(e)
print("RESULT " + json.dumps(out))
"""


def _run_viewer(python, backend=None):
    code = SCRIPT.format(plugins=str(PLUGINS), obj=CUBE_OBJ, pads=PADS, svgnode=SVGNODE, svg=SVG)
    env = {k: v for k, v in os.environ.items()
           if k not in ("KICAD_API_TOKEN", "KICAD_API_SOCKET", "PYTHONPATH", "PYTHONHOME")}
    env["KICAD_API_TOKEN"] = "t"            # no SWIG registration attempt
    env["PYTHONIOENCODING"] = "utf-8"
    if backend:
        env["LCSC_WEBVIEW_BACKEND"] = backend
    # WebView2 keeps its profile next to the executable unless told otherwise,
    # and C:\Program Files\KiCad is not writable.
    env.setdefault("WEBVIEW2_USER_DATA_FOLDER", tempfile.mkdtemp(prefix="webview2-"))
    try:
        run = subprocess.run([str(python), "-u", "-c", textwrap.dedent(code), *no_window_restore()],
                             env=env, capture_output=True, encoding="utf-8", errors="replace",
                             timeout=240)
    except subprocess.TimeoutExpired as e:
        def text(data):
            return data.decode("utf-8", "replace") if isinstance(data, bytes) else (data or "")
        raise AssertionError("the viewer script hung; its output so far:\n"
                             + text(e.stdout)[-2000:] + text(e.stderr)[-1000:])
    assert run.returncode == 0, run.stdout[-1500:] + run.stderr[-1500:]
    line = [l for l in run.stdout.splitlines() if l.startswith("RESULT ")]
    assert line, run.stdout[-1500:] + run.stderr[-1500:]
    out = json.loads(line[-1][len("RESULT "):])
    print("  wx:", out.get("wx"), " backends:", out.get("backends"), " loader:", out.get("html2_dir"))
    print("  runtime:", out.get("webview2_runtime"), " user data:", out.get("user_data"))
    print("  IE probe:", out.get("ie_probe"))
    print("  Edge probe:", out.get("edge_probe"))
    print("  engine:", out.get("user_agent"), " loaded event:", out.get("loaded_event"),
          " script messages:", out.get("script_messages"), " rebuilt with IE:", out.get("rebuilt_with_ie"))
    print("  page:", out.get("ready_state"))
    for e in out.get("events", []):
        print("  event:", e)
    return out


def _check_viewer(out, need_webgl):
    assert out["runscript"], "RunScript did not succeed on this engine (see the lines above)"
    loaded = out["loaded"]
    assert loaded and loaded["pads"] == 4 and loaded["snaps"] >= 12, out
    assert loaded["status"] == "ready", out            # the (stubbed) model arrived
    assert out["measure"] and "0.400 mm" in out["measure"], out["measure"]
    v3 = out["view3d"]
    print("  3D:", v3)
    assert v3["status"] == "ready"
    if need_webgl or (v3.get("gl") and v3.get("mesh")):
        assert v3["gl"] and v3["mesh"] and v3["parts"] == 1 and v3["tex"], v3
        # The 2 mm cube sits at the centre of the view, so the middle pixel
        # is its blue-ish top, lit, not the grey background.
        r, g, b = v3["centre"]
        assert b > r + 40 and b > g + 40, v3["centre"]
    else:
        print("  (engine without WebGL: 3D rendering not checked)")
    assert out["wx_log"] == [], out["wx_log"]


def test_footprint_viewer_in_a_real_webview():
    python = kicad_python()
    if not python.exists():
        print("test_footprint_viewer_in_a_real_webview: SKIP (no KiCad python)")
        return
    out = _run_viewer(python)
    if not out["webview"]:
        print("test_footprint_viewer_in_a_real_webview: SKIP (no WebView backend)")
        return
    ua = out.get("user_agent") or ""
    assert out.get("loaded_event"), "no page ever loaded, not even after the IE fallback"
    # On Windows the default is Edge when its runtime is installed (the CI
    # job installs it); elsewhere the platform engine, which has WebGL.
    if sys.platform == "win32" and out.get("rebuilt_with_ie"):
        print("  WARNING: Edge (WebView2) never loaded a page here; the window fell back to IE")
    need_webgl = sys.platform != "win32" or "Edg/" in ua
    _check_viewer(out, need_webgl)
    print("test_footprint_viewer_in_a_real_webview: PASS"
          + (" (on the IE fallback)" if out.get("rebuilt_with_ie") else ""))


def test_footprint_viewer_on_internet_explorer():
    """Windows without the WebView2 runtime: IE in IE11 mode must still show
    the drawing and measure; 3D is checked only if IE's WebGL works."""
    python = kicad_python()
    if sys.platform != "win32" or not python.exists():
        print("test_footprint_viewer_on_internet_explorer: SKIP (not Windows with KiCad)")
        return
    out = _run_viewer(python, backend="ie")
    ua = out.get("user_agent") or ""
    assert "Trident" in ua or "MSIE" in ua, f"expected Internet Explorer, got: {ua!r}"
    assert "MSIE 7.0" not in ua, "IE is still in IE7 emulation; the registry value didn't take"
    _check_viewer(out, need_webgl=False)
    print("test_footprint_viewer_on_internet_explorer: PASS")


if __name__ == "__main__":
    test_footprint_viewer_in_a_real_webview()
    test_footprint_viewer_on_internet_explorer()
    print("\nAll footprint viewer WebView tests passed.")
