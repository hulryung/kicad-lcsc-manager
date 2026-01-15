"""
Footprint Converter - Convert EasyEDA footprints to KiCad format

This module converts EasyEDA footprint JSON data to KiCad footprint format (.kicad_mod)
Based on JLC2KiCad_lib by TousstNicolas
"""
from typing import Dict, Any
from pathlib import Path
from dataclasses import dataclass
from ..utils.logger import get_logger

logger = get_logger()

try:
    from KicadModTree import Footprint, KicadFileHandler, Pad, Text, Translation
    KICADMODTREE_AVAILABLE = True
except ImportError:
    KICADMODTREE_AVAILABLE = False
    logger.warning("KicadModTree not available, footprint conversion will use placeholder")

try:
    from .jlc2kicad import footprint_handlers
except ImportError:
    logger.warning("footprint_handlers not available")
    footprint_handlers = None


@dataclass
class FootprintInfo:
    """Helper class to store footprint information during conversion"""
    max_X: float = -10000
    max_Y: float = -10000
    min_X: float = 10000
    min_Y: float = 10000
    footprint_name: str = ""
    output_dir: str = ""
    footprint_lib: str = ""
    model_base_variable: str = ""
    model_dir: str = ""
    origin: tuple = (0, 0)
    models: str = ""


