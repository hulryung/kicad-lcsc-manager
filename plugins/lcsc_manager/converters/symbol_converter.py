"""
Symbol Converter - Convert EasyEDA symbols to KiCad format

This module converts EasyEDA symbol JSON data to KiCad symbol format (.kicad_sym)
Based on JLC2KiCad_lib by TousstNicolas
"""
from typing import Dict, Any, Optional
from pathlib import Path
from ..utils.logger import get_logger
from ..utils.config import get_config
from ..utils.files import sexpr_escape
try:
    from .jlc2kicad import symbol_handlers
except ImportError:
    symbol_handlers = None

logger = get_logger()


def sanitize_name(text: str) -> str:
    """Make a part description or package usable as a KiCad symbol or
    footprint name (same rules as JLC2KiCad_lib). The symbol's Footprint
    field and the footprint's file name both go through this, so they can't
    drift apart."""
    return (text
            .replace(" ", "_")
            .replace(".", "_")
            .replace("/", "{slash}")
            .replace("\\", "{backslash}")
            .replace("<", "{lt}")
            .replace(">", "{gt}")
            .replace(":", "{colon}")
            .replace('"', "{dblquote}"))


class SymbolConverter:
    """Converter for EasyEDA symbols to KiCad format"""

    def __init__(self):
        """Initialize symbol converter"""
        self.logger = get_logger("symbol_converter")
        self.config = get_config()

    def convert(
        self,
        easyeda_data: Dict[str, Any],
        component_info: Dict[str, Any],
        symbol_name: Optional[str] = None
    ) -> str:
        """
        Convert EasyEDA symbol data to KiCad symbol format

        Args:
            easyeda_data: Raw EasyEDA symbol data (complete API response)
            component_info: Component metadata (name, description, etc.)
            symbol_name: Name to give the symbol; derived from the part's
                description when omitted. The library manager passes one
                that doesn't clash with another part's symbol.

        Returns:
            KiCad symbol content (S-expression format)

        Raises:
            ValueError: If conversion fails
        """
        self.logger.info(f"Converting symbol: {component_info.get('name', 'unknown')}")

        try:
            # Extract symbol data from EasyEDA format
            symbol_name = symbol_name or self._get_symbol_name(component_info)
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
                symbol_name=symbol_name or self._get_symbol_name(component_info),
                reference=component_info.get("prefix", "U").replace("?", ""),
                value=component_info.get("description", "Unknown"),
                description=component_info.get("description", ""),
                datasheet=component_info.get("datasheet", ""),
                manufacturer=component_info.get("manufacturer", ""),
                lcsc_id=component_info.get("lcsc_id", ""),
                footprint=self._get_footprint_reference(component_info)
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
        # Everything below goes inside "..." in the library file.
        name = sexpr_escape(symbol_name)

        # Extract shape data from EasyEDA response
        if "dataStr" not in easyeda_data:
            raise ValueError("No shape data in EasyEDA response")

        if symbol_handlers is None:
            raise ValueError("symbol_handlers not available (missing KicadModTree?)")

        # Multi-unit symbols (e.g. large MCUs split across several gates) deliver
        # each unit as an entry in "subparts"; the top-level dataStr.shape is empty
        # in that case. Single-unit symbols carry their geometry directly in the
        # top-level dataStr.shape and have no subparts. Emit one KiCad sub-symbol
        # ("{name}_{unit}_1") per unit so every piece imports — previously only the
        # top-level shape was read, dropping every subpart unit.
        subparts = easyeda_data.get("subparts") or []
        units = subparts if subparts else [easyeda_data]

        # All units share a single canvas origin so their geometry stays aligned
        # when placed together in a schematic (mirrors easyeda2kicad's shared-origin
        # handling). EasyEDA stores the same head x/y on the top-level and every
        # subpart, so the top-level head is the authoritative reference.
        head = easyeda_data["dataStr"].get("head", {})
        translation = (float(head.get("x") or 0), float(head.get("y") or 0))

        shape_count = 0
        for unit_index, unit in enumerate(units, start=1):
            unit_shape = unit.get("dataStr", {}).get("shape", []) or []

            # Add drawing start (unit_demorgan format for KiCad 9.0)
            kicad_symbol.drawing += f'\n    (symbol "{name}_{unit_index}_1"'

            for line in unit_shape:
                args = [i for i in line.split("~")]
                model = args[0]

                if model in symbol_handlers.handlers:
                    shape_count += 1
                    try:
                        if model == "P":
                            # h_P needs the raw line to extract multi-unit pin numbers
                            # from the ^^-delimited num segment.
                            symbol_handlers.handlers[model](
                                data=args[1:],
                                translation=translation,
                                kicad_symbol=kicad_symbol,
                                raw_line=line,
                            )
                        else:
                            symbol_handlers.handlers[model](
                                data=args[1:],
                                translation=translation,
                                kicad_symbol=kicad_symbol,
                            )
                    except Exception as e:
                        self.logger.warning(f"Failed to parse shape element {model}: {e}")
                else:
                    self.logger.debug(f"Unhandled symbol shape type: {model}")

            kicad_symbol.drawing += "\n    )"

        # No drawable geometry anywhere -> fall back to the placeholder symbol.
        if shape_count == 0:
            raise ValueError("No shape data in EasyEDA response")

        if len(units) > 1:
            self.logger.info(f"Multi-unit symbol: {len(units)} units")

        # Build complete symbol with properties
        reference = sexpr_escape(reference)
        lcsc_id = sexpr_escape(component_info.get("lcsc_id", ""))
        datasheet = sexpr_escape(component_info.get("datasheet", ""))
        description = sexpr_escape(component_info.get("description", ""))
        manufacturer = sexpr_escape(component_info.get("manufacturer", ""))

        # Generate footprint reference (library:footprint format)
        footprint_name = sexpr_escape(self._get_footprint_reference(component_info))

        complete_symbol = f'''(kicad_symbol_lib
  (version 20241209)
  (generator "kicad_lcsc_manager")
  (generator_version "1.0")
  (symbol "{name}"
    (exclude_from_sim no)
    (in_bom yes)
    (on_board yes)
    (property "Reference" "{reference}"
      (at 0 1.27 0)
      (effects
        (font (size 1.27 1.27))
      )
    )
    (property "Value" "{description}"
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
        # Use description (e.g., "RP2040") as the symbol name; a part
        # without one falls back to its name, then its LCSC number.
        description = (component_info.get("description")
                       or component_info.get("name")
                       or component_info.get("lcsc_id")
                       or "Unknown")
        return sanitize_name(str(description).strip()) or "Unknown"

    def _get_footprint_reference(self, component_info: Dict[str, Any]) -> str:
        """
        Generate KiCad footprint reference (library:footprint format)

        Args:
            component_info: Component metadata

        Returns:
            Footprint reference in KiCad format (e.g., "footprints:C2040_LQFN-56")
        """
        lcsc_id = component_info.get("lcsc_id", "Unknown")
        package = component_info.get("package", "Unknown")

        # Same rule as footprint_converter, which names the file.
        footprint_name = f"{lcsc_id}_{sanitize_name(package)}"

        # KiCad footprint reference format: library_nickname:footprint_name
        # Get library nickname from component_info (set by library_manager from fp-lib-table)
        # If not available, fall back to config default
        lib_nickname = component_info.get("footprint_lib_nickname") or self.config.get("footprint_lib_nickname")
        return f"{lib_nickname}:{footprint_name}"

    def _create_placeholder_symbol(
        self,
        symbol_name: str,
        reference: str,
        value: str,
        description: str,
        datasheet: str,
        manufacturer: str,
        lcsc_id: str,
        footprint: str = ""
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
            footprint: Footprint reference (library:footprint)

        Returns:
            KiCad symbol S-expression
        """
        symbol_name = sexpr_escape(symbol_name)
        reference = sexpr_escape(reference)
        value = sexpr_escape(value)
        description = sexpr_escape(description)
        datasheet = sexpr_escape(datasheet)
        manufacturer = sexpr_escape(manufacturer)
        lcsc_id = sexpr_escape(lcsc_id)
        footprint = sexpr_escape(footprint)
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
    (property "Footprint" "{footprint}"
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

        An existing symbol of the same name is replaced. A file that isn't a
        symbol library is left untouched (see library/symbol_lib.py).

        Args:
            symbol_content: KiCad symbol S-expression (a one-symbol library)
            library_path: Path to .kicad_sym file
            append: If True, add to an existing library; if False, overwrite

        Returns:
            True if successful

        Raises:
            IOError: If file operation fails
        """
        from ..library import symbol_lib
        from ..utils.files import atomic_write_text

        try:
            if append:
                outcome = symbol_lib.put_symbol(library_path, symbol_content)
            else:
                library_path.parent.mkdir(parents=True, exist_ok=True)
                atomic_write_text(library_path, symbol_content)
                outcome = "written"
            self.logger.info(f"Symbol saved to: {library_path} ({outcome})")
            return True

        except symbol_lib.SymbolLibraryError as e:
            self.logger.error(f"Symbol library left untouched: {e}")
            raise IOError(symbol_lib.untouched_message(e))
        except Exception as e:
            self.logger.error(f"Failed to save symbol: {e}", exc_info=True)
            raise IOError(f"Failed to save symbol: {e}")
