"""
Configuration management for LCSC Manager plugin.

Supports layered overrides:
    hardcoded defaults  <  global  <  project

- Global config:  ~/.kicad/lcsc_manager/config.json
- Project config: <project_dir>/.lcsc_manager.json (sibling of .kicad_pro)

Each level may contain any subset of keys; missing keys fall back to the
next level. A project override is loaded explicitly via
load_project_overrides() once the project path is known.

Library location:
- "project" (default) — libraries live inside each project at
  <project>/<library_path>, referenced as ${KIPRJMOD}/... and registered in
  the project's own library tables.
- "shared" — one library folder for every project (shared_library_path, an
  absolute path, ~, or a ${VAR} path), registered in KiCad's global library
  tables (issue #20).
"""
import json
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Dict, List, Optional, cast
from .logger import get_logger

logger = get_logger()


PROJECT_CONFIG_FILENAME = ".lcsc_manager.json"

# Keys that participate in the layered resolution. Other keys (e.g.
# api_timeout) live only at global scope.
PATH_KEYS = ("library_path", "symbol_lib_name", "footprint_lib_name", "model_3d_path")

LOCATION_PROJECT = "project"
LOCATION_SHARED = "shared"

# Keys resolved through default < global < project. library_location can be
# overridden per project (e.g. a team repo that commits its own libraries
# while personal projects use the shared folder).
LAYERED_KEYS = PATH_KEYS + ("library_location",)

# A folder on *this* computer: never stored in a project file, which may be
# committed and opened on another machine.
GLOBAL_ONLY_KEYS = ("shared_library_path",)


def _is_absolute_on_any_os(raw: str) -> bool:
    """True for anything that is not a plain relative path on *some* OS.

    Checking only for a leading "/" (as the Settings dialog used to) let a
    Windows drive path such as "C:\\libs" through, which then produced a
    broken "${KIPRJMOD}/C:\\libs/..." library-table URI (issue #20).
    """
    if raw.startswith(("/", "\\", "~")):
        return True
    win = PureWindowsPath(raw)
    return bool(win.drive) or win.is_absolute() or PurePosixPath(raw).is_absolute()


def validate_path_value(key: str, raw: str) -> Optional[str]:
    """Return an error message for a Settings field value, or None if valid.

    Every path value is relative to the project folder, so it must not be
    empty, absolute, or climb out with "..". Both separators are honoured,
    since a project may be opened on Windows and macOS/Linux alike.
    """
    if not raw:
        return "must not be empty."
    if _is_absolute_on_any_os(raw):
        return ("must be a project-relative path "
                "(no drive letter, leading / or \\, or ~).")
    if ".." in PureWindowsPath(raw).parts:  # splits on both / and \\
        return "must not contain '..'."
    return None


def expand_path_vars(raw: str) -> str:
    """Expand ${VAR} and ~ in a user-entered folder path.

    Inside KiCad, pcbnew.ExpandEnvVarSubstitutions knows the path variables
    from Preferences → Configure Paths as well as the OS environment; outside
    it (tests), only the OS environment is available. Undefined variables are
    left as "${NAME}" so callers can detect them. Neither expands "~".
    """
    expanded = raw.strip()
    try:
        import pcbnew  # noqa: WPS433 — only available inside KiCad
        expanded = pcbnew.ExpandEnvVarSubstitutions(expanded, None)
    except Exception:
        expanded = os.path.expandvars(expanded)
    return os.path.expanduser(expanded)


def validate_shared_path(raw: str) -> Optional[str]:
    """Return an error message for the shared library folder, or None."""
    raw = raw.strip()
    if not raw:
        return "choose a folder for the shared library."
    expanded = expand_path_vars(raw)
    if "${" in expanded:
        name = expanded.split("${", 1)[1].split("}", 1)[0]
        return (f"uses ${{{name}}}, which KiCad doesn't define. Add it under "
                "Preferences → Configure Paths, or enter a full path.")
    # Absolute on *this* OS: a Windows drive path typed on macOS/Linux would
    # otherwise be taken as relative to KiCad's working directory.
    if not os.path.isabs(expanded):
        example = "C:\\KiCadLibs\\lcsc" if os.name == "nt" else "~/KiCad/lcsc"
        return f"must be a full path on this computer, such as {example}."
    return None


