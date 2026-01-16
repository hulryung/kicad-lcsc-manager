"""
Symbol Preview Renderer

Renders EasyEDA symbol data to 2D bitmap for preview display.
"""
from typing import Dict, Any, Optional
from PIL import Image, ImageDraw, ImageFont
import io
import wx
from ..utils.logger import get_logger

logger = get_logger()


class SymbolPreviewRenderer:
    """Renders EasyEDA symbols to 2D images"""

    # Preview image settings
    IMAGE_SIZE = (400, 400)
    BACKGROUND_COLOR = (255, 255, 255)  # White
    LINE_COLOR = (0, 0, 0)  # Black
    PIN_COLOR = (200, 0, 0)  # Red
    FILL_COLOR = (240, 240, 240)  # Light gray

    def __init__(self):
        self.logger = get_logger("symbol_preview")

    def render(self, easyeda_data: Dict[str, Any]) -> Optional[wx.Bitmap]:
        """
        Render EasyEDA symbol data to wx.Bitmap

        Args:
            easyeda_data: Complete EasyEDA API response with symbol data

        Returns:
            wx.Bitmap for display, or None if rendering fails
        """
        try:
            self.logger.debug(f"Symbol render called, data keys: {list(easyeda_data.keys())}")

            # Extract symbol shape data
            if "dataStr" not in easyeda_data:
                self.logger.warning(f"No 'dataStr' in EasyEDA response. Available keys: {list(easyeda_data.keys())}")
                return self._create_placeholder("No symbol data")

            data_str = easyeda_data["dataStr"]
            self.logger.debug(f"dataStr type: {type(data_str)}, keys: {list(data_str.keys()) if isinstance(data_str, dict) else 'not a dict'}")

            if "shape" not in data_str:
                self.logger.warning(f"No 'shape' in dataStr. Available keys: {list(data_str.keys())}")
                return self._create_placeholder("No symbol data")

            shape_array = data_str["shape"]
            self.logger.debug(f"Shape array type: {type(shape_array)}, length: {len(shape_array) if isinstance(shape_array, list) else 'not a list'}")
            if isinstance(shape_array, list) and len(shape_array) > 0:
                self.logger.debug(f"First shape element: {shape_array[0][:100] if len(shape_array[0]) > 100 else shape_array[0]}")

            head = data_str.get("head", {})
            translation = (float(head.get("x", 0)), float(head.get("y", 0)))

            # Parse shapes and calculate bounds
            shapes = self._parse_shapes(shape_array, translation)
            self.logger.debug(f"Parsed {len(shapes)} shapes from {len(shape_array)} elements")

            if not shapes:
                self.logger.warning(f"No shapes parsed from {len(shape_array)} shape elements")
                return self._create_placeholder("Empty symbol")

            # Render to PIL image
            pil_image = self._render_shapes(shapes)

            # Convert to wx.Bitmap
            return self._pil_to_wx_bitmap(pil_image)

        except Exception as e:
            self.logger.error(f"Symbol preview rendering failed: {e}", exc_info=True)
            return self._create_placeholder("Render error")

    def _parse_shapes(self, shape_array, translation):
        """Parse EasyEDA shape elements into drawing commands"""
        shapes = []

        for line in shape_array:
            try:
                args = line.split("~")
                if not args:
                    continue

                shape_type = args[0]

                # Parse different shape types
                if shape_type == "R":  # Rectangle
                    shapes.append(self._parse_rectangle(args[1:], translation))
                elif shape_type == "E":  # Ellipse/Circle
                    shapes.append(self._parse_ellipse(args[1:], translation))
                elif shape_type == "P":  # Pin
                    shapes.append(self._parse_pin(args[1:], translation))
                elif shape_type == "PL":  # Polyline
                    shapes.append(self._parse_polyline(args[1:], translation))
                elif shape_type == "PG":  # Polygon
                    shapes.append(self._parse_polygon(args[1:], translation))
                # Add more types as needed

            except Exception as e:
                self.logger.debug(f"Failed to parse shape {shape_type}: {e}")
                continue

        return [s for s in shapes if s is not None]

    def _parse_rectangle(self, args, translation):
        """Parse rectangle: x, y, width, height, stroke_color, fill_color"""
        if len(args) < 4:
            return None

        try:
            x = self._mil_to_px(float(args[0]) - translation[0])
            y = self._mil_to_px(float(args[1]) - translation[1])
            width = self._mil_to_px(float(args[2]))
            height = self._mil_to_px(float(args[3]))

            return {
                'type': 'rectangle',
                'coords': (x, y, x + width, y + height),
                'fill': len(args) > 8 and args[8] != 'none'
            }
        except (ValueError, IndexError):
            return None

    def _parse_ellipse(self, args, translation):
        """Parse ellipse: cx, cy, rx, ry"""
        if len(args) < 4:
            return None

        try:
            cx = self._mil_to_px(float(args[0]) - translation[0])
            cy = self._mil_to_px(float(args[1]) - translation[1])
            rx = self._mil_to_px(float(args[2]))
            ry = self._mil_to_px(float(args[3]))

            return {
                'type': 'ellipse',
                'coords': (cx - rx, cy - ry, cx + rx, cy + ry),
                'fill': False
            }
        except (ValueError, IndexError):
            return None

    def _parse_pin(self, args, translation):
        """Parse pin: x, y, rotation, pin_type, pin_name, pin_number"""
        if len(args) < 2:
            return None

        try:
            x = self._mil_to_px(float(args[0]) - translation[0])
            y = self._mil_to_px(float(args[1]) - translation[1])
            rotation = float(args[2]) if len(args) > 2 else 0

            # Pin is drawn as a line
            length = 40  # pixels
            if rotation == 0:  # Right
                coords = (x, y, x + length, y)
            elif rotation == 90:  # Down
                coords = (x, y, x, y + length)
            elif rotation == 180:  # Left
                coords = (x, y, x - length, y)
            else:  # Up
                coords = (x, y, x, y - length)

            return {
                'type': 'pin',
                'coords': coords
            }
        except (ValueError, IndexError):
            return None

    def _parse_polyline(self, args, translation):
        """Parse polyline: points"""
        if len(args) < 1:
            return None

        try:
            points_str = args[0]
            points = []
            coords = points_str.split()

            for i in range(0, len(coords), 2):
                if i + 1 < len(coords):
                    x = self._mil_to_px(float(coords[i]) - translation[0])
                    y = self._mil_to_px(float(coords[i + 1]) - translation[1])
                    points.append((x, y))

            if len(points) < 2:
                return None

            return {
                'type': 'polyline',
                'points': points
            }
        except (ValueError, IndexError):
            return None

    def _parse_polygon(self, args, translation):
        """Parse polygon: points (similar to polyline but closed)"""
        result = self._parse_polyline(args, translation)
        if result:
            result['type'] = 'polygon'
            result['fill'] = True
        return result

    def _mil_to_px(self, mil_value):
        """Convert mils to pixels for preview (simplified scaling)"""
        # EasyEDA uses mils, scale to fit 400x400 preview
        # Assuming typical symbol is ~1000 mils, scale to ~200px
        return mil_value * 0.2

    def _render_shapes(self, shapes):
        """Render parsed shapes to PIL image"""
        # Create image
        img = Image.new('RGB', self.IMAGE_SIZE, self.BACKGROUND_COLOR)
        draw = ImageDraw.Draw(img)

        # Calculate bounds for centering
        if shapes:
            all_coords = []
            for shape in shapes:
                if 'coords' in shape:
                    all_coords.extend([shape['coords'][0], shape['coords'][2]])
                    all_coords.extend([shape['coords'][1], shape['coords'][3]])
                elif 'points' in shape:
                    for point in shape['points']:
                        all_coords.extend([point[0], point[1]])

            if all_coords:
                min_x = min(all_coords[::2])
                max_x = max(all_coords[::2])
                min_y = min(all_coords[1::2])
                max_y = max(all_coords[1::2])

                # Center offset
                width = max_x - min_x
                height = max_y - min_y
                offset_x = (self.IMAGE_SIZE[0] - width) / 2 - min_x
                offset_y = (self.IMAGE_SIZE[1] - height) / 2 - min_y
            else:
                offset_x, offset_y = 0, 0
        else:
            offset_x, offset_y = 0, 0

        # Draw shapes
        for shape in shapes:
            shape_type = shape.get('type')

            if shape_type == 'rectangle':
                coords = self._offset_coords(shape['coords'], offset_x, offset_y)
                if shape.get('fill'):
                    draw.rectangle(coords, fill=self.FILL_COLOR, outline=self.LINE_COLOR, width=2)
                else:
                    draw.rectangle(coords, outline=self.LINE_COLOR, width=2)

            elif shape_type == 'ellipse':
                coords = self._offset_coords(shape['coords'], offset_x, offset_y)
                draw.ellipse(coords, outline=self.LINE_COLOR, width=2)

            elif shape_type == 'pin':
                coords = self._offset_coords(shape['coords'], offset_x, offset_y)
                draw.line(coords, fill=self.PIN_COLOR, width=3)

            elif shape_type == 'polyline':
                points = [(p[0] + offset_x, p[1] + offset_y) for p in shape['points']]
                draw.line(points, fill=self.LINE_COLOR, width=2)

            elif shape_type == 'polygon':
                points = [(p[0] + offset_x, p[1] + offset_y) for p in shape['points']]
                if shape.get('fill'):
                    draw.polygon(points, fill=self.FILL_COLOR, outline=self.LINE_COLOR)
                else:
                    draw.polygon(points, outline=self.LINE_COLOR)

        return img

    def _offset_coords(self, coords, offset_x, offset_y):
        """Apply offset to coordinates"""
        if len(coords) == 4:
            return (
                coords[0] + offset_x,
                coords[1] + offset_y,
                coords[2] + offset_x,
                coords[3] + offset_y
            )
        return coords

    def _create_placeholder(self, message: str) -> wx.Bitmap:
        """Create a placeholder image with message"""
        img = Image.new('RGB', self.IMAGE_SIZE, self.BACKGROUND_COLOR)
        draw = ImageDraw.Draw(img)

        # Draw border
        draw.rectangle([10, 10, self.IMAGE_SIZE[0]-10, self.IMAGE_SIZE[1]-10],
                      outline=(200, 200, 200), width=2)

        # Draw text
        text = f"Symbol Preview\n{message}"
        draw.text((self.IMAGE_SIZE[0]//2, self.IMAGE_SIZE[1]//2), text,
                 fill=(150, 150, 150), anchor="mm")

        return self._pil_to_wx_bitmap(img)

    def _pil_to_wx_bitmap(self, pil_image):
        """Convert PIL Image to wx.Bitmap"""
        # Convert PIL image to bytes
        buf = io.BytesIO()
        pil_image.save(buf, format='PNG')
        buf.seek(0)

        # Create wx.Image from bytes
        wx_image = wx.Image(buf, wx.BITMAP_TYPE_PNG)

        # Convert to bitmap
        return wx.Bitmap(wx_image)
