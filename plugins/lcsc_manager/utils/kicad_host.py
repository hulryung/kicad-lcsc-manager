"""
The KiCad the plugin is running under, behind one interface.

LCSC Manager can run in three places:

    SwigHost  inside pcbnew as a SWIG action plugin (KiCad 9/10)
    IpcHost   an IPC API plugin: a separate process KiCad launches (#19)
    NullHost  no KiCad session at all (tests, scripts, a plain Python)

Everything that used to call pcbnew directly asks the host instead: where
KiCad keeps its settings, expanding ${VARS}, whether a footprint library is
loaded, registering one in memory. A successful `import pcbnew` doesn't tell
you which of these you're in. An IPC plugin's venv sees KiCad's
site-packages, and KiCad's bundled Python imports pcbnew standalone too —
both without a KiCad session behind it.

Kept free of wx; pcbnew and kipy are imported lazily, only by the host that
needs them.
"""
import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, Mapping, Optional

from .logger import get_logger
from .runtime import in_ipc_plugin_process

logger = get_logger()

_VAR = re.compile(r"\$\{([^}]+)\}")


def default_user_settings_dir(major: int, minor: int,
                              env: Optional[Mapping[str, str]] = None,
                              platform: Optional[str] = None,
                              home: Optional[Path] = None) -> Path:
    """KiCad's user settings folder (it holds the global library tables and
    kicad_common.json), computed as PATHS::CalculateUserSettingsPath does:
    $KICAD_CONFIG_HOME if set, otherwise the platform's user config folder
    plus "kicad"; then "<major>.<minor>"."""
    env = os.environ if env is None else env
    platform = sys.platform if platform is None else platform
    home = Path.home() if home is None else Path(home)

    override = env.get("KICAD_CONFIG_HOME")
    if override:
        base = Path(override)
    else:
        if platform == "darwin":
            config = home / "Library" / "Preferences"
        elif platform.startswith("win"):
            config = Path(env.get("APPDATA") or home / "AppData" / "Roaming")
        else:
            config = Path(env.get("XDG_CONFIG_HOME") or home / ".config")
        base = config / "kicad"
    return base / f"{major}.{minor}"


def substitute_vars(text: str, variables: Mapping[str, str]) -> str:
    """Replace ${NAME} with variables[NAME]. Unknown names are left as
    ${NAME}, so callers can tell the variable is undefined."""
    return _VAR.sub(lambda m: variables.get(m.group(1), m.group(0)), text)


class KiCadHost:
    """No KiCad session: tests, scripts, a plain Python. Also the base with
    safe defaults for the others."""

    name = "none"
    # A KiCad session is running that may not have loaded what we just wrote.
    session_running = False

    def project_file(self) -> Optional[Path]:
        """The open board or project file, if there is one."""
        return None

    def user_settings_dir(self) -> Optional[Path]:
        """KiCad's user settings folder, if known."""
        return None

    def expand_path_vars(self, text: str) -> str:
        """Expand ${VAR} and ~ in a folder path. Undefined variables stay as
        ${NAME}."""
        return os.path.expanduser(os.path.expandvars(text.strip()))

    def footprint_library_loaded(self, nickname: str) -> Optional[bool]:
        """Whether the running session has loaded a footprint library, or
        None when that can't be told."""
        return None

    def can_register_footprint_library_in_memory(self) -> bool:
        return False

    def register_footprint_library_in_memory(self, nickname: str, uri: str,
                                             table_path: Path) -> bool:
        """Add a project footprint library to the live session and save the
        table. True if added, False if it was already there."""
        raise NotImplementedError(f"{self.name} host can't register libraries in memory")


class NullHost(KiCadHost):
    """No KiCad session."""


class SwigHost(KiCadHost):
    """Inside pcbnew, as a SWIG action plugin (KiCad 9/10)."""

    name = "swig"
    session_running = True

    def __init__(self, pcbnew_module):
        self._pcbnew = pcbnew_module

    def project_file(self) -> Optional[Path]:
        board = self._pcbnew.GetBoard()
        filename = board.GetFileName() if board else ""
        return Path(filename) if filename else None

    def user_settings_dir(self) -> Optional[Path]:
        try:
            return Path(self._pcbnew.SETTINGS_MANAGER.GetUserSettingsPath())
        except Exception as e:
            logger.warning(f"Could not get KiCad settings path: {e}")
            return None

    def expand_path_vars(self, text: str) -> str:
        # Knows the variables from Preferences → Configure Paths as well as
        # the OS environment; neither this nor expandvars expands "~".
        try:
            text = self._pcbnew.ExpandEnvVarSubstitutions(text.strip(), None)
        except Exception:
            text = os.path.expandvars(text.strip())
        return os.path.expanduser(text)

    def footprint_library_loaded(self, nickname: str) -> Optional[bool]:
        if not hasattr(self._pcbnew, "GetFootprintLibraries"):
            return None
        try:
            names = [str(name) for name in self._pcbnew.GetFootprintLibraries()]
        except Exception as e:
            logger.debug(f"GetFootprintLibraries failed: {e}")
            return None
        return nickname in names

    def can_register_footprint_library_in_memory(self) -> bool:
        # KiCad 9 and earlier. KiCad 10 no longer wraps FP_LIB_TABLE or
        # PROJECT for Python, so there the table can only be written to disk.
        return hasattr(self._pcbnew, "FP_LIB_TABLE_ROW")

    def register_footprint_library_in_memory(self, nickname: str, uri: str,
                                             table_path: Path) -> bool:
        board = self._pcbnew.GetBoard()
        if not board:
            raise RuntimeError("No board loaded")
        table = board.GetProject().PcbFootprintLibs()
        if table.HasLibrary(nickname):
            return False
        row = self._pcbnew.FP_LIB_TABLE_ROW(nickname, uri, "KiCad", "")
        row.SetDescr("LCSC imported footprints")
        table.InsertRow(row)
        table.Save(str(table_path))    # persist across sessions
        return True


