"""
Where KiCad's own Python is on this machine, for the tests that run code
under it (wx, pcbnew, the bundled stack on Python 3.9).

Set KICAD_PYTHON to use a particular interpreter. Otherwise the macOS app
bundle is tried, then the newest install under C:\\Program Files\\KiCad
(what the Windows CI job uses). The returned Path may not exist; callers
check `.exists()` and skip.
"""
import glob
import os
import sys
from pathlib import Path


def kicad_python() -> Path:
    override = os.environ.get("KICAD_PYTHON")
    if override:
        return Path(override)
    mac = Path("/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework"
               "/Versions/Current/bin/python3")
    if mac.exists():
        return mac
    if sys.platform == "win32":
        found = sorted(glob.glob(r"C:\Program Files\KiCad\*\bin\python.exe"),
                       key=lambda p: [int(x) if x.isdigit() else x
                                      for x in Path(p).parts[-3].split(".")])
        if found:
            return Path(found[-1])
    return mac


def no_window_restore():
    """Extra argv for a wx process on macOS: without it, a Python.app that
    exited abruptly a few times stops the next launch at a "Reopen
    windows?" prompt that no test run answers."""
    return ["-ApplePersistenceIgnoreState", "YES"] if sys.platform == "darwin" else []
