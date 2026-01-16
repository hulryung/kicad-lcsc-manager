"""
Library Manager - Manage KiCad project libraries

This module handles adding components to KiCad project libraries
and managing library configuration
"""
from typing import Dict, Any, Optional
from pathlib import Path
from ..utils.logger import get_logger
from ..utils.config import get_config
from ..converters.symbol_converter import SymbolConverter
from ..converters.footprint_converter import FootprintConverter
from ..converters.model_3d_converter import Model3DConverter

logger = get_logger()


class LibraryManager:
    """Manage KiCad project libraries"""

    def __init__(self, project_path: Path):
        """
        Initialize library manager

        Args:
            project_path: Path to KiCad project file
        """
        self.project_path = project_path
        self.config = get_config()
        self.logger = get_logger("library_manager")

        # Initialize converters
        self.symbol_converter = SymbolConverter()
        self.footprint_converter = FootprintConverter()
        self.model_3d_converter = Model3DConverter()

        # Get library paths
        self.lib_base_path = self.config.get_library_path(project_path)
        self.symbol_lib_path = self.config.get_symbol_lib_path(project_path)
        self.footprint_lib_path = self.config.get_footprint_lib_path(project_path)
        self.model_3d_path = self.config.get_3d_model_path(project_path)

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
            self._update_library_tables()

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

    def _update_library_tables(self):
        """
        Update KiCad library tables to include imported libraries

        This ensures KiCad can find the imported components
        """
        self.logger.info("Updating library tables")

        try:
            # Update symbol library table
            self._update_symbol_lib_table()

            # Update footprint library table
            self._update_footprint_lib_table()

        except Exception as e:
            self.logger.error(f"Failed to update library tables: {e}")
            # Non-fatal error - user can manually add libraries

    def _update_symbol_lib_table(self):
        """Update sym-lib-table file"""
        lib_table_path = self.project_path.parent / "sym-lib-table"

        lib_name = self.config.get("symbol_lib_nickname")
        lib_path = "${KIPRJMOD}/libs/lcsc/symbols/lcsc_imported.kicad_sym"

        try:
            # Check if library table exists
            if lib_table_path.exists():
                with open(lib_table_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                # Check if our library is already registered
                if lib_name in content:
                    self.logger.info("Symbol library already registered")
                    return

                # Add library entry
                # Remove closing parenthesis
                content = content.rstrip().rstrip(')')

                # Add new library entry
                entry = f'''  (lib (name "{lib_name}")(type "KiCad")(uri "{lib_path}")(options "")(descr "LCSC imported components"))
)
'''
                content = content + '\n' + entry

            else:
                # Create new library table
                content = f'''(sym_lib_table
  (lib (name "{lib_name}")(type "KiCad")(uri "{lib_path}")(options "")(descr "LCSC imported components"))
)
'''

            # Write library table
            with open(lib_table_path, 'w', encoding='utf-8') as f:
                f.write(content)

            self.logger.info(f"Symbol library table updated: {lib_table_path}")

        except Exception as e:
            self.logger.error(f"Failed to update symbol library table: {e}")

    def _update_footprint_lib_table(self):
        """Update fp-lib-table file"""
        lib_table_path = self.project_path.parent / "fp-lib-table"

        lib_name = self.config.get("footprint_lib_nickname")
        lib_path = "${KIPRJMOD}/libs/lcsc/footprints.pretty"

        try:
            # Check if library table exists
            if lib_table_path.exists():
                with open(lib_table_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                # Check if our library is already registered
                if lib_name in content:
                    self.logger.info("Footprint library already registered")
                    return

                # Add library entry
                content = content.rstrip().rstrip(')')

                entry = f'''  (lib (name "{lib_name}")(type "KiCad")(uri "{lib_path}")(options "")(descr "LCSC imported footprints"))
)
'''
                content = content + '\n' + entry

            else:
                # Create new library table
                content = f'''(fp_lib_table
  (lib (name "{lib_name}")(type "KiCad")(uri "{lib_path}")(options "")(descr "LCSC imported footprints"))
)
'''

            # Write library table
            with open(lib_table_path, 'w', encoding='utf-8') as f:
                f.write(content)

            self.logger.info(f"Footprint library table updated: {lib_table_path}")

        except Exception as e:
            self.logger.error(f"Failed to update footprint library table: {e}")

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
