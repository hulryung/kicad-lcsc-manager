"""Tests for the responsiveness fixes that followed 0.9.1:

- requests are spaced per host, not 5 s apart whatever the host (a BOM spent
  10 s per part waiting), and the limiter is safe to use from several threads;
- searching runs off the GUI thread, and the list, the results and the
  selection always agree, also after a failed or empty search;
- "Load More" continues the search that produced the list;
- the dialog fits on a small screen; status colours follow the theme;
- downloads outside the API client use the same CA bundle;
- the log file is rotated, and logging can't stop the plugin from loading.

The dialog checks run the real dialog under KiCad's Python (skipped without
KiCad).

Run with: python3 tests/test_search_and_speed.py
"""
import logging
import os
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch

REPO = Path(__file__).parent.parent
sys.path.insert(0, str(REPO / "plugins"))

import lcsc_manager  # noqa: F401  puts the bundled requests on sys.path
import requests

import lcsc_manager.api.lcsc_api as api
from lcsc_manager.api.lcsc_api import LCSCAPIClient, LCSCRateLimitError
from lcsc_manager.utils import logger as logmod
from lcsc_manager.utils.ui import clamp_size

PLUGIN_DIR = REPO / "plugins" / "lcsc_manager"
KICAD_PYTHON = Path("/Applications/KiCad/KiCad.app/Contents/Frameworks/"
                    "Python.framework/Versions/Current/bin/python3")
EASYEDA = "https://easyeda.com/api/products/C1/components"
JLCPCB = LCSCAPIClient.JLCPCB_SEARCH_URL


class _Clock:
    """Stand-in for time.monotonic/time.sleep: sleeping advances the clock."""
    def __init__(self):
        self.now, self.sleeps = 1000.0, []

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(round(seconds, 3))
        self.now += seconds


def _fresh_limiter():
    LCSCAPIClient._next_request_at.clear()
    LCSCAPIClient._host_interval.clear()


# ─── request spacing ──────────────────────────────────────────────────

def test_requests_are_spaced_per_host():
    _fresh_limiter()
    clock = _Clock()
    client = LCSCAPIClient()
    with patch.object(api.time, "monotonic", clock.monotonic), \
            patch.object(api.time, "sleep", clock.sleep):
        client._rate_limit(EASYEDA)                 # first request: no wait
        client._rate_limit(JLCPCB)                  # another host: no wait
        assert clock.sleeps == [], "0.9.1 waited 5 s here"
        client._rate_limit(EASYEDA)
        assert clock.sleeps == [LCSCAPIClient.REQUEST_INTERVAL]
        client._rate_limit(JLCPCB)
        # JLCPCB keeps a wider gap; the 0.5 s already slept counts toward it.
        assert clock.sleeps[-1] == 0.5 and len(clock.sleeps) == 2
        clock.now += 60
        client._rate_limit(EASYEDA)
        assert len(clock.sleeps) == 2, "no wait after a pause"
    assert LCSCAPIClient.REQUEST_INTERVAL <= 1.0 and LCSCAPIClient.HOST_INTERVALS["jlcpcb.com"] <= 2.0
    print("test_requests_are_spaced_per_host: PASS")


