"""
Configuration management for LCSC Manager plugin
"""
import json
from pathlib import Path
from typing import Any, Dict, Optional
from .logger import get_logger

logger = get_logger()


class Config:
    """Plugin configuration manager"""

    DEFAULT_CONFIG = {
        "library_path": "libs/lcsc",
        "symbol_lib_name": "lcsc_imported.kicad_sym",
        "footprint_lib_name": "footprints.pretty",
        "model_3d_path": "3dmodels",
        "api_timeout": 30,
        "download_timeout": 60,
        "cache_enabled": True,
        "cache_expiry_days": 7,
    }

    def __init__(self, config_path: Optional[Path] = None):
        """
        Initialize configuration

        Args:
            config_path: Path to configuration file. If None, uses default location.
        """
        if config_path is None:
            config_dir = Path.home() / ".kicad" / "lcsc_manager"
            config_dir.mkdir(parents=True, exist_ok=True)
            config_path = config_dir / "config.json"

        self.config_path = config_path
        self._config: Dict[str, Any] = {}
        self.load()

    def load(self) -> None:
        """Load configuration from file"""
        try:
            if self.config_path.exists():
                with open(self.config_path, 'r') as f:
                    self._config = json.load(f)
                logger.info(f"Configuration loaded from {self.config_path}")
            else:
                self._config = self.DEFAULT_CONFIG.copy()
                self.save()
                logger.info("Created new configuration file with defaults")
        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            self._config = self.DEFAULT_CONFIG.copy()

    def save(self) -> None:
        """Save configuration to file"""
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_path, 'w') as f:
                json.dump(self._config, f, indent=2)
            logger.info(f"Configuration saved to {self.config_path}")
        except Exception as e:
            logger.error(f"Failed to save configuration: {e}")

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value

        Args:
            key: Configuration key
            default: Default value if key not found

        Returns:
            Configuration value
        """
        return self._config.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """
        Set configuration value

        Args:
            key: Configuration key
            value: Value to set
        """
        self._config[key] = value
        self.save()

    def get_library_path(self, project_path: Path) -> Path:
        """
        Get library path for a project

        Args:
            project_path: Path to KiCad project

        Returns:
            Path to library directory
        """
        lib_path = project_path.parent / self.get("library_path", "libs/lcsc")
        return lib_path

    def get_symbol_lib_path(self, project_path: Path) -> Path:
        """
        Get symbol library path

        Args:
            project_path: Path to KiCad project

        Returns:
            Path to symbol library file
        """
        lib_path = self.get_library_path(project_path)
        return lib_path / "symbols" / self.get("symbol_lib_name")

    def get_footprint_lib_path(self, project_path: Path) -> Path:
        """
        Get footprint library path

        Args:
            project_path: Path to KiCad project

        Returns:
            Path to footprint library directory
        """
        lib_path = self.get_library_path(project_path)
        return lib_path / self.get("footprint_lib_name")

    def get_3d_model_path(self, project_path: Path) -> Path:
        """
        Get 3D model path

        Args:
            project_path: Path to KiCad project

        Returns:
            Path to 3D models directory
        """
        lib_path = self.get_library_path(project_path)
        return lib_path / self.get("model_3d_path")


# Global configuration instance
_config_instance: Optional[Config] = None


def get_config() -> Config:
    """
    Get global configuration instance

    Returns:
        Configuration instance
    """
    global _config_instance
    if _config_instance is None:
        _config_instance = Config()
    return _config_instance