class FootprintConverter:
    """Converter for EasyEDA footprints to KiCad format"""

    def __init__(self):
        """Initialize footprint converter"""
        self.logger = get_logger("footprint_converter")

    def convert(
        self,
        easyeda_data: Dict[str, Any],
        component_info: Dict[str, Any]
    ) -> str:
        """
        Convert EasyEDA footprint data to KiCad footprint format

        Args:
            easyeda_data: Raw EasyEDA data (complete API response)
            component_info: Component metadata

        Returns:
            KiCad footprint content (S-expression format)

        Raises:
            ValueError: If conversion fails
        """
        self.logger.info(f"Converting footprint: {component_info.get('name', 'unknown')}")

        try:
            footprint_name = self._get_footprint_name(component_info)

            if KICADMODTREE_AVAILABLE and footprint_handlers:
                # Use real conversion with KicadModTree
                kicad_footprint = self._create_footprint_from_easyeda(
                    easyeda_data=easyeda_data,
                    footprint_name=footprint_name,
                    component_info=component_info
                )
            else:
                # Fallback to placeholder
                self.logger.warning("Using placeholder footprint (KicadModTree not available)")
                kicad_footprint = self._create_placeholder_footprint(
                    footprint_name=footprint_name,
                    description=component_info.get("description", ""),
                    package=component_info.get("package", "Unknown"),
                    lcsc_id=component_info.get("lcsc_id", "")
                )

            self.logger.info(f"Footprint conversion completed: {footprint_name}")
            return kicad_footprint

        except Exception as e:
            self.logger.error(f"Footprint conversion failed: {e}", exc_info=True)
            # Fallback to placeholder
            self.logger.warning("Falling back to placeholder footprint")
            return self._create_placeholder_footprint(
                footprint_name=self._get_footprint_name(component_info),
                description=component_info.get("description", ""),
                package=component_info.get("package", "Unknown"),
                lcsc_id=component_info.get("lcsc_id", "")
            )

    def _create_footprint_from_easyeda(
        self,
        easyeda_data: Dict[str, Any],
        footprint_name: str,
        component_info: Dict[str, Any]
    ) -> str:
        """
        Create KiCad footprint from EasyEDA data using KicadModTree

        Args:
            easyeda_data: Complete EasyEDA API response
            footprint_name: Footprint name
            component_info: Component metadata

        Returns:
            KiCad footprint S-expression
        """
        # Extract footprint data from package detail
        if "packageDetail" not in easyeda_data:
            raise ValueError("No packageDetail in EasyEDA response")

        package_detail = easyeda_data["packageDetail"]
        if "dataStr" not in package_detail or "shape" not in package_detail["dataStr"]:
            raise ValueError("No shape data in packageDetail")

        footprint_shape = package_detail["dataStr"]["shape"]
        translation = (
            float(package_detail["dataStr"]["head"]["x"]),
            float(package_detail["dataStr"]["head"]["y"])
        )

        # Initialize KiCad footprint
        kicad_mod = Footprint(f'"{footprint_name}"')
        kicad_mod.setDescription(f"{footprint_name} footprint")
        kicad_mod.setTags(f"{footprint_name} footprint {component_info.get('lcsc_id', '')}")

        footprint_info = FootprintInfo(
            footprint_name=footprint_name,
            origin=translation
        )

        # Parse each shape element using handlers
        for line in footprint_shape:
            args = [i for i in line.split("~")]
            model = args[0]

            if model in footprint_handlers.handlers:
                try:
                    footprint_handlers.handlers[model](args[1:], kicad_mod, footprint_info)
                except Exception as e:
                    self.logger.warning(f"Failed to parse footprint element {model}: {e}")
            else:
                self.logger.debug(f"Unhandled footprint shape type: {model}")

        # Determine if THT or SMD
        if any(isinstance(child, Pad) and child.type == Pad.TYPE_THT for child in kicad_mod.getAllChilds()):
            kicad_mod.setAttribute("through_hole")
        else:
            kicad_mod.setAttribute("smd")

        # Apply translation
        mil2mm = footprint_handlers.mil2mm
        kicad_mod.insert(Translation(-mil2mm(translation[0]), -mil2mm(translation[1])))

        # Translate the footprint max and min values to the origin
        footprint_info.max_X -= mil2mm(translation[0])
        footprint_info.max_Y -= mil2mm(translation[1])
        footprint_info.min_X -= mil2mm(translation[0])
        footprint_info.min_Y -= mil2mm(translation[1])

        # Add reference and value texts
        kicad_mod.append(
            Text(
                type="reference",
                text="REF**",
                at=[
                    (footprint_info.min_X + footprint_info.max_X) / 2,
                    footprint_info.min_Y - 2,
                ],
                layer="F.SilkS",
            )
        )
        kicad_mod.append(
            Text(
                type="user",
                text="${REFERENCE}",
                at=[
                    (footprint_info.min_X + footprint_info.max_X) / 2,
                    (footprint_info.min_Y + footprint_info.max_Y) / 2,
                ],
                layer="F.Fab",
            )
        )
        kicad_mod.append(
            Text(
                type="value",
                text=footprint_name,
                at=[
                    (footprint_info.min_X + footprint_info.max_X) / 2,
                    footprint_info.max_Y + 2,
                ],
                layer="F.Fab",
            )
        )

        # Convert to string (S-expression)
        file_handler = KicadFileHandler(kicad_mod)
        return file_handler.serialize()

    def _get_footprint_name(self, component_info: Dict[str, Any]) -> str:
        """
        Generate KiCad footprint name

        Args:
            component_info: Component metadata

        Returns:
            Footprint name
        """
        lcsc_id = component_info.get("lcsc_id", "Unknown")
        package = component_info.get("package", "Unknown")

        # Sanitize name (same as JLC2KiCad_lib)
        package = (package
                   .replace(" ", "_")
                   .replace(".", "_")
                   .replace("/", "{slash}")
                   .replace("\\", "{backslash}")
                   .replace("<", "{lt}")
                   .replace(">", "{gt}")
                   .replace(":", "{colon}")
                   .replace('"', "{dblquote}"))

        return f"{lcsc_id}_{package}"

    def _create_placeholder_footprint(
        self,
        footprint_name: str,
        description: str,
        package: str,
        lcsc_id: str
    ) -> str:
        """
        Create a placeholder KiCad footprint (fallback)

        Args:
            footprint_name: Footprint identifier
            description: Component description
            package: Package type
            lcsc_id: LCSC part number

        Returns:
            KiCad footprint S-expression
        """
        # Simple 2-pad SMD footprint
        footprint = f'''(footprint "{footprint_name}" (version 20211014) (generator kicad_lcsc_manager)
  (layer "F.Cu")
  (descr "{package}")
  (tags "{package} LCSC:{lcsc_id}")
  (attr smd)
  (fp_text reference "REF**" (at 0 -2.5) (layer "F.SilkS")
    (effects (font (size 1 1) (thickness 0.15)))
  )
  (fp_text value "{footprint_name}" (at 0 2.5) (layer "F.Fab")
    (effects (font (size 1 1) (thickness 0.15)))
  )
  (fp_text user "{package}" (at 0 0) (layer "F.Fab")
    (effects (font (size 0.8 0.8) (thickness 0.12)))
  )
  (fp_line (start -1.5 -1) (end 1.5 -1) (layer "F.SilkS") (width 0.12))
  (fp_line (start -1.5 1) (end 1.5 1) (layer "F.SilkS") (width 0.12))
  (fp_line (start -2 -1.5) (end 2 -1.5) (layer "F.CrtYd") (width 0.05))
  (fp_line (start -2 1.5) (end -2 -1.5) (layer "F.CrtYd") (width 0.05))
  (fp_line (start 2 -1.5) (end 2 1.5) (layer "F.CrtYd") (width 0.05))
  (fp_line (start 2 1.5) (end -2 1.5) (layer "F.CrtYd") (width 0.05))
  (fp_rect (start -1.2 -0.8) (end 1.2 0.8) (layer "F.Fab") (width 0.1) (fill none))
  (pad "1" smd rect (at -1 0) (size 0.8 1.2) (layers "F.Cu" "F.Paste" "F.Mask"))
  (pad "2" smd rect (at 1 0) (size 0.8 1.2) (layers "F.Cu" "F.Paste" "F.Mask"))
  (model "${{KIPRJMOD}}/libs/lcsc/3dmodels/{lcsc_id}.step"
    (offset (xyz 0 0 0))
    (scale (xyz 1 1 1))
    (rotate (xyz 0 0 0))
  )
)
'''
        return footprint

    def save_to_library(
        self,
        footprint_content: str,
        footprint_name: str,
        library_path: Path
    ) -> bool:
        """
        Save footprint to KiCad library directory

        Args:
            footprint_content: KiCad footprint S-expression
            footprint_name: Footprint name
            library_path: Path to .pretty directory

        Returns:
            True if successful

        Raises:
            IOError: If file operation fails
        """
        try:
            # Create library directory if needed
            library_path.mkdir(parents=True, exist_ok=True)

            # Write footprint file
            footprint_file = library_path / f"{footprint_name}.kicad_mod"
            with open(footprint_file, 'w', encoding='utf-8') as f:
                f.write(footprint_content)

            self.logger.info(f"Footprint saved to: {footprint_file}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to save footprint: {e}", exc_info=True)
            raise IOError(f"Failed to save footprint: {e}")
