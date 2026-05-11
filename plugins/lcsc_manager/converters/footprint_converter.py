"""
Footprint Converter — convert EasyEDA footprints to KiCad .kicad_mod text.

Backed by a vendored subset of upstream easyeda2kicad.py
(plugins/lcsc_manager/vendor/easyeda2kicad/, AGPL-3.0). Upstream's
EasyedaFootprintImporter parses our raw LCSC API JSON directly, and
ExporterFootprintKicad emits S-expressions via plain string templates —
no external Python deps, no KicadModTree.
"""
import os
import re
import tempfile
from typing import Dict, Any
from pathlib import Path

from ..utils.logger import get_logger
from ..vendor.easyeda2kicad.easyeda.easyeda_importer import EasyedaFootprintImporter
from ..vendor.easyeda2kicad.kicad.export_kicad_footprint import ExporterFootprintKicad

logger = get_logger()


class FootprintConverter:
    """Converter for EasyEDA footprints to KiCad format."""

    def __init__(self, model_uri_base: str = "${KIPRJMOD}/libs/lcsc/3dmodels"):
        """
        Args:
            model_uri_base: URI prefix used for 3D model references inside
                            generated .kicad_mod files. Trailing slash is
                            stripped.
        """
        self.logger = get_logger("footprint_converter")
        self.model_uri_base = model_uri_base.rstrip("/")

    def convert(
        self,
        easyeda_data: Dict[str, Any],
        component_info: Dict[str, Any],
    ) -> str:
        """
        Convert EasyEDA footprint data to KiCad .kicad_mod text.

        Args:
            easyeda_data: raw EasyEDA API response for the component
            component_info: component metadata (lcsc_id, package, …)

        Returns:
            KiCad footprint S-expression as a single string.

        Raises:
            ValueError: if the EasyEDA data can't be parsed.
        """
        lcsc_id = component_info.get("lcsc_id", "unknown")
        self.logger.info(f"Converting footprint: {lcsc_id}")

        ee_footprint = EasyedaFootprintImporter(
            easyeda_cp_cad_data=easyeda_data
        ).output

        # Force the on-disk name to match our existing naming scheme
        # (LCSC_ID_PACKAGE), so symbol→footprint linkage and the existing
        # path layout keep working.
        ee_footprint.info.name = self._get_footprint_name(component_info)

        exporter = ExporterFootprintKicad(footprint=ee_footprint)

        # Upstream's export() writes to disk. Round-trip through a
        # tempfile to avoid forking upstream's templating code.
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = os.path.join(tmp, f"{ee_footprint.info.name}.kicad_mod")
            exporter.export(
                footprint_full_path=tmp_path,
                model_3d_path=self.model_uri_base,
                model_3d_extension="wrl",
            )
            with open(tmp_path, "r", encoding="utf-8") as f:
                text = f.read()

        text = self._postprocess(text, lcsc_id)
        self.logger.info(f"Footprint conversion completed: {lcsc_id}")
        return text

    # ─── post-processing ──────────────────────────────────────────────

    def _postprocess(self, text: str, lcsc_id: str) -> str:
        """
        Adjustments applied after upstream emits text:

        - rewrite the `package_lib` token from upstream's hardcoded
          "easyeda2kicad" to our plugin name so generated files are
          attributable to us
        - normalise pad numbers of form `NAME(NUMBER)` → `NUMBER`
          (upstream sometimes leaves the EasyEDA-style "VCC(3)" string
          on certain BGA / connector parts).
        """
        text = text.replace("easyeda2kicad:", "kicad_lcsc_manager:", 1)
        text = self._normalize_pad_numbers(text, lcsc_id)
        return text

    @staticmethod
    def _normalize_pad_numbers(text: str, lcsc_id: str) -> str:
        """Strip `NAME(N)` decoration from `(pad ...)` lines."""
        def _sub(match: "re.Match[str]") -> str:
            pad_num = match.group(1)
            stripped = re.sub(r"^[^(]+\((\d+)\)$", r"\1", pad_num)
            if stripped != pad_num:
                logger = get_logger("footprint_converter")
                logger.debug(
                    f"{lcsc_id}: normalized pad number {pad_num!r} → {stripped!r}"
                )
            return f"(pad {stripped} "
        # Pad line shapes: (pad NUMBER type shape …) or (pad "NUMBER" …)
        return re.sub(r'\(pad\s+"?([^"\s]+)"?\s+', _sub, text)

    # ─── naming + save helpers (used by library_manager) ─────────────

    def _get_footprint_name(self, component_info: Dict[str, Any]) -> str:
        """Generate the on-disk footprint name: ``LCSCID_SANITIZED_PACKAGE``."""
        lcsc_id = component_info.get("lcsc_id", "Unknown")
        package = component_info.get("package", "Unknown")
        package = (
            package.replace(" ", "_")
                   .replace(".", "_")
                   .replace("/", "{slash}")
                   .replace("\\", "{backslash}")
                   .replace("<", "{lt}")
                   .replace(">", "{gt}")
                   .replace(":", "{colon}")
                   .replace('"', "{dblquote}")
        )
        return f"{lcsc_id}_{package}"

    def save_to_library(
        self,
        footprint_content: str,
        footprint_name: str,
        library_path: Path,
    ) -> bool:
        """Write the footprint into `<library_path>/<footprint_name>.kicad_mod`."""
        try:
            library_path.mkdir(parents=True, exist_ok=True)
            out_file = library_path / f"{footprint_name}.kicad_mod"
            with open(out_file, "w", encoding="utf-8") as f:
                f.write(footprint_content)
            self.logger.info(f"Footprint saved: {out_file}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to save footprint: {e}")
            return False
