"""
Configuration management for LCSC Manager plugin.

Supports layered overrides:
    hardcoded defaults  <  global  <  project

- Global config:  ~/.kicad/lcsc_manager/config.json
- Project config: <project_dir>/.lcsc_manager.json (sibling of .kicad_pro)

Each level may contain any subset of keys; missing keys fall back to the
next level. A project override is loaded explicitly via
load_project_overrides() once the project path is known.
"""
import json
from pathlib import Path
from typing import Any, Dict, Optional, cast
from .logger import get_logger

logger = get_logger()


PROJECT_CONFIG_FILENAME = ".lcsc_manager.json"

# Keys that participate in the layered resolution. Other keys (e.g.
# api_timeout) live only at global scope.
PATH_KEYS = ("library_path", "symbol_lib_name", "footprint_lib_name", "model_3d_path")


class Config:
    """Plugin configuration manager."""

    DEFAULT_CONFIG = {
        "library_path": "libs/lcsc",
        "symbol_lib_name": "lcsc_imported.kicad_sym",
        "symbol_lib_nickname": "lcsc_imported",
        "footprint_lib_name": "footprints.pretty",
        "footprint_lib_nickname": "lcsc_footprints",
        "model_3d_path": "3dmodels",
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

    # ─── value resolution ────────────────────────────────────────────

    def get(self, key: str, default: Any = None) -> Any:
        """Resolve a key through project → global → DEFAULT_CONFIG → default."""
        if key in self._project:
            return self._project[key]
        if key in self._global:
            return self._global[key]
        if key in self.DEFAULT_CONFIG:
            return self.DEFAULT_CONFIG[key]
        return default

    def get_value_source(self, key: str) -> str:
        """Return 'project' | 'global' | 'default' for the given key."""
        if key in self._project:
            return "project"
        if key in self._global:
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
        if project_path is None:
            return {
                "library_root": None,
                "symbol_lib": None,
                "footprint_lib": None,
                "model_3d_dir": None,
            }

        proj_dir = project_path.parent if project_path.is_file() else project_path
        library_path = values.get("library_path", "libs/lcsc")
        symbol_name = values.get("symbol_lib_name", "lcsc_imported.kicad_sym")
        footprint_name = values.get("footprint_lib_name", "footprints.pretty")
        model_dir = values.get("model_3d_path", "3dmodels")

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

    def get_kiprjmod_uris(self) -> Dict[str, str]:
        """
        Return ${KIPRJMOD}-prefixed URIs used inside KiCad lib tables and
        footprint files. Independent of the project path on disk.
        """
        v = self._effective_values()
        root = v["library_path"]
        return {
            "library_root": f"${{KIPRJMOD}}/{root}",
            "symbol_lib": f"${{KIPRJMOD}}/{root}/symbols/{v['symbol_lib_name']}",
            "footprint_lib": f"${{KIPRJMOD}}/{root}/{v['footprint_lib_name']}",
            "model_3d_dir": f"${{KIPRJMOD}}/{root}/{v['model_3d_path']}",
        }

    def _effective_values(self) -> Dict[str, Any]:
        out = {}
        for k in PATH_KEYS:
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
