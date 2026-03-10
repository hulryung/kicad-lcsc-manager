"""
KiCad Native Preview Renderer

Uses KiCad's CLI tools to render symbols and footprints natively.
"""
from typing import Dict, Any, Optional
from pathlib import Path
import tempfile
import subprocess
import shutil
import sys
import io
import wx
from PIL import Image
from ..utils.logger import get_logger
from ..converters.symbol_converter import SymbolConverter
from ..converters.footprint_converter import FootprintConverter

logger = get_logger()


def _find_kicad_cli() -> Optional[str]:
    """
    Find KiCad CLI executable based on platform

    Returns:
        Path to kicad-cli executable, or None if not found
    """
    # Platform-specific default paths
    if sys.platform == "darwin":  # macOS
        candidates = [
            "/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli",
            "/Applications/KiCad 9.0/KiCad.app/Contents/MacOS/kicad-cli",
        ]
    elif sys.platform == "win32":  # Windows
        candidates = [
            r"C:\Program Files\KiCad\9.0\bin\kicad-cli.exe",
            r"C:\Program Files\KiCad\8.0\bin\kicad-cli.exe",
            r"C:\Program Files (x86)\KiCad\9.0\bin\kicad-cli.exe",
        ]
    else:  # Linux
        candidates = [
            "/usr/bin/kicad-cli",
            "/usr/local/bin/kicad-cli",
            "/snap/bin/kicad-cli",
        ]

    # Check platform-specific paths first
    for path in candidates:
        if Path(path).exists():
            logger.debug(f"Found KiCad CLI at: {path}")
            return path

    # Fall back to PATH search
    kicad_cli = shutil.which("kicad-cli")
    if kicad_cli:
        logger.debug(f"Found KiCad CLI in PATH: {kicad_cli}")
        return kicad_cli

    logger.warning("KiCad CLI not found")
    return None


