"""
KiCad Preview Renderer

Fetches pre-rendered SVGs from EasyEDA's API for fast, accurate previews.
Falls back to KiCad CLI rendering if the API is unavailable.
"""
from typing import Dict, Any, Optional, List
from pathlib import Path
import tempfile
import subprocess
import shutil
import sys
import io
import requests
import wx
from PIL import Image
from ..utils.logger import get_logger

logger = get_logger()


# EasyEDA docType constants
DOCTYPE_SYMBOL = 2
DOCTYPE_FOOTPRINT = 4


def _find_kicad_cli() -> Optional[str]:
    """Find KiCad CLI executable based on platform"""
    if sys.platform == "darwin":
        candidates = [
            "/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli",
            "/Applications/KiCad 9.0/KiCad.app/Contents/MacOS/kicad-cli",
        ]
    elif sys.platform == "win32":
        candidates = [
            r"C:\Program Files\KiCad\9.0\bin\kicad-cli.exe",
            r"C:\Program Files\KiCad\8.0\bin\kicad-cli.exe",
            r"C:\Program Files (x86)\KiCad\9.0\bin\kicad-cli.exe",
        ]
    else:
        candidates = [
            "/usr/bin/kicad-cli",
            "/usr/local/bin/kicad-cli",
            "/snap/bin/kicad-cli",
        ]

    for path in candidates:
        if Path(path).exists():
            return path

    return shutil.which("kicad-cli")


