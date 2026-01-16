"""
KiCad Native Preview Renderer

Uses KiCad's CLI tools to render symbols and footprints natively.
"""
from typing import Dict, Any, Optional
from pathlib import Path
import tempfile
import subprocess
import io
import wx
from PIL import Image
from ..utils.logger import get_logger
from ..converters.symbol_converter import SymbolConverter
from ..converters.footprint_converter import FootprintConverter

logger = get_logger()


class KiCadPreviewRenderer:
    """Renders symbols and footprints using KiCad's native rendering"""

    # Preview image settings
    IMAGE_SIZE = (400, 400)
    BACKGROUND_COLOR = (255, 255, 255)  # White
    KICAD_CLI = "/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli"

    def __init__(self):
        self.logger = get_logger("kicad_preview")
        self.symbol_converter = SymbolConverter()
        self.footprint_converter = FootprintConverter()

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
                        self.KICAD_CLI,
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

                # Convert SVG to bitmap (symbol)
                return self._svg_to_bitmap(svg_files[0], scale=3.0, is_footprint=False)

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
                        self.KICAD_CLI,
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
                return self._svg_to_bitmap(svg_files[0], scale=3.0, is_footprint=True)

        except subprocess.TimeoutExpired:
            self.logger.error("KiCad CLI timeout")
            return self._create_placeholder("Render timeout")
        except Exception as e:
            self.logger.error(f"Footprint rendering failed: {e}", exc_info=True)
            return self._create_placeholder("Render error")

    def _svg_to_bitmap(self, svg_path: Path, scale: float = 3.0, is_footprint: bool = False) -> wx.Bitmap:
        """
        Convert SVG file to wx.Bitmap with high quality

        Args:
            svg_path: Path to SVG file
            scale: Scale factor for higher resolution (default 3.0 for crisp display)
            is_footprint: If True, apply additional zoom for footprints

        Returns:
            wx.Bitmap
        """
        try:
            # Use cairosvg to convert SVG to PNG at high resolution
            try:
                import cairosvg
                import xml.etree.ElementTree as ET

                # Parse SVG to get viewBox for intelligent scaling
                tree = ET.parse(svg_path)
                root = tree.getroot()
                viewbox = root.get('viewBox')

                # Calculate appropriate scale based on SVG dimensions
                if viewbox and is_footprint:
                    # For footprints, apply extra zoom
                    parts = viewbox.split()
                    if len(parts) == 4:
                        svg_width = float(parts[2])
                        svg_height = float(parts[3])
                        # If footprint is very large (large PCB coordinates), zoom in more
                        max_dim = max(svg_width, svg_height)
                        if max_dim > 1000:
                            # Large SVG coordinates, need more zoom
                            scale = scale * 2.0
                        self.logger.debug(f"Footprint SVG size: {svg_width}x{svg_height}, scale: {scale}")

                # Convert to higher resolution for better quality
                output_width = int(self.IMAGE_SIZE[0] * scale)
                output_height = int(self.IMAGE_SIZE[1] * scale)

                png_data = cairosvg.svg2png(
                    url=str(svg_path),
                    output_width=output_width,
                    output_height=output_height
                )
                pil_image = Image.open(io.BytesIO(png_data))

                # Crop to content (remove excess whitespace) for footprints
                if is_footprint:
                    # Convert to grayscale to find content bounds
                    bbox = pil_image.convert('L').getbbox()
                    if bbox:
                        # Add small margin
                        margin = int(20 * scale)
                        bbox = (
                            max(0, bbox[0] - margin),
                            max(0, bbox[1] - margin),
                            min(pil_image.width, bbox[2] + margin),
                            min(pil_image.height, bbox[3] + margin)
                        )
                        pil_image = pil_image.crop(bbox)
                        self.logger.debug(f"Cropped footprint to: {pil_image.size}")

                # Scale to fit display size
                pil_image.thumbnail(self.IMAGE_SIZE, Image.Resampling.LANCZOS)

            except ImportError:
                self.logger.warning("cairosvg not available, using PIL SVG fallback")
                # Try PIL directly (limited SVG support)
                pil_image = Image.open(svg_path)
                # Resize to fit preview size
                pil_image.thumbnail(self.IMAGE_SIZE, Image.Resampling.LANCZOS)

            # Handle RGBA images
            if pil_image.mode == 'RGBA':
                # Create white background
                bg = Image.new('RGB', pil_image.size, self.BACKGROUND_COLOR)
                bg.paste(pil_image, mask=pil_image.split()[3])  # Alpha channel as mask
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

            # Convert to wx.Bitmap
            return self._pil_to_wx_bitmap(final_image)

        except Exception as e:
            self.logger.error(f"SVG conversion failed: {e}", exc_info=True)
            return self._create_placeholder("Image conversion failed")

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