def test_rate_limiter_gives_each_thread_its_own_slot():
    """Twenty threads asking at once must be spread out, not all let through
    (the old limiter read and wrote its timestamp without a lock)."""
    _fresh_limiter()
    waits, lock = [], threading.Lock()
    start = 5000.0

    def fake_sleep(seconds):
        with lock:
            waits.append(round(seconds, 3))

    client = LCSCAPIClient()
    with patch.object(api.time, "monotonic", lambda: start), \
            patch.object(api.time, "sleep", fake_sleep):
        threads = [threading.Thread(target=client._rate_limit, args=(EASYEDA,))
                   for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
    step = LCSCAPIClient.REQUEST_INTERVAL
    assert sorted(waits) == [round(step * i, 3) for i in range(1, 20)], sorted(waits)
    print("test_rate_limiter_gives_each_thread_its_own_slot: PASS")


def _session_with_status(*statuses):
    """Mock session answering with the given HTTP statuses in turn."""
    responses = []
    for status in statuses:
        resp = MagicMock()
        resp.status_code = status
        if status >= 400:
            resp.raise_for_status.side_effect = requests.exceptions.HTTPError(response=resp)
        resp.json.return_value = {"ok": True}
        responses.append(resp)
    sess = MagicMock()
    sess.request.side_effect = responses
    return sess


def test_a_throttling_host_gets_a_wider_gap():
    _fresh_limiter()
    client = LCSCAPIClient()
    with patch.object(LCSCAPIClient, "_get_session",
                      return_value=_session_with_status(403, 200)), \
            patch.object(api.time, "sleep"):
        assert client._make_request("GET", EASYEDA) == {"ok": True}
    assert client._interval("easyeda.com") == 2.0, "backs off after a 403"
    assert client._interval("jlcpcb.com") == 1.0, "other hosts are unaffected"
    for _ in range(5):
        client._slow_down(EASYEDA)
    assert client._interval("easyeda.com") == LCSCAPIClient.MAX_REQUEST_INTERVAL
    _fresh_limiter()
    print("test_a_throttling_host_gets_a_wider_gap: PASS")


def test_optional_stock_lookup_does_not_hold_up_an_import():
    """Stock and price are extras; a throttled JLCPCB used to cost a minute
    of retries (10 + 20 + 30 s) on every part."""
    _fresh_limiter()
    client = LCSCAPIClient()
    clock = _Clock()
    slept = clock.sleeps            # gaps between requests are at most 5 s
    with patch.object(LCSCAPIClient, "_get_session",
                      side_effect=lambda: _session_with_status(403)), \
            patch.object(api.time, "monotonic", clock.monotonic), \
            patch.object(api.time, "sleep", clock.sleep):
        assert client._get_jlcpcb_info("C1") is None
        retry_waits = [s for s in slept if s >= LCSCAPIClient.RETRY_DELAY]
        assert retry_waits == [10.0], retry_waits
        slept.clear()
        try:
            client._get_jlcpcb_info("C1", swallow_errors=False)
        except LCSCRateLimitError:
            pass
        else:
            raise AssertionError("an explicit lookup still reports rate limiting")
        assert [s for s in slept if s >= 10] == [10.0, 20.0, 30.0]
    _fresh_limiter()
    print("test_optional_stock_lookup_does_not_hold_up_an_import: PASS")


def test_no_encodings_requests_cannot_decode():
    """`br, zstd` were advertised, but requests only decodes them when extra
    packages are installed; a CDN choosing one made the JSON unreadable."""
    session = LCSCAPIClient()._get_session()
    try:
        # Left to requests, which lists exactly what this Python can decode.
        assert session.headers.get("Accept-Encoding") == \
            requests.utils.default_headers()["Accept-Encoding"]
        assert session.verify == api.ca_bundle()
    finally:
        session.close()
    print("test_no_encodings_requests_cannot_decode: PASS")


def test_every_download_uses_the_ca_bundle():
    from lcsc_manager.converters import model_3d_converter as m3d
    calls = []

    def fake_get(url, **kwargs):
        calls.append(kwargs)
        resp = MagicMock()
        resp.status_code = 200
        resp.content = b"data"
        return resp

    converter = m3d.Model3DConverter()
    with patch.object(m3d.requests, "get", fake_get):
        assert converter._download_obj("https://modules.easyeda.com/3dmodel/x") == "data"
        assert converter._download_step("https://modules.easyeda.com/q/x") == b"data"
    assert [c.get("verify") for c in calls] == [api.ca_bundle()] * 2, calls
    search = (PLUGIN_DIR / "dialog_search.py").read_text(encoding="utf-8")
    svg = search.split("def _fetch_easyeda_svgs")[1].split("def _load_previews_async")[0]
    assert "verify=ca_bundle()" in svg
    assert "self._svg_cache[lcsc_id] = None\n            return None\n\n        except" not in svg
    assert svg.count("self._svg_cache[lcsc_id] = None") == 1, \
        "a timeout must not hide the preview for the whole session"
    print("test_every_download_uses_the_ca_bundle: PASS")


# ─── logging ──────────────────────────────────────────────────────────

def _isolated_logging(home):
    """Run setup_logger() from scratch against a temporary home."""
    base = logging.getLogger(logmod.BASE)
    saved = list(base.handlers)
    for handler in saved:
        base.removeHandler(handler)
    return base, saved


def test_log_is_rotated_and_shared():
    home = Path(tempfile.mkdtemp())
    base, saved = _isolated_logging(home)
    try:
        with patch.object(Path, "home", return_value=home), \
                patch.object(logmod, "MAX_BYTES", 2000):
            log = logmod.get_logger()
            child = logmod.get_logger("library_manager")
            assert child.name == "lcsc_manager.library_manager" and child.parent is log
            assert logmod.get_logger("library_manager") is child
            files = [h for h in log.handlers if isinstance(h, logging.FileHandler)]
            assert len(files) == 1 and not child.handlers, "one file handler for every module"
            assert log.propagate is False
            for i in range(200):
                child.debug("x" * 50 + str(i))
            for handler in log.handlers:
                handler.flush()
            folder = home / ".kicad" / "lcsc_manager" / "logs"
            names = sorted(p.name for p in folder.iterdir())
            assert names == ["lcsc_manager.log", "lcsc_manager.log.1", "lcsc_manager.log.2"], names
            assert all(p.stat().st_size <= 2100 for p in folder.iterdir())
            assert "lcsc_manager.library_manager - DEBUG" in (folder / "lcsc_manager.log").read_text()
    finally:
        for handler in list(base.handlers):
            base.removeHandler(handler)
            handler.close()
        for handler in saved:
            base.addHandler(handler)
    print("test_log_is_rotated_and_shared: PASS")


def test_an_unwritable_home_does_not_stop_the_plugin():
    home = Path(tempfile.mkdtemp())
    (home / ".kicad").write_text("a file where the folder should be")
    base, saved = _isolated_logging(home)
    try:
        with patch.object(Path, "home", return_value=home):
            log = logmod.get_logger("anything")         # 0.9.1 raised here
            log.info("still works")
            assert not any(isinstance(h, logging.FileHandler) for h in base.handlers)
    finally:
        for handler in list(base.handlers):
            base.removeHandler(handler)
        for handler in saved:
            base.addHandler(handler)
    print("test_an_unwritable_home_does_not_stop_the_plugin: PASS")


# ─── window size and colours ──────────────────────────────────────────

def test_dialog_size_is_clamped_to_the_screen():
    big = ((1400, 900), (860, 620))
    assert clamp_size(*big, area=(2560, 1400)) == ((1400, 900), (860, 620))
    # A 1366x768 laptop (menu bar and dock taken off): 0.9.1 demanded 1200x800.
    size, minimum = clamp_size(*big, area=(1366, 728))
    assert size == (1326, 688) and minimum == (860, 620)
    size, minimum = clamp_size(*big, area=(1024, 600))
    assert size == (984, 560) and minimum == (860, 560), "the minimum never exceeds the size"
    print("test_dialog_size_is_clamped_to_the_screen: PASS")


def test_no_fixed_colours_or_oversized_minimums_left():
    for name in ("dialog_search.py", "dialog.py", "dialog_bom.py", "dialog_settings.py"):
        source = (PLUGIN_DIR / name).read_text(encoding="utf-8")
        assert "wx.Colour(" not in source, f"{name}: use status_colour() so dark mode stays readable"
    search = (PLUGIN_DIR / "dialog_search.py").read_text(encoding="utf-8")
    assert "SetMinSize((1200, 800))" not in search and "fit_to_screen(self" in search
    print("test_no_fixed_colours_or_oversized_minimums_left: PASS")


# ─── the search dialog, for real ──────────────────────────────────────

DIALOG_SCRIPT = """
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
from lcsc_manager.api.lcsc_api import LCSCAPIError
from lcsc_manager.dialog_search import LCSCManagerSearchDialog
from lcsc_manager.utils.ui import status_colour

boxes = []
wx.MessageBox = lambda message, caption="", style=0, parent=None: boxes.append(caption) or wx.OK

class FakeApi:
    def __init__(self):
        self.calls, self.plan, self.gui_thread = [], [], threading.get_ident()
        self.off_gui_thread = True
    def advanced_search(self, component_name, value, package, manufacturer, page):
        self.calls.append((component_name, package, page))
        if threading.get_ident() == self.gui_thread:
            self.off_gui_thread = False
        delay, outcome = self.plan.pop(0)
        time.sleep(delay)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome
    def search_component(self, lcsc_id):
        return None

def rows(prefix, count):
    return [{{"lcsc": {{"number": f"{{prefix}}{{i}}"}}, "title": f"T{{i}}", "package": "0603",
             "price": float(count - i), "stockCount": i, "libraryType": "Basic"}}
            for i in range(count)]

dlg = LCSCManagerSearchDialog(None, str(pcb))
fake = dlg.api_client = FakeApi()
out = print

def state():
    selected = (dlg.selected_component or {{}}).get("lcsc", {{}}).get("number")
    row = dlg.results_list.GetFirstSelected()
    shown = dlg.results_list.GetItemText(row) if row >= 0 else None
    return (dlg.results_list.GetItemCount(), len(dlg.search_results), selected, shown,
            dlg.load_more_btn.IsEnabled(), dlg.current_page, dlg.results_label.GetLabel())

def idle():
    return dlg.search_btn.IsEnabled()

def search(text, plan):
    fake.plan.append(plan)
    dlg.name_input.SetValue(text)
    dlg._on_search(None)

def step_first():
    search("res", (0.3, rows("A", 20)))
    out("while searching:", dlg.search_btn.IsEnabled(), dlg.results_label.GetLabel())
def after_first():
    out("first:", state())
    dlg.results_list.Select(3)
def step_failed():
    out("selected:", state()[2:4])
    search("other", (0.0, LCSCAPIError("boom")))
def after_failed():
    out("failed:", state(), boxes[-1:])
def step_more():
    dlg.name_input.SetValue("something else typed meanwhile")
    fake.plan.append((0.0, rows("B", 5)))
    dlg._on_load_more(None)
def after_more():
    out("more:", state(), fake.calls[-1])
def step_more_fails():
    dlg.load_more_btn.Enable(True)
    fake.plan.append((0.0, LCSCAPIError("boom")))
    dlg._on_load_more(None)
def after_more_fails():
    out("more failed:", dlg.current_page, dlg.results_list.GetItemCount(), fake.calls[-1])
def step_sort():
    event = wx.ListEvent(wx.wxEVT_LIST_COL_CLICK); event.SetColumn(3)
    dlg._on_column_click(event)
    out("sorted:", dlg.results_list.GetItemText(0), state()[2:4])
def step_stale():
    search("slow", (0.6, rows("S", 3)))
    fake.plan.append((0.0, rows("F", 2)))
    dlg.name_input.SetValue("fast"); dlg.search_btn.Enable(); dlg._on_search(None)
def after_stale():
    time.sleep(0.8); wx.Yield()                      # let the slow one report in
    out("stale:", state()[:2], dlg.results_list.GetItemText(0))
def step_empty():
    dlg.results_list.Select(1)
    search("nothing", (0.0, []))
def after_empty():
    out("empty:", state(), boxes[-1:])
def step_close():
    search("late", (0.3, rows("L", 4)))
    dlg._closing = True
def after_close():
    time.sleep(0.5); wx.Yield()
    out("closed:", dlg.results_list.GetItemCount())
    area = wx.Display(max(0, wx.Display.GetFromWindow(dlg))).GetClientArea()
    w, h = dlg.GetSize()
    out("fits screen:", w <= area.width and h <= area.height, dlg.GetMinSize().Get() <= (860, 620))
    out("colour:", status_colour("ok").Get()[:3] in ((0, 110, 0), (120, 205, 120)))
    out("off gui thread:", fake.off_gui_thread)

STEPS = [step_first, after_first, step_failed, after_failed, step_more, after_more,
         step_more_fails, after_more_fails, step_sort, step_stale, after_stale,
         step_empty, after_empty, step_close, after_close]

def run(index, tries=0):
    if not idle() and not dlg._closing and tries < 100:
        wx.CallLater(50, run, index, tries + 1)
        return
    if index == len(STEPS):
        dlg.Destroy(); app.ExitMainLoop(); return
    STEPS[index]()
    wx.CallLater(120, run, index + 1)

dlg.Show()
wx.CallLater(200, run, 0)
app.MainLoop()
"""


def test_search_dialog_under_kicad_python():
    if not KICAD_PYTHON.exists():
        print("test_search_dialog_under_kicad_python: SKIP (no KiCad python)")
        return
    home = tempfile.mkdtemp()
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "PYTHONHOME")}
    env.update(HOME=home, KICAD_CONFIG_HOME=home, KICAD_API_TOKEN="t")   # no SWIG registration
    run = subprocess.run([str(KICAD_PYTHON), "-c",
                          DIALOG_SCRIPT.format(plugins=str(REPO / "plugins")),
                          "-ApplePersistenceIgnoreState", "YES"],
                         capture_output=True, text=True, env=env, timeout=120)
    out = run.stdout
    assert run.returncode == 0, run.stderr[-1500:]
    expected = [
        # The button is disabled and the label says so while a search runs.
        "while searching: False Search Results — searching…",
        "first: (20, 20, None, None, True, 1, 'Search Results (20)')",
        "selected: ('A3', 'A3')",
        # A failed search changes nothing on screen: list, results, selection.
        "failed: (20, 20, 'A3', 'A3', True, 1, 'Search Results (20)') ['Search Error']",
        # Load More continues the original search, whatever the box says now,
        # and keeps the selection.
        "more: (25, 25, 'A3', 'A3', False, 2, 'Search Results (25)') ('res', '', 2)",
        # A failed page isn't skipped: the next try asks for page 3 again.
        "more failed: 2 25 ('res', '', 3)",
        # Sorting by price moves the rows; the selection follows its part.
        "sorted: A19 ('A3', 'A3')",
        # A slower, older search can't overwrite a newer one's results.
        "stale: (2, 2) F1",        # (still sorted by price)
        # A search that finds nothing empties the list and the selection.
        "empty: (0, 0, None, None, False, 1, 'Search Results') ['No Results']",
        "closed: 0",
        "fits screen: True True",
        "colour: True",
        "off gui thread: True",
    ]
    for line in expected:
        assert line in out, f"missing: {line}\n--- got:\n{out}\n{run.stderr[-600:]}"
    print("test_search_dialog_under_kicad_python: PASS")


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
    print("\nAll search-and-speed tests passed.")
