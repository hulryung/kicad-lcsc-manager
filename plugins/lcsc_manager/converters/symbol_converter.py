"""
Symbol Converter - Convert EasyEDA symbols to KiCad format

This module converts EasyEDA symbol JSON data to KiCad symbol format (.kicad_sym)
Based on JLC2KiCad_lib by TousstNicolas
"""
from typing import Dict, Any, Optional
from pathlib import Path
from ..utils.logger import get_logger
from .jlc2kicad import symbol_handlers

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
            easyeda_data: Raw EasyEDA symbol data (complete API response)
            component_info: Component metadata (name, description, etc.)

        Returns:
            KiCad symbol content (S-expression format)

        Raises:
            ValueError: If conversion fails
        """
        self.logger.info(f"Converting symbol: {component_info.get('name', 'unknown')}")

        try:
            # Extract symbol data from EasyEDA format
            symbol_name = self._get_symbol_name(component_info)
            reference = component_info.get("prefix", "U").replace("?", "")

            # Create symbol using JLC2KiCad handlers
            kicad_symbol = self._create_symbol_from_easyeda(
                easyeda_data=easyeda_data,
                symbol_name=symbol_name,
                reference=reference,
                component_info=component_info
            )

            self.logger.info(f"Symbol conversion completed: {symbol_name}")
            return kicad_symbol

        except Exception as e:
            self.logger.error(f"Symbol conversion failed: {e}", exc_info=True)
            # Fallback to placeholder
            self.logger.warning("Falling back to placeholder symbol")
            return self._create_placeholder_symbol(
                symbol_name=self._get_symbol_name(component_info),
                reference=component_info.get("prefix", "U").replace("?", ""),
                value=component_info.get("name", "Unknown"),
                description=component_info.get("description", ""),
                datasheet=component_info.get("datasheet", ""),
                manufacturer=component_info.get("manufacturer", ""),
                lcsc_id=component_info.get("lcsc_id", "")
            )

    def _create_symbol_from_easyeda(
        self,
        easyeda_data: Dict[str, Any],
        symbol_name: str,
        reference: str,
        component_info: Dict[str, Any]
    ) -> str:
        """
        Create KiCad symbol from EasyEDA data using handlers

        Args:
            easyeda_data: Complete EasyEDA API response
            symbol_name: Symbol name
            reference: Reference designator
            component_info: Component metadata

        Returns:
            KiCad symbol S-expression
        """
        class KicadSymbol:
            """Helper class to accumulate symbol drawing elements"""
            def __init__(self):
                self.drawing = ""
                self.pinNamesHide = "(pin_names hide)"
                self.pinNumbersHide = "(pin_numbers hide)"

        kicad_symbol = KicadSymbol()

        # Extract shape data from EasyEDA response
        if "dataStr" not in easyeda_data or "shape" not in easyeda_data["dataStr"]:
            raise ValueError("No shape data in EasyEDA response")

        symbol_shape = easyeda_data["dataStr"]["shape"]
        translation = (
            float(easyeda_data["dataStr"]["head"]["x"]),
            float(easyeda_data["dataStr"]["head"]["y"])
        )

        # Add drawing start (unit_demorgan format for KiCad 9.0)
        kicad_symbol.drawing += f'\n    (symbol "{symbol_name}_1_1"'

        # Parse each shape element using handlers
        for line in symbol_shape:
            args = [i for i in line.split("~")]
            model = args[0]

            if model in symbol_handlers.handlers:
                try:
                    symbol_handlers.handlers[model](
                        data=args[1:],
                        translation=translation,
                        kicad_symbol=kicad_symbol
                    )
                except Exception as e:
                    self.logger.warning(f"Failed to parse shape element {model}: {e}")
            else:
                self.logger.debug(f"Unhandled symbol shape type: {model}")

        kicad_symbol.drawing += "\n    )"

        # Build complete symbol with properties
        lcsc_id = component_info.get("lcsc_id", "")
        datasheet = component_info.get("datasheet", "")
        description = component_info.get("description", "")
        manufacturer = component_info.get("manufacturer", "")
        footprint_name = ""  # Will be set by library manager

        complete_symbol = f'''(kicad_symbol_lib
  (version 20241209)
  (generator "kicad_lcsc_manager")
  (generator_version "1.0")
  (symbol "{symbol_name}"
    (exclude_from_sim no)
    (in_bom yes)
    (on_board yes)
    (property "Reference" "{reference}"
      (at 0 1.27 0)
      (effects
        (font (size 1.27 1.27))
      )
    )
    (property "Value" "{symbol_name}"
      (at 0 -2.54 0)
      (effects
        (font (size 1.27 1.27))
      )
    )
    (property "Footprint" "{footprint_name}"
      (at 0 -10.16 0)
      (effects
        (font (size 1.27 1.27))
        (hide yes)
      )
    )
    (property "Datasheet" "{datasheet}"
      (at -2.286 0.127 0)
      (effects
        (font (size 1.27 1.27))
        (hide yes)
      )
    )
    (property "Description" "{description}"
      (at 0 0 0)
      (effects
        (font (size 1.27 1.27))
        (hide yes)
      )
    )
    (property "LCSC" "{lcsc_id}"
      (at 0 0 0)
      (effects
        (font (size 1.27 1.27))
        (hide yes)
      )
    )
    (property "Manufacturer" "{manufacturer}"
      (at 0 0 0)
      (effects
        (font (size 1.27 1.27))
        (hide yes)
      )
    ){kicad_symbol.drawing}
  )
)
'''
        return complete_symbol

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

        # Sanitize name for KiCad (same as JLC2KiCad_lib)
        name = (name
                .replace(" ", "_")
                .replace(".", "_")
                .replace("/", "{slash}")
                .replace("\\", "{backslash}")
                .replace("<", "{lt}")
                .replace(">", "{gt}")
                .replace(":", "{colon}")
                .replace('"', "{dblquote}"))

        return f"{lcsc_id}_{name}"

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
        Create a placeholder KiCad symbol (fallback)

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
        symbol = f'''(kicad_symbol_lib
  (version 20241209)
  (generator "kicad_lcsc_manager")
  (generator_version "1.0")
  (symbol "{symbol_name}"
    (pin_names (offset 1.016))
    (exclude_from_sim no)
    (in_bom yes)
    (on_board yes)
    (property "Reference" "{reference}"
      (at 0 5.08 0)
      (effects
        (font (size 1.27 1.27))
      )
    )
    (property "Value" "{value}"
      (at 0 -5.08 0)
      (effects
        (font (size 1.27 1.27))
      )
    )
    (property "Footprint" ""
      (at 0 -7.62 0)
      (effects
        (font (size 1.27 1.27))
        (hide yes)
      )
    )
    (property "Datasheet" "{datasheet}"
      (at 0 0 0)
      (effects
        (font (size 1.27 1.27))
        (hide yes)
      )
    )
    (property "Description" "{description}"
      (at 0 0 0)
      (effects
        (font (size 1.27 1.27))
        (hide yes)
      )
    )
    (property "Manufacturer" "{manufacturer}"
      (at 0 -10.16 0)
      (effects
        (font (size 1.27 1.27))
        (hide yes)
      )
    )
    (property "LCSC" "{lcsc_id}"
      (at 0 -12.7 0)
      (effects
        (font (size 1.27 1.27))
        (hide yes)
      )
    )
    (symbol "{symbol_name}_0_1"
      (rectangle
        (start -5.08 3.81)
        (end 5.08 -3.81)
        (stroke
          (width 0.254)
          (type default)
        )
        (fill
          (type background)
        )
      )
    )
    (symbol "{symbol_name}_1_1"
      (pin unspecified line
        (at -7.62 0 0)
        (length 2.54)
        (name "1"
          (effects
            (font (size 1.27 1.27))
          )
        )
        (number "1"
          (effects
            (font (size 1.27 1.27))
          )
        )
      )
      (pin unspecified line
        (at 7.62 0 180)
        (length 2.54)
        (name "2"
          (effects
            (font (size 1.27 1.27))
          )
        )
        (number "2"
          (effects
            (font (size 1.27 1.27))
          )
        )
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
