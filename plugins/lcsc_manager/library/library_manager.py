"""
Library Manager - Manage KiCad project libraries

This module handles adding components to KiCad project libraries
and managing library configuration
"""
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path
import re
from ..utils.logger import get_logger
from ..utils.config import get_config
from ..converters.symbol_converter import SymbolConverter
from ..converters.footprint_converter import FootprintConverter
from ..converters.model_3d_converter import Model3DConverter
from .lib_table import (ensure_lib_entry, LibTableError, ADDED, UPDATED,
                        CONFLICT)
from ..utils.kicad_host import KiCadHost, get_host

logger = get_logger()


class LibraryManager:
    """Manage KiCad project libraries"""

    def __init__(self, project_path: Path,
                 kicad_config_dir: Optional[Path] = None,
                 host: Optional[KiCadHost] = None):
        """
        Initialize library manager

        Args:
            project_path: Path to KiCad project file
            kicad_config_dir: KiCad's user settings folder (holds the global
                library tables). Looked up from KiCad when omitted; tests
                pass a temporary folder.
            host: the KiCad this runs under (utils/kicad_host.py). Detected
                when omitted; tests pass a stand-in.
        """
        self.project_path = project_path
        self._kicad_config_dir = kicad_config_dir
        self.host = host if host is not None else get_host()
        # Set while updating library tables when KiCad's running session
        # won't see a library until the project is reopened / KiCad restarts.
        self._restart_pending = False
        self.config = get_config()
        self.logger = get_logger("library_manager")

        # Load any project-scope config overrides before computing paths
        self.config.load_project_overrides(project_path)

        # Get library paths
        self.lib_base_path = self.config.get_library_path(project_path)
        self.symbol_lib_path = self.config.get_symbol_lib_path(project_path)
        self.footprint_lib_path = self.config.get_footprint_lib_path(project_path)
        self.model_3d_path = self.config.get_3d_model_path(project_path)

        # Initialize converters. FootprintConverter needs the 3D-model URI
        # base so the generated .kicad_mod references stay in sync with
        # whatever library path the user configured.
        self.symbol_converter = SymbolConverter()
        self.footprint_converter = FootprintConverter(
            model_uri_base=self.config.get_library_uris()["model_3d_dir"]
        )
        self.model_3d_converter = Model3DConverter()

    def import_component(
        self,
        easyeda_data: Dict[str, Any],
        component_info: Dict[str, Any],
        import_symbol: bool = True,
        import_footprint: bool = True,
        import_3d: bool = True
    ) -> Dict[str, Any]:
        """
        Import component to project libraries

        Args:
            easyeda_data: Raw EasyEDA component data
            component_info: Component metadata
            import_symbol: Whether to import symbol
            import_footprint: Whether to import footprint
            import_3d: Whether to import 3D model

        Returns:
            Dictionary with import results

        Raises:
            Exception: If import fails
        """
        self.logger.info(f"Importing component: {component_info.get('lcsc_id')}")

        if self.lib_base_path is None:
            # Only reachable with a shared location whose folder is unset or
            # uses a ${VAR} KiCad doesn't define (the Settings dialog refuses
            # to save that, but the variable can disappear later).
            raise RuntimeError(
                "The shared library folder isn't set, or uses a path variable "
                "KiCad doesn't define. Fix it under ⚙ Settings.")

        # Find footprint library nickname from project's fp-lib-table
        footprint_lib_nickname = self._get_footprint_lib_nickname()
        component_info["footprint_lib_nickname"] = footprint_lib_nickname
        self.logger.debug(f"Using footprint library nickname: {footprint_lib_nickname}")

        results = {
            "symbol": None,
            "footprint": None,
            "model_3d": None,
            "success": False,
            "errors": []
        }

        try:
            # Import symbol
            if import_symbol:
                try:
                    symbol_result = self._import_symbol(easyeda_data, component_info)
                    results["symbol"] = symbol_result
                    self.logger.info(f"Symbol imported: {symbol_result}")
                except Exception as e:
                    error_msg = f"Symbol import failed: {e}"
                    self.logger.error(error_msg)
                    results["errors"].append(error_msg)

            # Import footprint
            if import_footprint:
                try:
                    footprint_result = self._import_footprint(easyeda_data, component_info)
                    results["footprint"] = footprint_result
                    self.logger.info(f"Footprint imported: {footprint_result}")
                except Exception as e:
                    error_msg = f"Footprint import failed: {e}"
                    self.logger.error(error_msg)
                    results["errors"].append(error_msg)

            # Import 3D model
            if import_3d:
                try:
                    model_result = self._import_3d_model(easyeda_data, component_info)
                    results["model_3d"] = model_result
                    self.logger.info(f"3D model imported: {model_result}")
                except Exception as e:
                    error_msg = f"3D model import failed: {e}"
                    self.logger.error(error_msg)
                    results["errors"].append(error_msg)

            # Update library tables
            notifications = self._update_library_tables()
            results["notifications"] = notifications
            # Tells the dialogs a reopen/restart notice is already in
            # `notifications`, so the generic "reopen the schematic editor"
            # hint would only repeat it.
            results["restart_required"] = self._restart_pending

            results["success"] = (
                (not import_symbol or results["symbol"] is not None) and
                (not import_footprint or results["footprint"] is not None) and
                (not import_3d or results["model_3d"] is not None)
            )

            return results

        except Exception as e:
            self.logger.error(f"Component import failed: {e}", exc_info=True)
            results["errors"].append(str(e))
            raise

    def _import_symbol(
        self,
        easyeda_data: Dict[str, Any],
        component_info: Dict[str, Any]
    ) -> str:
        """
        Import symbol to library

        Args:
            easyeda_data: EasyEDA component data
            component_info: Component metadata

        Returns:
            Symbol name

        Raises:
            Exception: If import fails
        """
        self.logger.info("Importing symbol")

        # Convert symbol
        symbol_content = self.symbol_converter.convert(easyeda_data, component_info)

        # Save to library
        self.symbol_converter.save_to_library(
            symbol_content=symbol_content,
            library_path=self.symbol_lib_path,
            append=True
        )

        symbol_name = self.symbol_converter._get_symbol_name(component_info)
        return symbol_name

    def _import_footprint(
        self,
        easyeda_data: Dict[str, Any],
        component_info: Dict[str, Any]
    ) -> str:
        """
        Import footprint to library

        Args:
            easyeda_data: EasyEDA component data
            component_info: Component metadata

        Returns:
            Footprint name

        Raises:
            Exception: If import fails
        """
        self.logger.info("Importing footprint")

        # Convert footprint
        footprint_content = self.footprint_converter.convert(easyeda_data, component_info)
        footprint_name = self.footprint_converter._get_footprint_name(component_info)

        # Save to library
        self.footprint_converter.save_to_library(
            footprint_content=footprint_content,
            footprint_name=footprint_name,
            library_path=self.footprint_lib_path
        )

        return footprint_name

    def _import_3d_model(
        self,
        easyeda_data: Dict[str, Any],
        component_info: Dict[str, Any]
    ) -> Dict[str, Path]:
        """
        Import 3D models to library

        Args:
            easyeda_data: EasyEDA component data
            component_info: Component metadata

        Returns:
            Dictionary mapping format to file path

        Raises:
            Exception: If import fails
        """
        self.logger.info("Importing 3D model")

        # Download and process models
        models = self.model_3d_converter.process_component_model(
            easyeda_data=easyeda_data,
            component_info=component_info,
            output_dir=self.model_3d_path
        )

        # If no models available, create placeholder
        if not models:
            lcsc_id = component_info.get("lcsc_id", "unknown")
            package = component_info.get("package", "Unknown")

            placeholder_path = self.model_3d_path / f"{lcsc_id}.wrl"
            success = self.model_3d_converter.create_placeholder_model(
                output_path=placeholder_path,
                package_name=package
            )

            if success:
                models["wrl"] = placeholder_path

        return models

    def _update_library_tables(self) -> List[str]:
        """
        Update KiCad library tables to include imported libraries

        This ensures KiCad can find the imported components.
        Uses pcbnew API for footprint library (in-memory update),
        and file-based approach for symbol library.

        Returns:
            List of user notification messages (e.g., reload instructions)
        """
        self.logger.info("Updating library tables")
        self._restart_pending = False
        if self.config.is_shared_library():
            return self._register_shared_libraries()

        notifications = []

        try:
            # Update symbol library table (file-based, eeschema manages this)
            sym_notif = self._update_symbol_lib_table()
            if sym_notif:
                notifications.append(sym_notif)

            # Update footprint library table (try pcbnew API first)
            fp_notif = self._update_footprint_lib_table()
            if fp_notif:
                notifications.append(fp_notif)

        except Exception as e:
            self.logger.error(f"Failed to update library tables: {e}")
            notifications.append(
                "Failed to update library tables. "
                "Please add libraries manually via Preferences > Manage Libraries."
            )

        return notifications

    def kicad_config_dir(self) -> Optional[Path]:
        """KiCad's user settings folder, where the global library tables live."""
        if self._kicad_config_dir is not None:
            return self._kicad_config_dir
        return self.host.user_settings_dir()

    def _register_shared_libraries(self) -> List[str]:
        """Register the shared library in KiCad's global library tables, so
        every project can use it (issue #20).

        KiCad reads the global tables at startup, so a newly registered
        library shows up after a restart. Registration runs on every import
        and is idempotent: if KiCad later rewrites its global table from
        memory without our row, the next import puts it back.
        """
        nicknames = self.config.get_library_nicknames()
        uris = self.config.get_library_uris()
        config_dir = self.kicad_config_dir()
        if config_dir is None:
            return [
                "Couldn't locate KiCad's global library tables. Add the shared "
                "library under Preferences → Manage Symbol/Footprint Libraries "
                f"(Global tab): {nicknames['symbol']} → {uris['symbol_lib']}, "
                f"{nicknames['footprint']} → {uris['footprint_lib']}."
            ]

        notifications = []
        changed = False
        for kind, table, nickname, uri, descr, editor in (
            ("sym", "sym-lib-table", nicknames["symbol"], uris["symbol_lib"],
             "shared symbols", "Symbol"),
            ("fp", "fp-lib-table", nicknames["footprint"], uris["footprint_lib"],
             "shared footprints", "Footprint"),
        ):
            try:
                outcome = ensure_lib_entry(config_dir / table, kind, nickname,
                                           uri, descr)
            except (LibTableError, OSError) as e:
                self.logger.error(f"Could not update global {table}: {e}")
                notifications.append(
                    f"Couldn't update KiCad's global {table} ({e}). Add it under "
                    f"Preferences → Manage {editor} Libraries (Global tab): "
                    f"{nickname} → {uri}.")
                continue
            self.logger.info(f"Global {table}: {nickname} {outcome}")
            if outcome in (ADDED, UPDATED):
                changed = True
            elif outcome == CONFLICT:
                notifications.append(
                    f"KiCad's global {editor.lower()} library table already has "
                    f'a library named "{nickname}" that LCSC Manager didn\'t '
                    "create, so it was left alone. Rename that library, or add "
                    f"the shared one yourself: {uri}.")

        if changed:
            self._restart_pending = True
            notifications.append(
                "The shared LCSC library is now registered in KiCad's global "
                "library tables. Restart KiCad for it to appear in every project.")
        return notifications

    def _update_symbol_lib_table(self) -> Optional[str]:
        """
        Update sym-lib-table file.

        Since this plugin runs in pcbnew, we cannot update the symbol library
        table in eeschema's memory. We write to disk and notify the user
        to reload libraries in the schematic editor.

        Returns:
            Notification message if user action is needed, None otherwise
        """
        lib_table_path = self.project_path.parent / "sym-lib-table"

        lib_name = self.config.get("symbol_lib_nickname")
        lib_path = self.config.get_kiprjmod_uris()["symbol_lib"]

        try:
            # Check if library table exists
            if lib_table_path.exists():
                with open(lib_table_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                # Check if our library is already registered
                if lib_name in content:
                    self.logger.info("Symbol library already registered")
                    return None

                # Add library entry before closing parenthesis
                content = content.rstrip().rstrip(')')

                entry = f'''  (lib (name "{lib_name}")(type "KiCad")(uri "{lib_path}")(options "")(descr "LCSC imported components"))
)
'''
                content = content + '\n' + entry

            else:
                # Create new library table with version tag
                content = f'''(sym_lib_table
  (version 7)
  (lib (name "{lib_name}")(type "KiCad")(uri "{lib_path}")(options "")(descr "LCSC imported components"))
)
'''

            # Write library table
            with open(lib_table_path, 'w', encoding='utf-8') as f:
                f.write(content)

            self.logger.info(f"Symbol library table updated: {lib_table_path}")
            return None

        except Exception as e:
            self.logger.error(f"Failed to update symbol library table: {e}")
            return f"Failed to register symbol library: {e}"

    def _update_footprint_lib_table(self) -> Optional[str]:
        """
        Register the project's footprint library: in the live session where
        KiCad allows it, otherwise in fp-lib-table on disk.

        Returns:
            Notification message if user action is needed, None otherwise
        """
        lib_name = self.config.get("footprint_lib_nickname")
        lib_uri = self.config.get_kiprjmod_uris()["footprint_lib"]
        table_path = self.project_path.parent / "fp-lib-table"

        # KiCad 9's pcbnew can add the row to the live session, so the
        # footprints can be placed straight away.
        if self.host.can_register_footprint_library_in_memory():
            try:
                added = self.host.register_footprint_library_in_memory(
                    lib_name, lib_uri, table_path)
                self.logger.info("Footprint library registered in memory"
                                 if added else
                                 "Footprint library already registered in memory")
                return None
            except Exception as e:
                self.logger.warning(f"In-memory registration failed, falling back to file: {e}")

        # File-based: the only route on KiCad 10 and over IPC.
        notice, added = self._update_footprint_lib_table_file(lib_name, lib_uri)
        # Only worth saying when there are footprints to place: KiCad 10
        # leaves a library whose folder doesn't exist out of its list even
        # after the project is reopened (e.g. a symbol-only import).
        if (notice is None and self.footprint_lib_path.exists()
                and self._reload_needed(lib_name, added)):
            # Written to disk, but the session read the project's tables when
            # the project opened and can't be made to reread them, so the
            # footprints can't be placed yet. Verified on KiCad 10.0.6:
            # invisible until the project is reopened, then listed.
            self._restart_pending = True
            return ("This KiCad session hasn't loaded the LCSC footprint "
                    "library yet. Reopen this project (or restart KiCad) to "
                    "place the imported footprints.")
        return notice

    def _reload_needed(self, nickname: str, just_added: bool) -> bool:
        """Whether the running KiCad session still has to load a footprint
        library registered on disk.

        pcbnew can say what it has loaded. Over IPC that can't be asked, so a
        row added just now counts as not loaded: it wasn't in the table when
        the project opened. With no KiCad session there's nothing to reload.
        """
        loaded = self.host.footprint_library_loaded(nickname)
        if loaded is None:
            needed = self.host.session_running and just_added
        else:
            needed = not loaded
        self.logger.info(f"Footprint library {nickname} ({self.host.name} host): "
                         f"loaded={loaded}, just added={just_added}, "
                         f"reload notice={needed}")
        return needed

    def _update_footprint_lib_table_file(self, lib_name: str,
                                         lib_uri: str) -> Tuple[Optional[str], bool]:
        """
        Update fp-lib-table file directly.

        Returns:
            (notification message if user action is needed, else None;
             whether the row was added just now)
        """
        lib_table_path = self.project_path.parent / "fp-lib-table"

        try:
            if lib_table_path.exists():
                with open(lib_table_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                if lib_name in content:
                    self.logger.info("Footprint library already registered")
                    return None, False

                content = content.rstrip().rstrip(')')

                entry = f'''  (lib (name "{lib_name}")(type "KiCad")(uri "{lib_uri}")(options "")(descr "LCSC imported footprints"))
)
'''
                content = content + '\n' + entry

            else:
                content = f'''(fp_lib_table
  (version 7)
  (lib (name "{lib_name}")(type "KiCad")(uri "{lib_uri}")(options "")(descr "LCSC imported footprints"))
)
'''

            with open(lib_table_path, 'w', encoding='utf-8') as f:
                f.write(content)

            self.logger.info(f"Footprint library table file updated: {lib_table_path}")
            return None, True

        except Exception as e:
            self.logger.error(f"Failed to update footprint library table: {e}")
            return f"Failed to register footprint library: {e}", False

    def get_library_info(self) -> Dict[str, Any]:
        """
        Get information about project libraries

        Returns:
            Dictionary with library paths and status
        """
        return {
            "base_path": str(self.lib_base_path),
            "symbol_lib": str(self.symbol_lib_path),
            "footprint_lib": str(self.footprint_lib_path),
            "model_3d_path": str(self.model_3d_path),
            "symbol_lib_exists": self.symbol_lib_path.exists(),
            "footprint_lib_exists": self.footprint_lib_path.exists(),
            "model_3d_path_exists": self.model_3d_path.exists(),
        }

    def _get_footprint_lib_nickname(self) -> str:
        """
        Get footprint library nickname from project's fp-lib-table

        Searches the fp-lib-table for a library entry that points to the
        LCSC footprint library path and returns its nickname.

        Returns:
            Library nickname (e.g., "lcsc_footprints")
            Falls back to config default if not found
        """
        # The shared library is registered under its own nickname in the
        # global table; the project's fp-lib-table has nothing to say.
        if self.config.is_shared_library():
            return self.config.get_library_nicknames()["footprint"]

        lib_table_path = self.project_path.parent / "fp-lib-table"

        # If fp-lib-table doesn't exist yet, return config default
        if not lib_table_path.exists():
            nickname = self.config.get("footprint_lib_nickname")
            self.logger.debug(f"fp-lib-table not found, using config default: {nickname}")
            return nickname

        try:
            # Read fp-lib-table
            with open(lib_table_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Look for library entry that contains our footprint path
            # Pattern: (lib (name "nickname")...(uri "path/footprints.pretty")...)
            # We look for entries containing "footprints.pretty" in the URI
            footprint_lib_name = self.config.get("footprint_lib_name")  # e.g., "footprints.pretty"

            # Match: (lib (name "some_name")... anything ...(uri "...footprints.pretty")...)
            # We use a more flexible pattern that handles variations
            lines = content.split('\n')
            current_lib_name = None

            for line in lines:
                # Check for lib name
                name_match = re.search(r'\(name\s+"([^"]+)"', line)
                if name_match:
                    current_lib_name = name_match.group(1)

                # Check if this line contains our footprint path
                if current_lib_name and footprint_lib_name in line:
                    self.logger.info(f"Found footprint library nickname in fp-lib-table: {current_lib_name}")
                    return current_lib_name

            # Not found in table, use config default
            nickname = self.config.get("footprint_lib_nickname")
            self.logger.debug(f"Footprint library not found in fp-lib-table, using config default: {nickname}")
            return nickname

        except Exception as e:
            # On any error, fall back to config default
            self.logger.warning(f"Failed to parse fp-lib-table: {e}")
            nickname = self.config.get("footprint_lib_nickname")
            self.logger.debug(f"Using config default: {nickname}")
            return nickname
