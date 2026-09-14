"""
Entry point of the IPC API plugin (#19). KiCad runs this file in the plugin's
own Python environment each time the LCSC Manager button is pressed, with
KICAD_API_SOCKET and KICAD_API_TOKEN set and the plugin folder as the working
directory.

Only the IPC build puts plugin.json next to it (see ipc/README.md). The SWIG
plugin never runs this file.
"""
import importlib.util
import os
import sys
from pathlib import Path
from typing import Optional, Tuple

PACKAGE = "lcsc_manager"
PLUGIN_DIR = Path(__file__).resolve().parent

MISSING_KIPY = (
    "LCSC Manager can't talk to KiCad: the kicad-python package is missing "
    "from its Python environment ({error}).\n\n"
    "KiCad installs it each time it loads the plugin, which needs an internet "
    "connection. Restart KiCad to try again.\n\nLog: {log}"
)
CANT_REACH = (
    "LCSC Manager couldn't reach KiCad ({error}).\n\n"
    "Try again. If it keeps happening, restart KiCad.\n\nLog: {log}"
)
NO_PROJECT = "No project is open. Please open a board or schematic first."
NOT_SAVED = "Please save your project first.\n\n{path} doesn't exist yet."


def load_package(folder: Path = PLUGIN_DIR):
    """Import the plugin folder as the lcsc_manager package.

    The Plugin and Content Manager installs it into a folder named after the
    package identifier (com_github_hulryung_kicad-lcsc-manager), which can't
    be imported by name. The modules only import each other relatively, so
    the package works under any name.
    """
    if PACKAGE in sys.modules:
        return sys.modules[PACKAGE]
    spec = importlib.util.spec_from_file_location(
        PACKAGE, folder / "__init__.py", submodule_search_locations=[str(folder)])
    package = importlib.util.module_from_spec(spec)
    sys.modules[PACKAGE] = package
    try:
        spec.loader.exec_module(package)
    except BaseException:
        del sys.modules[PACKAGE]
        raise
    return package


def redirect_output(path: Path) -> None:
    """Send stdout and stderr to path, down to the file descriptors, so
    output from wx and other C code goes there too.

    KiCad reads a plugin's output only after it exits and shows it as a
    warning in the editor. A plugin that keeps writing blocks once the pipe
    is full, and harmless noise (a Python warning, a GTK message) looks like
    an error.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    for stream in (sys.stdout, sys.stderr):
        if stream is not None:
            stream.flush()
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
    try:
        os.dup2(fd, 1)
        os.dup2(fd, 2)
    finally:
        os.close(fd)
    sys.stdout = open(1, "w", encoding="utf-8", errors="replace", buffering=1, closefd=False)
    sys.stderr = open(2, "w", encoding="utf-8", errors="replace", buffering=1, closefd=False)


def find_project(host) -> Tuple[Optional[Path], str]:
    """The board or project file open in KiCad, or None and what to tell the
    user."""
    from lcsc_manager.utils.logger import log_file

    try:
        project = host.project_file()
    except ImportError as e:
        return None, MISSING_KIPY.format(error=e, log=log_file())
    except Exception as e:      # kipy.errors.ConnectionError, a timeout, ...
        return None, CANT_REACH.format(error=e, log=log_file())
    if project is None:
        return None, NO_PROJECT
    if not project.is_file():
        return None, NOT_SAVED.format(path=project)
    return project, ""


def run(host=None) -> int:
    """Open the LCSC Manager dialog for the project open in KiCad."""
    import wx
    from lcsc_manager.launcher import open_main_dialog, show_error
    from lcsc_manager.utils.kicad_host import IpcHost, set_host
    from lcsc_manager.utils.logger import get_logger

    logger = get_logger()
    app = wx.App(False)
    # Inside KiCad a wx assertion is only logged. A standalone wx.App raises
    # it instead, and a harmless one would keep a dialog from opening.
    app.SetAssertMode(wx.APP_ASSERT_LOG)

    # Explicitly, so a manual run without KICAD_API_TOKEN works the same.
    host = host if host is not None else IpcHost()
    set_host(host)

    project, problem = find_project(host)
    if project is None:
        logger.warning(problem)
        show_error(problem)
        return 0
    logger.info(f"LCSC Manager (IPC) started for {project}")
    open_main_dialog(project)
    return 0


def main() -> int:
    # Running a file puts its folder first on sys.path. Here that's the plugin
    # folder, whose subpackages (api, utils, library, ...) would shadow any
    # top-level modules of the same name.
    if sys.path and Path(sys.path[0] or os.curdir).resolve() == PLUGIN_DIR:
        del sys.path[0]
    load_package()
    try:
        import wx  # noqa: F401
    except ImportError as e:
        # Still on KiCad's pipe, so KiCad shows this in the editor.
        print(f"LCSC Manager needs wxPython, which this Python lacks: {e}",
              file=sys.stderr)
        return 1

    from lcsc_manager.utils.logger import get_logger, log_file, log_to_file_only
    redirect_output(log_file())
    log_to_file_only()
    try:
        return run()
    except Exception as e:
        get_logger().exception("LCSC Manager (IPC) failed")
        from lcsc_manager.launcher import show_error
        show_error(f"Plugin error: {e}\n\nLog: {log_file()}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