class KiCadPreviewRenderer:
    """Renders symbols and footprints using EasyEDA SVG API or KiCad CLI fallback"""

    IMAGE_SIZE = (400, 400)
    BACKGROUND_COLOR = (255, 255, 255)

    # EasyEDA SVG API endpoint
    EASYEDA_SVG_URL = "https://easyeda.com/api/products/{lcsc_id}/svgs"

    def __init__(self):
        self.logger = get_logger("kicad_preview")
        self.kicad_cli = _find_kicad_cli()
        # Cache fetched SVG data per LCSC ID
        self._svg_cache: Dict[str, Optional[List]] = {}

    def _fetch_easyeda_svgs(self, lcsc_id: str) -> Optional[List[Dict[str, Any]]]:
        """
        Fetch pre-rendered SVGs from EasyEDA API.

        Returns list of SVG entries with docType, svg, and bbox fields.
        Results are cached per LCSC ID.
        """
        if lcsc_id in self._svg_cache:
            return self._svg_cache[lcsc_id]

        try:
            url = self.EASYEDA_SVG_URL.format(lcsc_id=lcsc_id)
            self.logger.debug(f"Fetching SVGs from: {url}")

            response = requests.get(url, timeout=10, headers={
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                              'AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36',
                'Accept': 'application/json',
            })
            response.raise_for_status()
            data = response.json()

            if not data.get("success"):
                self.logger.warning(f"EasyEDA SVG API failed for {lcsc_id}")
                self._svg_cache[lcsc_id] = None
                return None

            result = data.get("result", [])
            self._svg_cache[lcsc_id] = result
            self.logger.debug(f"Fetched {len(result)} SVGs for {lcsc_id}")
            return result

        except Exception as e:
            self.logger.warning(f"Failed to fetch EasyEDA SVGs: {e}")
            self._svg_cache[lcsc_id] = None
            return None

    def _get_svg_by_doctype(self, svgs: List[Dict[str, Any]], doc_type: int) -> Optional[str]:
        """Extract SVG string for a specific docType from API results."""
        for entry in svgs:
            if entry.get("docType") == doc_type:
                return entry.get("svg")
        return None

    def render_symbol(self, easyeda_data: Dict[str, Any], component_info: Dict[str, Any]) -> Optional[wx.Bitmap]:
        """Render symbol preview, trying EasyEDA SVG API first."""
        lcsc_id = component_info.get("lcsc_id", "")

        # Try EasyEDA pre-rendered SVG
        if lcsc_id:
            bitmap = self._render_from_easyeda_svg(lcsc_id, DOCTYPE_SYMBOL)
            if bitmap:
                return bitmap

        # Fallback to KiCad CLI
        return self._render_symbol_kicad_cli(easyeda_data, component_info)

    def render_footprint(self, easyeda_data: Dict[str, Any], component_info: Dict[str, Any]) -> Optional[wx.Bitmap]:
        """Render footprint preview, trying EasyEDA SVG API first."""
        lcsc_id = component_info.get("lcsc_id", "")

        # Try EasyEDA pre-rendered SVG
        if lcsc_id:
            bitmap = self._render_from_easyeda_svg(lcsc_id, DOCTYPE_FOOTPRINT)
            if bitmap:
                return bitmap

        # Fallback to KiCad CLI
        return self._render_footprint_kicad_cli(easyeda_data, component_info)

    def _render_from_easyeda_svg(self, lcsc_id: str, doc_type: int) -> Optional[wx.Bitmap]:
        """Render preview from EasyEDA pre-rendered SVG."""
        try:
            svgs = self._fetch_easyeda_svgs(lcsc_id)
            if not svgs:
                return None

            svg_str = self._get_svg_by_doctype(svgs, doc_type)
            if not svg_str:
                self.logger.debug(f"No SVG for docType={doc_type} in {lcsc_id}")
                return None

            # Write SVG to temp file and render
            with tempfile.NamedTemporaryFile(suffix='.svg', mode='w',
                                              encoding='utf-8', delete=False) as f:
                f.write(svg_str)
                svg_path = Path(f.name)

            try:
                bitmap = self._svg_to_bitmap_wx(svg_path)
                self.logger.debug(f"Rendered {lcsc_id} docType={doc_type} from EasyEDA SVG")
                return bitmap
            finally:
                svg_path.unlink(missing_ok=True)

        except Exception as e:
            self.logger.warning(f"EasyEDA SVG rendering failed: {e}")
            return None

    def _render_symbol_kicad_cli(self, easyeda_data: Dict[str, Any], component_info: Dict[str, Any]) -> Optional[wx.Bitmap]:
        """Render symbol using KiCad CLI (fallback)."""
        try:
            if not self.kicad_cli:
                return self._create_placeholder("Preview unavailable")

            from ..converters.symbol_converter import SymbolConverter
            converter = SymbolConverter()

            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)

                symbol_content = converter.convert(easyeda_data, component_info)
                symbol_lib_file = temp_path / "temp.kicad_sym"
                symbol_lib_file.write_text(symbol_content, encoding='utf-8')

                svg_output = temp_path / "output"
                svg_output.mkdir(exist_ok=True)

                result = subprocess.run(
                    [self.kicad_cli, "sym", "export", "svg",
                     "--output", str(svg_output), "--black-and-white",
                     str(symbol_lib_file)],
                    capture_output=True, text=True, timeout=10
                )

                if result.returncode != 0:
                    self.logger.error(f"KiCad CLI failed: {result.stderr}")
                    return self._create_placeholder("KiCad export failed")

                svg_files = list(svg_output.glob("*.svg"))
                if not svg_files:
                    return self._create_placeholder("No output generated")

                return self._svg_to_bitmap_wx(svg_files[0])

        except subprocess.TimeoutExpired:
            return self._create_placeholder("Render timeout")
        except Exception as e:
            self.logger.error(f"Symbol rendering failed: {e}", exc_info=True)
            return self._create_placeholder("Render error")

    def _render_footprint_kicad_cli(self, easyeda_data: Dict[str, Any], component_info: Dict[str, Any]) -> Optional[wx.Bitmap]:
        """Render footprint using KiCad CLI (fallback)."""
        try:
            if not self.kicad_cli:
                return self._create_placeholder("Preview unavailable")

            from ..converters.footprint_converter import FootprintConverter
            converter = FootprintConverter()

            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)

                fp_lib_dir = temp_path / "temp.pretty"
                fp_lib_dir.mkdir(exist_ok=True)

                footprint_content = converter.convert(easyeda_data, component_info)
                footprint_name = component_info.get("package", "footprint")
                fp_file = fp_lib_dir / f"{footprint_name}.kicad_mod"
                fp_file.write_text(footprint_content, encoding='utf-8')

                svg_output = temp_path / "output"
                svg_output.mkdir(exist_ok=True)

                result = subprocess.run(
                    [self.kicad_cli, "fp", "export", "svg",
                     "--output", str(svg_output),
                     "--layers", "F.Cu,F.SilkS,F.Fab",
                     "--black-and-white", str(fp_lib_dir)],
                    capture_output=True, text=True, timeout=10
                )

                if result.returncode != 0:
                    self.logger.error(f"KiCad CLI failed: {result.stderr}")
                    return self._create_placeholder("KiCad export failed")

                svg_files = list(svg_output.glob("*.svg"))
                if not svg_files:
                    return self._create_placeholder("No output generated")

                return self._svg_to_bitmap_wx(svg_files[0])

        except subprocess.TimeoutExpired:
            return self._create_placeholder("Render timeout")
        except Exception as e:
            self.logger.error(f"Footprint rendering failed: {e}", exc_info=True)
            return self._create_placeholder("Render error")

    def _svg_to_bitmap_wx(self, svg_path: Path) -> wx.Bitmap:
        """
        Convert SVG file to wx.Bitmap using wx.svg.SVGimage.

        Handles alpha channel by compositing onto white background.
        Crops to content and centers on white canvas.
        """
        from wx.svg import SVGimage

        svg_img = SVGimage.CreateFromFile(str(svg_path))
        if svg_img.width <= 0 or svg_img.height <= 0:
            raise RuntimeError("SVGimage failed to load SVG")

        # Render at 2x resolution for quality
        render_width = int(self.IMAGE_SIZE[0] * 2)
        render_height = int(self.IMAGE_SIZE[1] * 2)

        bmp = svg_img.ConvertToScaledBitmap(wx.Size(render_width, render_height))

        # Convert to PIL, handling alpha channel
        wx_img = bmp.ConvertToImage()
        width, height = wx_img.GetWidth(), wx_img.GetHeight()
        rgb_data = bytes(wx_img.GetData())

        if wx_img.HasAlpha():
            alpha_data = bytes(wx_img.GetAlpha())
            pil_rgb = Image.frombytes('RGB', (width, height), rgb_data)
            pil_alpha = Image.frombytes('L', (width, height), alpha_data)
            pil_rgba = pil_rgb.copy()
            pil_rgba.putalpha(pil_alpha)
            pil_image = Image.new('RGB', (width, height), self.BACKGROUND_COLOR)
            pil_image.paste(pil_rgba, mask=pil_alpha)
        else:
            pil_image = Image.frombytes('RGB', (width, height), rgb_data)

        # Crop to content (remove whitespace around the drawing)
        bbox = pil_image.convert('L').point(lambda x: 0 if x > 250 else 255).getbbox()
        if bbox:
            margin = 20
            bbox = (
                max(0, bbox[0] - margin),
                max(0, bbox[1] - margin),
                min(pil_image.width, bbox[2] + margin),
                min(pil_image.height, bbox[3] + margin)
            )
            pil_image = pil_image.crop(bbox)

        # Scale to fit display size
        pil_image.thumbnail(self.IMAGE_SIZE, Image.Resampling.LANCZOS)

        # Center on white background
        final_image = Image.new('RGB', self.IMAGE_SIZE, self.BACKGROUND_COLOR)
        offset = (
            (self.IMAGE_SIZE[0] - pil_image.size[0]) // 2,
            (self.IMAGE_SIZE[1] - pil_image.size[1]) // 2
        )
        final_image.paste(pil_image, offset)

        return self._pil_to_wx_bitmap(final_image)

    def _create_placeholder(self, message: str) -> wx.Bitmap:
        """Create a placeholder image with message"""
        from PIL import ImageDraw

        img = Image.new('RGB', self.IMAGE_SIZE, self.BACKGROUND_COLOR)
        draw = ImageDraw.Draw(img)

        # Draw border
        draw.rectangle([10, 10, self.IMAGE_SIZE[0]-10, self.IMAGE_SIZE[1]-10],
                      outline=(200, 200, 200), width=2)

        # Draw text
        draw.text((self.IMAGE_SIZE[0]//2, self.IMAGE_SIZE[1]//2), message,
                 fill=(150, 150, 150), anchor="mm")

        return self._pil_to_wx_bitmap(img)

    def _pil_to_wx_bitmap(self, pil_image):
        """Convert PIL Image to wx.Bitmap"""
        buf = io.BytesIO()
        pil_image.save(buf, format='PNG')
        buf.seek(0)

        wx_image = wx.Image(buf, wx.BITMAP_TYPE_PNG)
        return wx.Bitmap(wx_image)
