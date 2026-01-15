"""
Symbol Converter - Convert EasyEDA symbols to KiCad format

This module converts EasyEDA symbol JSON data to KiCad symbol format (.kicad_sym)
"""
from typing import Dict, Any, Optional
from pathlib import Path
from ..utils.logger import get_logger

logger = get_logger()


class SymbolConverter:
    """Converter for EasyEDA symbols to KiCad format"""

    def __init__(self):
        """Initialize symbol converter"""
        self.logger = get_logger("symbol_converter")

    def convert(
        self,
        easyeda_data: Dict[str, Any],
        component_info: Dict[str, Any]
    ) -> str:
        """
        Convert EasyEDA symbol data to KiCad symbol format

        Args:
            easyeda_data: Raw EasyEDA symbol data (JSON)
            component_info: Component metadata (name, description, etc.)

        Returns:
            KiCad symbol content (S-expression format)

        Raises:
            ValueError: If conversion fails
        """
        self.logger.info(f"Converting symbol: {component_info.get('name', 'unknown')}")

        try:
            # Extract symbol data from EasyEDA format
            # EasyEDA uses a custom JSON format with shape definitions
            symbol_name = self._get_symbol_name(component_info)
            reference = self._get_reference_designator(component_info)

            # TODO: Implement actual conversion logic
            # This requires parsing EasyEDA's shape format and converting to KiCad S-expressions
            # For now, create a placeholder symbol

            kicad_symbol = self._create_placeholder_symbol(
                symbol_name=symbol_name,
                reference=reference,
                value=component_info.get("name", "Unknown"),
                description=component_info.get("description", ""),
                datasheet=component_info.get("datasheet", ""),
                manufacturer=component_info.get("manufacturer", ""),
                lcsc_id=component_info.get("lcsc_id", "")
            )

            self.logger.info(f"Symbol conversion completed: {symbol_name}")
            return kicad_symbol

        except Exception as e:
            self.logger.error(f"Symbol conversion failed: {e}", exc_info=True)
            raise ValueError(f"Failed to convert symbol: {e}")

    def _get_symbol_name(self, component_info: Dict[str, Any]) -> str:
        """
        Generate KiCad symbol name

        Args:
            component_info: Component metadata

        Returns:
            Symbol name
        """
        lcsc_id = component_info.get("lcsc_id", "Unknown")
        name = component_info.get("name", lcsc_id)

        # Sanitize name for KiCad
        name = name.replace(" ", "_").replace("/", "_").replace("\\", "_")

        return f"{lcsc_id}_{name}"

    def _get_reference_designator(self, component_info: Dict[str, Any]) -> str:
        """
        Determine reference designator based on component type

        Args:
            component_info: Component metadata

        Returns:
            Reference designator (e.g., "R", "C", "U")
        """
        category = component_info.get("category", "").lower()

        # Simple heuristic based on category
        if "resistor" in category:
            return "R"
        elif "capacitor" in category:
            return "C"
        elif "inductor" in category:
            return "L"
        elif "diode" in category:
            return "D"
        elif "transistor" in category or "mosfet" in category:
            return "Q"
        elif "ic" in category or "chip" in category:
            return "U"
        elif "connector" in category:
            return "J"
        else:
            return "U"  # Default to generic component

    def _create_placeholder_symbol(
        self,
        symbol_name: str,
        reference: str,
        value: str,
        description: str,
        datasheet: str,
        manufacturer: str,
        lcsc_id: str
    ) -> str:
        """
        Create a placeholder KiCad symbol

        This creates a simple rectangular symbol with properties.
        Full conversion from EasyEDA format will be implemented later.

        Args:
            symbol_name: Symbol identifier
            reference: Reference designator
            value: Component value
            description: Component description
            datasheet: Datasheet URL
            manufacturer: Manufacturer name
            lcsc_id: LCSC part number

        Returns:
            KiCad symbol S-expression
        """
        # KiCad 6.0+ symbol format (S-expression)
        symbol = f'''(kicad_symbol_lib (version 20211014) (generator kicad_lcsc_manager)
  (symbol "{symbol_name}" (pin_names (offset 1.016)) (in_bom yes) (on_board yes)
    (property "Reference" "{reference}" (id 0) (at 0 5.08 0)
      (effects (font (size 1.27 1.27)))
    )
    (property "Value" "{value}" (id 1) (at 0 -5.08 0)
      (effects (font (size 1.27 1.27)))
    )
    (property "Footprint" "" (id 2) (at 0 -7.62 0)
      (effects (font (size 1.27 1.27)) hide)
    )
    (property "Datasheet" "{datasheet}" (id 3) (at 0 0 0)
      (effects (font (size 1.27 1.27)) hide)
    )
    (property "Manufacturer" "{manufacturer}" (id 4) (at 0 -10.16 0)
      (effects (font (size 1.27 1.27)) hide)
    )
    (property "LCSC" "{lcsc_id}" (id 5) (at 0 -12.7 0)
      (effects (font (size 1.27 1.27)) hide)
    )
    (property "ki_description" "{description}" (id 6) (at 0 0 0)
      (effects (font (size 1.27 1.27)) hide)
    )
    (symbol "{symbol_name}_0_1"
      (rectangle (start -5.08 3.81) (end 5.08 -3.81)
        (stroke (width 0.254) (type default) (color 0 0 0 0))
        (fill (type background))
      )
    )
    (symbol "{symbol_name}_1_1"
      (pin unspecified line (at -7.62 0 0) (length 2.54)
        (name "1" (effects (font (size 1.27 1.27))))
        (number "1" (effects (font (size 1.27 1.27))))
      )
      (pin unspecified line (at 7.62 0 180) (length 2.54)
        (name "2" (effects (font (size 1.27 1.27))))
        (number "2" (effects (font (size 1.27 1.27))))
      )
    )
  )
)
'''
        return symbol

    def save_to_library(
        self,
        symbol_content: str,
        library_path: Path,
        append: bool = True
    ) -> bool:
        """
        Save symbol to KiCad library file

        Args:
            symbol_content: KiCad symbol S-expression
            library_path: Path to .kicad_sym file
            append: If True, append to existing library; if False, overwrite

        Returns:
            True if successful

        Raises:
            IOError: If file operation fails
        """
        try:
            library_path.parent.mkdir(parents=True, exist_ok=True)

            if append and library_path.exists():
                # Read existing library
                with open(library_path, 'r', encoding='utf-8') as f:
                    existing = f.read()

                # Check if it's a valid library file
                if not existing.strip().startswith('(kicad_symbol_lib'):
                    self.logger.warning("Existing file is not a valid symbol library")
                    append = False
                else:
                    # Remove closing parenthesis
                    existing = existing.rstrip().rstrip(')')

                    # Extract just the symbol definition (without wrapper)
                    symbol_def = symbol_content
                    if '(kicad_symbol_lib' in symbol_def:
                        # Extract inner symbol definition
                        start = symbol_def.find('(symbol')
                        end = symbol_def.rfind(')')
                        symbol_def = symbol_def[start:end]

                    # Append symbol and close
                    content = existing + '\n' + symbol_def + '\n)\n'
            else:
                content = symbol_content

            # Write to file
            with open(library_path, 'w', encoding='utf-8') as f:
                f.write(content)

            self.logger.info(f"Symbol saved to: {library_path}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to save symbol: {e}", exc_info=True)
            raise IOError(f"Failed to save symbol: {e}")