class IpcHost(KiCadHost):
    """An IPC API plugin process; KiCad is reached over its API socket.

    The IPC API has no command to list, add or reload library-table rows (as
    of KiCad 10.0 and master), so footprint_library_loaded() can't be
    answered and libraries are only ever written to disk.
    """

    name = "ipc"
    session_running = True

    def __init__(self, kicad=None, env: Optional[Mapping[str, str]] = None):
        self._kicad = kicad             # kipy.KiCad; created on first use
        self._env = os.environ if env is None else env
        self._version = None
        self._path_vars: Optional[Dict[str, str]] = None

    def _client(self):
        if self._kicad is None:
            from kipy import KiCad       # installed in the plugin's venv only
            self._kicad = KiCad()
        return self._kicad

    def _open_document(self):
        from kipy.errors import ApiError
        from kipy.proto.common.types import DocumentType
        kicad = self._client()
        for kind in (DocumentType.DOCTYPE_PCB, DocumentType.DOCTYPE_SCHEMATIC):
            try:
                documents = kicad.get_open_documents(kind)
            except ApiError as e:
                # KiCad answers "unhandled" when that editor isn't open.
                # Connection errors are left to the caller.
                logger.debug(f"get_open_documents({kind}) failed: {e}")
                continue
            if documents:
                return documents[0]
        return None

    def project_file(self) -> Optional[Path]:
        """The open board, or the project file when only the Schematic Editor
        is open. Raises if KiCad can't be reached."""
        document = self._open_document()
        if document is None or not document.project.path:
            return None                 # nothing open, or never saved
        project_dir = Path(document.project.path)
        if document.board_filename:
            return project_dir / document.board_filename
        return project_dir / f"{document.project.name}.kicad_pro"

    def kicad_version(self):
        """(major, minor) of the KiCad we're connected to, or None."""
        if self._version is None:
            try:
                version = self._client().get_version()
                self._version = (int(version.major), int(version.minor))
            except Exception as e:
                logger.warning(f"Could not get the KiCad version over IPC: {e}")
        return self._version

    def user_settings_dir(self) -> Optional[Path]:
        # KiCad 11 adds an IPC GetPaths command (PATH_USER_SETTINGS), but
        # kicad-python doesn't expose it yet. Computing it the way KiCad does
        # works on every version, and KiCad passes its own environment
        # (including any KICAD_CONFIG_HOME) to the plugin process.
        version = self.kicad_version()
        return default_user_settings_dir(*version, env=self._env) if version else None

    def _kicad_path_variables(self) -> Dict[str, str]:
        """User path variables from Preferences → Configure Paths, which
        KiCad stores in kicad_common.json. Read once."""
        if self._path_vars is None:
            self._path_vars = {}
            settings = self.user_settings_dir()
            if settings is not None:
                try:
                    data = json.loads((settings / "kicad_common.json").read_text(encoding="utf-8"))
                    self._path_vars = dict((data.get("environment") or {}).get("vars") or {})
                except (OSError, ValueError) as e:
                    logger.debug(f"No KiCad path variables read: {e}")
        return self._path_vars

    def expand_path_vars(self, text: str) -> str:
        # ExpandTextVariables(expand_env_vars=True) only exists from 10.0.7,
        # needs an open document the API accepts, and kicad-python doesn't
        # expose the flag; KiCad's own variables plus the environment cover
        # what a shared folder path uses.
        variables = dict(self._env)
        variables.update(self._kicad_path_variables())
        return os.path.expanduser(substitute_vars(text.strip(), variables))


_host: Optional[KiCadHost] = None


def detect_host() -> KiCadHost:
    """Work out which KiCad this code is running under."""
    if in_ipc_plugin_process():
        return IpcHost()
    try:
        import pcbnew  # noqa: WPS433 — only available with KiCad's Python
    except ImportError:
        return NullHost()
    try:
        board = pcbnew.GetBoard()      # None outside a running pcbnew
    except Exception:
        board = None
    return SwigHost(pcbnew) if board is not None else NullHost()


def get_host() -> KiCadHost:
    """The host for this process. A "no session" answer isn't remembered,
    since pcbnew may not have a board yet the first time this is asked."""
    global _host
    if _host is not None:
        return _host
    host = detect_host()
    if host.session_running:
        _host = host
    return host


def set_host(host: Optional[KiCadHost]) -> None:
    """Use this host from now on (None re-enables detection). For an entry
    point that knows where it runs — the IPC entry point — and for tests."""
    global _host
    _host = host
