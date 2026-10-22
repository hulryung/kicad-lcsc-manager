"""
Creating a wx WebView that can show the plugin's pages.

On macOS and Linux wx has one engine (WebKit). On Windows it has two, and
picks the old Internet Explorer one unless asked for Edge (WebView2): a
modern engine with WebGL, which the footprint details window needs. Edge
only works when the WebView2 runtime is installed, which Windows 11 and
most Windows 10 machines have; this module asks for it when it is there.

LCSC_WEBVIEW_BACKEND=edge|default overrides the choice (for the tests).
"""
import os
import sys
from typing import Optional

from .logger import get_logger

logger = get_logger()

_WEBVIEW2_CLIENT = "{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"


def webview2_runtime_installed() -> bool:
    """Whether the WebView2 (Evergreen) runtime is on this Windows machine:
    Microsoft's documented check is the EdgeUpdate client key's `pv`."""
    if sys.platform != "win32":
        return False
    import winreg
    for root, path in (
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients" + "\\" + _WEBVIEW2_CLIENT),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\EdgeUpdate\Clients" + "\\" + _WEBVIEW2_CLIENT),
            (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\EdgeUpdate\Clients" + "\\" + _WEBVIEW2_CLIENT)):
        try:
            with winreg.OpenKey(root, path) as key:
                version, _ = winreg.QueryValueEx(key, "pv")
        except OSError:
            continue
        if version and version != "0.0.0.0":
            return True
    return False


def choose_backend(html2, prefer_edge: bool):
    """The wx.html2 backend id to ask for, or None for wx's default."""
    wanted = os.environ.get("LCSC_WEBVIEW_BACKEND", "").lower()
    edge = getattr(html2, "WebViewBackendEdge", None)
    if sys.platform != "win32" or wanted == "default" or not edge:
        return None
    try:
        edge_ok = html2.WebView.IsBackendAvailable(edge)
    except Exception:
        edge_ok = False
    if edge_ok and (wanted == "edge" or (prefer_edge and webview2_runtime_installed())):
        return edge
    return None


def new_webview(parent, prefer_edge: bool = False):
    """A WebView, or None when wx has no usable backend here (the caller
    shows a placeholder). With prefer_edge, Edge on Windows when its
    runtime is installed; otherwise wx's default engine. The result has
    `.is_edge` set."""
    try:
        import wx.html2 as html2
    except ImportError:
        return None
    backend = choose_backend(html2, prefer_edge)
    try:
        if backend is not None:
            view = html2.WebView.New(parent, backend=backend)
        else:
            view = html2.WebView.New(parent)
    except Exception as e:
        logger.warning(f"WebView backend unavailable at runtime: {e}")
        return None
    view.is_edge = backend is not None
    return view
