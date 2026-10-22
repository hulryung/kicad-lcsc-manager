"""
Creating a wx WebView that can show the plugin's pages.

On macOS and Linux wx has one engine (WebKit). On Windows it has two: Edge
(WebView2, a modern engine with WebGL) and Internet Explorer. wx picks IE
unless asked for Edge, and Edge only works when the "WebView2 Runtime" is
installed and working, which Windows 11 and most Windows 10 machines have.
IE, in turn, starts in IE7 emulation, where neither inline SVG (the
previews) nor the footprint viewer's JavaScript works; a per-executable
registry value puts it in IE11 mode. This module makes those choices in one
place: the previews stay on IE (IE11 mode), which is what always worked
there; the footprint details window asks for Edge and falls back to IE when
Edge never loads.

LCSC_WEBVIEW_BACKEND=edge|ie|default overrides the choice (for the tests).
"""
import os
import sys
from pathlib import Path
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


def enable_ie11_emulation() -> bool:
    """Put IE-backed WebViews of this process's executable in IE11 mode
    (HKCU FEATURE_BROWSER_EMULATION = 11001). Returns whether it is set."""
    if sys.platform != "win32":
        return False
    import winreg
    exe = Path(sys.executable).name
    path = r"Software\Microsoft\Internet Explorer\Main\FeatureControl\FEATURE_BROWSER_EMULATION"
    try:
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, path, 0, winreg.KEY_SET_VALUE | winreg.KEY_READ) as key:
            try:
                current, _ = winreg.QueryValueEx(key, exe)
            except OSError:
                current = None
            if current != 11001:
                winreg.SetValueEx(key, exe, 0, winreg.REG_DWORD, 11001)
                logger.info(f"IE11 emulation set for {exe}")
        return True
    except OSError as e:
        logger.warning(f"Could not set IE11 emulation for {exe}: {e}")
        return False


_edge_broken = False


def mark_edge_broken() -> None:
    """Called when an Edge WebView never loaded its page (seen on machines
    whose WebView2 runtime is present but not working): the rest of the
    session uses IE."""
    global _edge_broken
    if not _edge_broken:
        logger.warning("The Edge (WebView2) engine did not load a page; using Internet Explorer")
    _edge_broken = True


def choose_backend(html2, prefer_edge: bool):
    """The wx.html2 backend id to ask for, or None for wx's default."""
    wanted = os.environ.get("LCSC_WEBVIEW_BACKEND", "").lower()
    edge = getattr(html2, "WebViewBackendEdge", None)
    ie = getattr(html2, "WebViewBackendIE", None)
    if sys.platform != "win32" or wanted == "default":
        return None
    if wanted == "ie" and ie:
        enable_ie11_emulation()
        return ie
    try:
        edge_ok = bool(edge) and html2.WebView.IsBackendAvailable(edge)
    except Exception:
        edge_ok = False
    if edge_ok and not _edge_broken and (wanted == "edge" or (prefer_edge and webview2_runtime_installed())):
        return edge
    # IE it is (wx's default here), in IE11 mode.
    enable_ie11_emulation()
    return None


def new_webview(parent, prefer_edge: bool = False):
    """A WebView, or None when wx has no usable backend here (the caller
    shows a placeholder). On Windows: IE in IE11 mode, which shows the SVG
    previews; with prefer_edge, Edge when its runtime is installed, for
    pages that need a modern engine (WebGL). The caller of an Edge view
    should watch for its first EVT_WEBVIEW_LOADED and, if it never comes,
    call mark_edge_broken() and rebuild with new_webview(). Elsewhere the
    platform engine. The result has `.is_edge` set."""
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
    view.is_edge = backend is not None and backend == getattr(html2, "WebViewBackendEdge", None)
    return view
