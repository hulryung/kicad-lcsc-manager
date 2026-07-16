"""Unit tests for the issue #14 fixes: degraded-mode messaging and the
public JLCPCB existence check.

Run with: python3 tests/test_issue14_fallback.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "plugins"))

from lcsc_manager.utils.deps import (
    describe_dialog_import_error,
    is_webview_import_error,
    webview_install_hint,
)
from lcsc_manager.api.lcsc_api import LCSCAPIClient


def test_webview_error_detected():
    """The classic Linux failure must be recognized and produce install hints."""
    exc = ImportError("No module named 'wx.html2'")
    assert is_webview_import_error(exc)
    msg = describe_dialog_import_error(exc)
    assert "python3-wxgtk-webview4.0" in msg, msg      # Debian/Ubuntu
    assert "python3-wxpython4-webview" in msg, msg     # Fedora
    assert "No module named 'wx.html2'" in msg, msg    # names the real cause
    assert "basic dialog" in msg, msg                  # explains the fallback
    print("test_webview_error_detected: PASS")


def test_generic_import_error_not_misattributed():
    """Other ImportErrors must show the real exception, not a webview hint
    (and never guess 'Pillow' like the old log message did)."""
    exc = ImportError("No module named 'requests'")
    assert not is_webview_import_error(exc)
    msg = describe_dialog_import_error(exc)
    assert "No module named 'requests'" in msg, msg
    assert "wxgtk-webview" not in msg, msg
    assert "Pillow" not in msg, msg
    print("test_generic_import_error_not_misattributed: PASS")


def test_non_import_error_still_described():
    """A non-ImportError (e.g. AttributeError at import time) is still named."""
    exc = AttributeError("module 'wx' has no attribute 'html2'")
    msg = describe_dialog_import_error(exc)
    assert "has no attribute 'html2'" in msg, msg
    # attribute error mentioning html2 counts as the webview case
    assert is_webview_import_error(exc)
    assert "python3-wxgtk-webview4.0" in msg, msg
    print("test_non_import_error_still_described: PASS")


def test_install_hint_covers_known_distros():
    hint = webview_install_hint()
    for needle in ("Debian/Ubuntu", "Fedora", "Arch"):
        assert needle in hint, hint
    print("test_install_hint_covers_known_distros: PASS")


def test_get_jlcpcb_info_is_public_delegate():
    """get_jlcpcb_info must delegate to _get_jlcpcb_info."""
    client = LCSCAPIClient()
    calls = []

    def fake_internal(lcsc_id, swallow_errors=True):
        calls.append((lcsc_id, swallow_errors))
        return {"stock": 42, "url": "https://example.com"}

    client._get_jlcpcb_info = fake_internal
    result = client.get_jlcpcb_info("C6056597")
    assert calls == [("C6056597", True)], calls
    assert result == {"stock": 42, "url": "https://example.com"}, result

    client.get_jlcpcb_info("C6056597", swallow_errors=False)
    assert calls[-1] == ("C6056597", False), calls
    print("test_get_jlcpcb_info_is_public_delegate: PASS")


def test_get_jlcpcb_info_error_modes():
    """Default swallows lookup errors to None; swallow_errors=False must
    propagate them so 'lookup failed' isn't shown as 'part does not exist'."""
    from lcsc_manager.api.lcsc_api import LCSCRateLimitError

    client = LCSCAPIClient()

    def throttled(*args, **kwargs):
        raise LCSCRateLimitError("simulated 429")

    client._make_request = throttled

    # Default: never raises, returns None (merge-stock-info callers).
    assert client.get_jlcpcb_info("C6056597") is None

    # Strict: propagates, so dialogs can render a rate-limit message.
    try:
        client.get_jlcpcb_info("C6056597", swallow_errors=False)
    except LCSCRateLimitError:
        print("test_get_jlcpcb_info_error_modes: PASS")
        return
    raise AssertionError("expected LCSCRateLimitError to propagate")


def test_dialog_search_webview_flag_exists():
    """dialog_search must expose HAS_WEBVIEW and guard the wx.html2 import.
    (Full import needs wx, so inspect the source instead.)"""
    src = (Path(__file__).parent.parent / "plugins" / "lcsc_manager"
           / "dialog_search.py").read_text(encoding="utf-8")
    assert "HAS_WEBVIEW = True" in src
    assert "HAS_WEBVIEW = False" in src
    assert "except ImportError" in src.split("class LCSCManagerSearchDialog")[0], \
        "wx.html2 import must be guarded at module level"
    # every SetPage call must be inside the None-guarded _set_webview_svg
    assert src.count("SetPage") == 1, "webview writes must funnel through _set_webview_svg"
    print("test_dialog_search_webview_flag_exists: PASS")


if __name__ == "__main__":
    test_webview_error_detected()
    test_generic_import_error_not_misattributed()
    test_non_import_error_still_described()
    test_install_hint_covers_known_distros()
    test_get_jlcpcb_info_is_public_delegate()
    test_get_jlcpcb_info_error_modes()
    test_dialog_search_webview_flag_exists()
    print("\nAll issue-14 tests passed.")
