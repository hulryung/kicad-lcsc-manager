"""Optional-dependency helpers.

Builds user-facing guidance when an optional/system dependency is missing,
so dialogs and the plugin entry point share one consistent message.
Kept free of wx imports so it can be unit-tested outside KiCad.
"""
import sys


# How to get the wxPython WebView backend per platform. On Linux most distros
# split it out of the main wxPython package (see issues #6 and #14).
WEBVIEW_INSTALL_HINTS = (
    ("Debian/Ubuntu", "sudo apt install python3-wxgtk-webview4.0"),
    ("Fedora", "sudo dnf install python3-wxpython4-webview"),
    ("Arch", "ensure webkit2gtk is installed (python-wxpython bundles WebView)"),
)


def webview_install_hint() -> str:
    """One-line-per-distro instructions for installing the WebView backend."""
    return "\n".join(f"  {distro}: {cmd}" for distro, cmd in WEBVIEW_INSTALL_HINTS)


def is_webview_import_error(exc: BaseException) -> bool:
    """True if the exception looks like the missing wx.html2/WebView backend."""
    text = str(exc)
    return "html2" in text or "webview" in text.lower()


def describe_dialog_import_error(exc: BaseException) -> str:
    """Build the message shown when the advanced search dialog cannot load.

    Names the real exception (instead of guessing) and, when it looks like
    the well-known missing WebView backend, adds per-distro install commands.
    """
    lines = [
        "The full-featured search dialog could not be loaded, so LCSC Manager "
        "is falling back to a basic dialog with reduced functionality.",
        "",
        f"Reason: {exc!r}",
    ]

    if is_webview_import_error(exc):
        lines += [
            "",
            "This usually means the wxPython WebView backend is missing. "
            "To enable the full search dialog, install it and restart KiCad:",
            webview_install_hint(),
        ]
    elif isinstance(exc, ImportError):
        lines += [
            "",
            "A Python package required by the search dialog is missing. "
            "Install it into KiCad's Python environment "
            f"({sys.executable}) and restart KiCad.",
        ]

    lines += [
        "",
        "The basic dialog below still supports importing by LCSC part number.",
    ]
    return "\n".join(lines)
