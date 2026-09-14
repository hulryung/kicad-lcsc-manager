"""Which KiCad runtime is this code running under?

Kept free of wx/pcbnew imports so it can be used — and unit-tested — before
either is known to be available.
"""
import os


def in_ipc_plugin_process() -> bool:
    """True when KiCad launched this process as an IPC API plugin.

    KiCad runs IPC plugins in a separate Python process and passes each
    launch a KICAD_API_TOKEN (plus KICAD_API_SOCKET to talk back on). pcbnew
    can still be importable there, because the plugin's venv sees KiCad's
    site-packages. But this isn't the pcbnew process: registering a SWIG
    ActionPlugin fails, and pcbnew's global state (board, library tables)
    isn't the user's session (#19).

    Only the token is checked. People who script KiCad from a terminal often
    export KICAD_API_SOCKET, and a KiCad started from such a shell must still
    load the SWIG plugin. A token is per-launch and not something people set.
    """
    return bool(os.environ.get("KICAD_API_TOKEN"))