def shared_uri_root(raw: str) -> str:
    """How the shared folder is written into library tables and footprints.

    ${VAR} is kept, so the tables stay valid if the folder moves or the
    project is opened on another machine with the variable set. "~" is
    expanded because KiCad doesn't expand it. Separators become "/", which
    KiCad accepts on every OS.
    """
    root = raw.strip()
    if root.startswith("~"):
        root = os.path.expanduser(root)
    return root.replace("\\", "/").rstrip("/")


class Config:
    """Plugin configuration manager."""

    DEFAULT_CONFIG = {
        "library_path": "libs/lcsc",
        "symbol_lib_name": "lcsc_imported.kicad_sym",
        "symbol_lib_nickname": "lcsc_imported",
        "footprint_lib_name": "footprints.pretty",
        "footprint_lib_nickname": "lcsc_footprints",
        "model_3d_path": "3dmodels",
        "library_location": LOCATION_PROJECT,
        "shared_library_path": "",
        # Distinct from the per-project nicknames, so a project that still
        # has its own lcsc_imported / lcsc_footprints entries can't shadow
        # the shared ones (project tables win over global on a name clash).
        "shared_symbol_lib_nickname": "lcsc_shared",
        "shared_footprint_lib_nickname": "lcsc_shared_footprints",
        "api_timeout": 30,
        "download_timeout": 60,
        "cache_enabled": True,
        "cache_expiry_days": 7,
    }

    def __init__(self, config_path: Optional[Path] = None):
        if config_path is None:
            config_dir = Path.home() / ".kicad" / "lcsc_manager"
            config_dir.mkdir(parents=True, exist_ok=True)
            config_path = config_dir / "config.json"

        self.config_path = config_path
        self._global: Dict[str, Any] = {}
        self._project: Dict[str, Any] = {}
        self._project_path: Optional[Path] = None
        self.load()

    # ─── load / save ──────────────────────────────────────────────────

    def load(self) -> None:
        """Load global configuration from file.

        Note: Global stores *only user overrides*. Missing keys fall back
        to DEFAULT_CONFIG at lookup time. We deliberately do NOT seed the
        file with defaults — that would make every key look like a user
        override in the Settings UI.
        """
        try:
            if self.config_path.exists():
                with open(self.config_path, 'r') as f:
                    self._global = json.load(f)
                logger.info(f"Configuration loaded from {self.config_path}")
            else:
                self._global = {}
                self.save()
                logger.info(f"Created empty configuration file at {self.config_path}")
        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            self._global = {}

    def save(self) -> None:
        """Save global configuration to file."""
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_path, 'w') as f:
                json.dump(self._global, f, indent=2)
            logger.info(f"Configuration saved to {self.config_path}")
        except Exception as e:
            logger.error(f"Failed to save configuration: {e}")

    def load_project_overrides(self, project_path: Optional[Path]) -> None:
        """
        Load project-scope overrides from <project_dir>/.lcsc_manager.json.

        Args:
            project_path: Path to the .kicad_pro file (or its parent).
                          Pass None to clear any current project overrides.
        """
        if project_path is None:
            self._project = {}
            self._project_path = None
            return

        proj_dir = project_path.parent if project_path.is_file() else project_path
        self._project_path = proj_dir
        override_file = proj_dir / PROJECT_CONFIG_FILENAME

        if not override_file.exists():
            self._project = {}
            return

        try:
            with open(override_file, 'r') as f:
                self._project = json.load(f)
            logger.info(f"Project overrides loaded from {override_file}")
        except Exception as e:
            logger.error(f"Failed to load project overrides: {e}")
            self._project = {}

    def save_scope(self, scope: str, values: Dict[str, Any],
                   project_path: Optional[Path] = None) -> None:
        """
        Save values to the given scope.

        Args:
            scope: "global" or "project"
            values: dict of key→value to merge into that scope (full replace
                    of the scope file with these values)
            project_path: required when scope == "project"
        """
        if scope == "global":
            self._global.update(values)
            self.save()
        elif scope == "project":
            if project_path is None:
                project_path = self._project_path
            if project_path is None:
                raise ValueError("project_path required to save project scope")
            proj_dir = project_path.parent if project_path.is_file() else project_path
            override_file = proj_dir / PROJECT_CONFIG_FILENAME
            self._project = dict(values)
            try:
                with open(override_file, 'w') as f:
                    json.dump(self._project, f, indent=2)
                logger.info(f"Project overrides saved to {override_file}")
            except Exception as e:
                logger.error(f"Failed to save project overrides: {e}")
                raise
        else:
            raise ValueError(f"Unknown scope: {scope}")

    def clear_scope(self, scope: str, project_path: Optional[Path] = None) -> None:
        """Reset a scope. Both scopes become empty so resolution falls
        back to lower layers (Global→Default for Project, Default for
        Global). The project file is removed; the global file is rewritten
        as empty JSON."""
        if scope == "global":
            self._global = {}
            self.save()
        elif scope == "project":
            if project_path is None:
                project_path = self._project_path
            if project_path is None:
                raise ValueError("project_path required to clear project scope")
            proj_dir = project_path.parent if project_path.is_file() else project_path
            override_file = proj_dir / PROJECT_CONFIG_FILENAME
            self._project = {}
            if override_file.exists():
                try:
                    override_file.unlink()
                    logger.info(f"Project overrides removed: {override_file}")
                except Exception as e:
                    logger.error(f"Failed to remove project overrides: {e}")
        else:
            raise ValueError(f"Unknown scope: {scope}")

    def save_global_settings(self, values: Dict[str, Any]) -> None:
        """Save Settings-dialog values at global scope, storing only what
        differs from the built-in defaults. A value typed back to its default
        is removed, so it keeps tracking future default changes and the scope
        summary stays honest ("default" rather than "global")."""
        for key, value in values.items():
            if str(value) == str(self.DEFAULT_CONFIG.get(key)):
                self._global.pop(key, None)
            else:
                self._global[key] = value
        self.save()

    def save_project_settings(self, values: Dict[str, Any],
                              project_path: Optional[Path] = None) -> Dict[str, Any]:
        """Save Settings-dialog values at project scope, storing only what
        differs from the value the project would inherit (Global, else
        Default).

        Writing every field — inherited ones included — used to pin the whole
        layout to the project, so any later Global change silently had no
        effect on it (issue #20). Keys left equal to the inherited value keep
        following Global. Non-path keys already in the project file are kept.
        If nothing is left to store, the project file is removed.

        Returns the path values that were stored.
        """
        diff = {}
        for key, value in values.items():
            if key in GLOBAL_ONLY_KEYS:
                continue
            inherited, _source = self.resolve_for_scope_view(key, "global")
            if str(value) != str(inherited):
                diff[key] = value

        stored = {k: v for k, v in self._project.items()
                  if k not in LAYERED_KEYS and k not in GLOBAL_ONLY_KEYS}
        stored.update(diff)
        if stored:
            self.save_scope("project", stored, project_path)
        else:
            self.clear_scope("project", project_path)
        return diff

    def project_override_keys(self) -> List[str]:
        """Layered keys the open project overrides — i.e. keys on which
        Global settings have no effect for this project."""
        return [k for k in LAYERED_KEYS if k in self._project]

    def default_edit_scope(self, project_open: bool) -> str:
        """Scope the Settings dialog should open in: the one that actually
        supplies the effective settings.

        The dialog used to open on "This project only" whenever a project was
        open, whatever had been saved. After saving at Global, reopening
        showed the project view — so the save looked lost (issue #20) — and
        the next Save then wrote a project override that shadowed Global.
        """
        if project_open and self.get_active_scope_summary() in ("project", "mixed"):
            return "project"
        return "global"

    # ─── value resolution ────────────────────────────────────────────

    def get(self, key: str, default: Any = None) -> Any:
        """Resolve a key through project → global → DEFAULT_CONFIG → default.
        Global-only keys skip the project layer, even in a hand-edited file."""
        if key in self._project and key not in GLOBAL_ONLY_KEYS:
            return self._project[key]
        if key in self._global:
            return self._global[key]
        if key in self.DEFAULT_CONFIG:
            return self.DEFAULT_CONFIG[key]
        return default

    def get_value_source(self, key: str) -> str:
        """Return 'project' | 'global' | 'default' for the given key."""
        if key in self._project and key not in GLOBAL_ONLY_KEYS:
            return "project"
        if key in self._global:
            return "global"
        return "default"

    def get_active_scope_summary(self) -> str:
        """
        Summarise where the effective path-config comes from across all
        PATH_KEYS. Returns one of:

            "project" — every path key is overridden at project scope
            "global"  — every path key is overridden at global scope
                        (and none at project)
            "default" — no overrides anywhere; pure defaults
            "mixed"   — at least one project override AND at least one
                        key still inherited from a lower layer (global
                        or default)

        Useful for one-line UI hints like "Saving with project settings".
        """
        sources = {self.get_value_source(k) for k in PATH_KEYS}
        # library_location counts only when someone actually set it — an
        # unset location is the default, not a customisation.
        location_source = self.get_value_source("library_location")
        if location_source != "default":
            sources.add(location_source)
        if sources == {"project"}:
            return "project"
        if "project" in sources:
            return "mixed"
        if "global" in sources:
            return "global"
        return "default"

    def resolve_for_scope_view(self, key: str, scope: str) -> tuple:
        """
        What to display when editing `scope`. Returns (value, source).

        Global view sees only Global and Default layers — never falls back
        to Project. Project view sees the full Project → Global → Default
        chain (i.e., the runtime-effective value).
        """
        if scope == "project":
            if key in self._project:
                return self._project[key], "project"
            if key in self._global:
                return self._global[key], "global"
            return self.DEFAULT_CONFIG.get(key), "default"
        if scope == "global":
            if key in self._global:
                return self._global[key], "global"
            return self.DEFAULT_CONFIG.get(key), "default"
        raise ValueError(f"Unknown scope: {scope}")

    def set(self, key: str, value: Any) -> None:
        """Legacy: set a value in global scope and persist."""
        self._global[key] = value
        self.save()

    def get_scope_values(self, scope: str) -> Dict[str, Any]:
        """Return raw values stored in the given scope (no merging)."""
        if scope == "global":
            return dict(self._global)
        if scope == "project":
            return dict(self._project)
        if scope == "default":
            return dict(self.DEFAULT_CONFIG)
        raise ValueError(f"Unknown scope: {scope}")

    # ─── path helpers ────────────────────────────────────────────────

    @staticmethod
    def resolve_paths(values: Dict[str, Any],
                      project_path: Optional[Path]) -> Dict[str, Optional[Path]]:
        """
        Compute resolved filesystem paths from a values dict.

        Returns a dict with keys 'library_root', 'symbol_lib', 'footprint_lib',
        'model_3d_dir'. Values are absolute Paths when project_path is given,
        else None (caller should display the template form instead).
        """
        symbol_name = values.get("symbol_lib_name", "lcsc_imported.kicad_sym")
        footprint_name = values.get("footprint_lib_name", "footprints.pretty")
        model_dir = values.get("model_3d_path", "3dmodels")

        if values.get("library_location") == LOCATION_SHARED:
            # One folder for every project, so no project is needed. Left
            # unresolved if the folder is unset or uses an unknown ${VAR}.
            raw = values.get("shared_library_path") or ""
            if validate_shared_path(raw) is not None:
                return {"library_root": None, "symbol_lib": None,
                        "footprint_lib": None, "model_3d_dir": None}
            library_root = Path(expand_path_vars(raw)).resolve()
        else:
            if project_path is None:
                return {"library_root": None, "symbol_lib": None,
                        "footprint_lib": None, "model_3d_dir": None}
            proj_dir = project_path.parent if project_path.is_file() else project_path
            library_path = values.get("library_path", "libs/lcsc")
            library_root = (proj_dir / library_path).resolve()
        return {
            "library_root": library_root,
            "symbol_lib": library_root / "symbols" / symbol_name,
            "footprint_lib": library_root / footprint_name,
            "model_3d_dir": library_root / model_dir,
        }

    def get_library_path(self, project_path: Path) -> Path:
        return cast(Path, self.resolve_paths(self._effective_values(), project_path)["library_root"])

    def get_symbol_lib_path(self, project_path: Path) -> Path:
        return cast(Path, self.resolve_paths(self._effective_values(), project_path)["symbol_lib"])

    def get_footprint_lib_path(self, project_path: Path) -> Path:
        return cast(Path, self.resolve_paths(self._effective_values(), project_path)["footprint_lib"])

    def get_3d_model_path(self, project_path: Path) -> Path:
        return cast(Path, self.resolve_paths(self._effective_values(), project_path)["model_3d_dir"])

    def is_shared_library(self) -> bool:
        """True when imports go to the shared folder instead of the project."""
        return self.get("library_location") == LOCATION_SHARED

    def describe_destination(self, project_path: Optional[Path]) -> str:
        """One line for the dialogs' "saving to" label."""
        root = self.get_library_path(project_path) if (
            project_path is not None or self.is_shared_library()) else None
        if self.is_shared_library():
            if root is None:
                return ("shared folder not set, or it uses a path variable "
                        "KiCad doesn't define — see ⚙ Settings")
            return f"{root}   (shared folder, used by every project)"
        return str(root)

    def get_library_nicknames(self) -> Dict[str, str]:
        """Library-table nicknames for the effective location."""
        if self.is_shared_library():
            return {"symbol": self.get("shared_symbol_lib_nickname"),
                    "footprint": self.get("shared_footprint_lib_nickname")}
        return {"symbol": self.get("symbol_lib_nickname"),
                "footprint": self.get("footprint_lib_nickname")}

    def get_library_uris(self) -> Dict[str, str]:
        """
        URIs written into KiCad library tables and footprint 3D references.
        Independent of where the project sits on disk:

        - project location: ${KIPRJMOD}/<library_path>/...
        - shared location:  the shared folder as entered, ${VAR} kept and
                            ~ expanded (see shared_uri_root)
        """
        v = self._effective_values()
        if v.get("library_location") == LOCATION_SHARED:
            root = shared_uri_root(v.get("shared_library_path") or "")
        else:
            root = f"${{KIPRJMOD}}/{v['library_path']}"
        return {
            "library_root": root,
            "symbol_lib": f"{root}/symbols/{v['symbol_lib_name']}",
            "footprint_lib": f"{root}/{v['footprint_lib_name']}",
            "model_3d_dir": f"{root}/{v['model_3d_path']}",
        }

    def get_kiprjmod_uris(self) -> Dict[str, str]:
        """Backward-compatible name for get_library_uris(). The URIs are only
        ${KIPRJMOD}-relative in the project location."""
        return self.get_library_uris()

    def _effective_values(self) -> Dict[str, Any]:
        out = {}
        for k in LAYERED_KEYS + GLOBAL_ONLY_KEYS:
            out[k] = self.get(k)
        return out


# Global configuration instance
_config_instance: Optional[Config] = None


def get_config() -> Config:
    global _config_instance
    if _config_instance is None:
        _config_instance = Config()
    return _config_instance


def reset_config_for_tests() -> None:
    """Test-only: clear the module-level singleton."""
    global _config_instance
    _config_instance = None