class KiCadPreviewRenderer:
    """Renders symbols and footprints using KiCad's native rendering"""

    # Preview image settings
    IMAGE_SIZE = (400, 400)
    BACKGROUND_COLOR = (255, 255, 255)  # White

    def __init__(self):
        self.logger = get_logger("kicad_preview")
        self.symbol_converter = SymbolConverter()
        self.footprint_converter = FootprintConverter()
        self.kicad_cli = _find_kicad_cli()

    def render_symbol(self, easyeda_data: Dict[str, Any], component_info: Dict[str, Any]) -> Optional[wx.Bitmap]:
        """
        Render symbol using KiCad's native rendering

        Args:
            easyeda_data: Complete EasyEDA API response
            component_info: Component metadata

        Returns:
            wx.Bitmap for display, or None if rendering fails
        """
        try:
            self.logger.debug("Rendering symbol with KiCad CLI")

            # Check if KiCad CLI is available
            if not self.kicad_cli:
                return self._create_placeholder("KiCad CLI not found")

            # Create temporary directory
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)

                # Generate symbol file
                symbol_content = self.symbol_converter.convert(easyeda_data, component_info)
                symbol_lib_file = temp_path / "temp.kicad_sym"
                symbol_lib_file.write_text(symbol_content, encoding='utf-8')

                # Export to SVG using KiCad CLI
                svg_output = temp_path / "output"
                svg_output.mkdir(exist_ok=True)

                result = subprocess.run(
                    [
                        self.kicad_cli,
                        "sym", "export", "svg",
                        "--output", str(svg_output),
                        "--black-and-white",
                        str(symbol_lib_file)
                    ],
                    capture_output=True,
                    text=True,
                    timeout=10
                )

                if result.returncode != 0:
                    self.logger.error(f"KiCad CLI failed: {result.stderr}")
                    return self._create_placeholder("KiCad export failed")

                # Find generated SVG file
                svg_files = list(svg_output.glob("*.svg"))
                if not svg_files:
                    self.logger.warning("No SVG file generated")
                    return self._create_placeholder("No output generated")

                # Convert SVG to bitmap (symbol with high quality)
                return self._svg_to_bitmap(svg_files[0], scale=5.0, is_footprint=False)

        except subprocess.TimeoutExpired:
            self.logger.error("KiCad CLI timeout")
            return self._create_placeholder("Render timeout")
        except Exception as e:
            self.logger.error(f"Symbol rendering failed: {e}", exc_info=True)
            return self._create_placeholder("Render error")

    def render_footprint(self, easyeda_data: Dict[str, Any], component_info: Dict[str, Any]) -> Optional[wx.Bitmap]:
        """
        Render footprint using KiCad's native rendering

        Args:
            easyeda_data: Complete EasyEDA API response
            component_info: Component metadata

        Returns:
            wx.Bitmap for display, or None if rendering fails
        """
        try:
            self.logger.debug("Rendering footprint with KiCad CLI")

            # Check if KiCad CLI is available
            if not self.kicad_cli:
                return self._create_placeholder("KiCad CLI not found")

            # Create temporary directory
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)

                # Create footprint library directory
                fp_lib_dir = temp_path / "temp.pretty"
                fp_lib_dir.mkdir(exist_ok=True)

                # Generate footprint file
                footprint_content = self.footprint_converter.convert(easyeda_data, component_info)
                footprint_name = component_info.get("package", "footprint")
                fp_file = fp_lib_dir / f"{footprint_name}.kicad_mod"
                fp_file.write_text(footprint_content, encoding='utf-8')

                # Export to SVG using KiCad CLI
                svg_output = temp_path / "output"
                svg_output.mkdir(exist_ok=True)

                result = subprocess.run(
                    [
                        self.kicad_cli,
                        "fp", "export", "svg",
                        "--output", str(svg_output),
                        "--layers", "F.Cu,F.SilkS,F.Fab",
                        "--black-and-white",
                        str(fp_lib_dir)
                    ],
                    capture_output=True,
                    text=True,
                    timeout=10
                )

                if result.returncode != 0:
                    self.logger.error(f"KiCad CLI failed: {result.stderr}")
                    return self._create_placeholder("KiCad export failed")

                # Find generated SVG file
                svg_files = list(svg_output.glob("*.svg"))
                if not svg_files:
                    self.logger.warning("No SVG file generated")
                    return self._create_placeholder("No output generated")

                # Convert SVG to bitmap (footprint with higher zoom)
                return self._svg_to_bitmap(svg_files[0], scale=5.0, is_footprint=True)

        except subprocess.TimeoutExpired:
            self.logger.error("KiCad CLI timeout")
            return self._create_placeholder("Render timeout")
        except Exception as e:
            self.logger.error(f"Footprint rendering failed: {e}", exc_info=True)
            return self._create_placeholder("Render error")

    def _svg_to_bitmap(self, svg_path: Path, scale: float = 5.0, is_footprint: bool = False) -> wx.Bitmap:
        """
        Convert SVG file to wx.Bitmap with high quality

        Tries renderers in order:
        1. wx.svg.SVGimage (built-in, no extra deps)
        2. cairosvg (if installed)
        3. Placeholder with error message

        Args:
            svg_path: Path to SVG file
            scale: Scale factor for higher resolution
            is_footprint: If True, apply additional zoom for footprints

        Returns:
            wx.Bitmap
        """
        # Try wx.svg first (available in wxPython 4.1+, bundled with KiCad)
        try:
            return self._svg_to_bitmap_wx(svg_path, is_footprint)
        except Exception as e:
            self.logger.debug(f"wx.svg rendering failed: {e}")

        # Try cairosvg
        try:
            return self._svg_to_bitmap_cairosvg(svg_path, scale, is_footprint)
        except ImportError:
            self.logger.debug("cairosvg not available")
        except Exception as e:
            self.logger.debug(f"cairosvg rendering failed: {e}")

        self.logger.error("All SVG renderers failed")
        return self._create_placeholder("SVG rendering failed")

    def _svg_to_bitmap_wx(self, svg_path: Path, is_footprint: bool = False) -> wx.Bitmap:
        """
        Convert SVG to wx.Bitmap using wx.svg.SVGimage (built-in).

        Handles alpha channel by compositing onto white background.

        Raises:
            Exception: If rendering fails
        """
        from wx.svg import SVGimage

        svg_img = SVGimage.CreateFromFile(str(svg_path))
        if svg_img.width <= 0 or svg_img.height <= 0:
            raise RuntimeError("SVGimage failed to load SVG")

        # Render at high resolution then scale down for quality
        render_width = int(self.IMAGE_SIZE[0] * 2)
        render_height = int(self.IMAGE_SIZE[1] * 2)

        bmp = svg_img.ConvertToScaledBitmap(wx.Size(render_width, render_height))

        # Convert to PIL, handling alpha channel
        wx_img = bmp.ConvertToImage()
        width, height = wx_img.GetWidth(), wx_img.GetHeight()
        rgb_data = bytes(wx_img.GetData())

        if wx_img.HasAlpha():
            # SVG renders with transparency - composite onto white
            alpha_data = bytes(wx_img.GetAlpha())
            pil_rgb = Image.frombytes('RGB', (width, height), rgb_data)
            pil_alpha = Image.frombytes('L', (width, height), alpha_data)
            pil_rgba = pil_rgb.copy()
            pil_rgba.putalpha(pil_alpha)
            pil_image = Image.new('RGB', (width, height), self.BACKGROUND_COLOR)
            pil_image.paste(pil_rgba, mask=pil_alpha)
            self.logger.debug(f"SVG rendered with alpha: {width}x{height}")
        else:
            pil_image = Image.frombytes('RGB', (width, height), rgb_data)
            self.logger.debug(f"SVG rendered without alpha: {width}x{height}")

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

    def _svg_to_bitmap_cairosvg(self, svg_path: Path, scale: float = 5.0, is_footprint: bool = False) -> wx.Bitmap:
        """
        Convert SVG to wx.Bitmap using cairosvg.

        Raises:
            ImportError: If cairosvg is not installed
            Exception: If rendering fails
        """
        import cairosvg
        import xml.etree.ElementTree as ET
        from PIL import ImageFilter, ImageEnhance

        # Parse SVG to get viewBox for intelligent scaling
        tree = ET.parse(svg_path)
        root = tree.getroot()
        viewbox = root.get('viewBox')

        if viewbox and is_footprint:
            parts = viewbox.split()
            if len(parts) == 4:
                svg_width = float(parts[2])
                svg_height = float(parts[3])
                max_dim = max(svg_width, svg_height)
                if max_dim > 1000:
                    scale = scale * 2.0
                self.logger.debug(f"Footprint SVG size: {svg_width}x{svg_height}, scale: {scale}")

        output_width = int(self.IMAGE_SIZE[0] * scale)
        output_height = int(self.IMAGE_SIZE[1] * scale)

        png_data = cairosvg.svg2png(
            url=str(svg_path),
            output_width=output_width,
            output_height=output_height
        )
        pil_image = Image.open(io.BytesIO(png_data))

        # Crop to content for footprints
        if is_footprint:
            bbox = pil_image.convert('L').getbbox()
            if bbox:
                margin = int(20 * scale)
                bbox = (
                    max(0, bbox[0] - margin),
                    max(0, bbox[1] - margin),
                    min(pil_image.width, bbox[2] + margin),
                    min(pil_image.height, bbox[3] + margin)
                )
                pil_image = pil_image.crop(bbox)

        pil_image.thumbnail(self.IMAGE_SIZE, Image.Resampling.LANCZOS)
        pil_image = pil_image.filter(ImageFilter.SHARPEN)
        enhancer = ImageEnhance.Contrast(pil_image)
        pil_image = enhancer.enhance(1.1)

        # Handle RGBA
        if pil_image.mode == 'RGBA':
            bg = Image.new('RGB', pil_image.size, self.BACKGROUND_COLOR)
            bg.paste(pil_image, mask=pil_image.split()[3])
            pil_image = bg
        elif pil_image.mode != 'RGB':
            pil_image = pil_image.convert('RGB')

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
