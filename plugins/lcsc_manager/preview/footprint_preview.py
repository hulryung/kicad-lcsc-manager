"""
Footprint Preview Renderer

Renders EasyEDA footprint data to 2D bitmap for preview display.
"""
from typing import Dict, Any, Optional
from PIL import Image, ImageDraw
import io
import wx
from ..utils.logger import get_logger

logger = get_logger()


class FootprintPreviewRenderer:
    """Renders EasyEDA footprints to 2D images"""

    # Preview image settings
    IMAGE_SIZE = (400, 400)
    BACKGROUND_COLOR = (40, 40, 40)  # Dark gray (PCB background)

    # Layer colors
    LAYER_COLORS = {
        'pads': (204, 153, 0),       # Copper/gold color
        'silkscreen': (255, 255, 255),  # White
        'fab': (150, 150, 150),      # Gray
        'courtyard': (0, 100, 200),  # Blue
        'track': (204, 153, 0),      # Copper
    }

    def __init__(self):
        self.logger = get_logger("footprint_preview")

    def render(self, easyeda_data: Dict[str, Any]) -> Optional[wx.Bitmap]:
        """
        Render EasyEDA footprint data to wx.Bitmap

        Args:
            easyeda_data: Complete EasyEDA API response with footprint data

        Returns:
            wx.Bitmap for display, or None if rendering fails
        """
        try:
            # Extract footprint shape data
            if "packageDetail" not in easyeda_data:
                self.logger.warning("No packageDetail in EasyEDA response")
                return self._create_placeholder("No footprint data")

            package_detail = easyeda_data["packageDetail"]
            if "dataStr" not in package_detail or "shape" not in package_detail["dataStr"]:
                self.logger.warning("No footprint shape data")
                return self._create_placeholder("No shape data")

            shape_array = package_detail["dataStr"]["shape"]
            head = package_detail["dataStr"].get("head", {})
            translation = (float(head.get("x", 0)), float(head.get("y", 0)))

            # Parse shapes
            shapes = self._parse_shapes(shape_array, translation)
            if not shapes:
                return self._create_placeholder("Empty footprint")

            # Render to PIL image
            pil_image = self._render_shapes(shapes)

            # Convert to wx.Bitmap
            return self._pil_to_wx_bitmap(pil_image)

        except Exception as e:
            self.logger.error(f"Footprint preview rendering failed: {e}", exc_info=True)
            return self._create_placeholder("Render error")

    def _parse_shapes(self, shape_array, translation):
        """Parse EasyEDA footprint shape elements"""
        shapes = []

        for line in shape_array:
            try:
                args = line.split("~")
                if not args:
                    continue

                shape_type = args[0]

                # Parse different footprint element types
                if shape_type == "PAD":
                    shapes.append(self._parse_pad(args[1:], translation))
                elif shape_type == "TRACK":
                    shapes.append(self._parse_track(args[1:], translation))
                elif shape_type == "CIRCLE":
                    shapes.append(self._parse_circle(args[1:], translation))
                elif shape_type == "RECT":
                    shapes.append(self._parse_rect(args[1:], translation))
                elif shape_type == "HOLE":
                    shapes.append(self._parse_hole(args[1:], translation))
                # Add more types as needed

            except Exception as e:
                self.logger.debug(f"Failed to parse footprint shape {shape_type}: {e}")
                continue

        return [s for s in shapes if s is not None]

    def _parse_pad(self, args, translation):
        """Parse pad: shape, x, y, width, height, layer, number, hole_size"""
        if len(args) < 5:
            return None

        try:
            shape = args[0]  # OVAL, RECT, ELLIPSE, POLYGON
            x = self._mil_to_px(float(args[1]) - translation[0])
            y = self._mil_to_px(float(args[2]) - translation[1])
            width = self._mil_to_px(float(args[3]))
            height = self._mil_to_px(float(args[4]))
            layer = args[5] if len(args) > 5 else "1"
            pad_number = args[6] if len(args) > 6 else ""
            hole_size = float(args[7]) if len(args) > 7 else 0

            return {
                'type': 'pad',
                'shape': shape,
                'coords': (x - width/2, y - height/2, x + width/2, y + height/2),
                'hole_size': self._mil_to_px(hole_size) if hole_size > 0 else 0,
                'layer': layer
            }
        except (ValueError, IndexError):
            return None

    def _parse_track(self, args, translation):
        """Parse track/line: width, layer, points"""
        if len(args) < 3:
            return None

        try:
            width = self._mil_to_px(float(args[0]))
            layer = args[1]
            points_str = args[2]

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
                'type': 'track',
                'points': points,
                'width': width,
                'layer': layer
            }
        except (ValueError, IndexError):
            return None

    def _parse_circle(self, args, translation):
        """Parse circle: cx, cy, radius, stroke_width, layer"""
        if len(args) < 3:
            return None

        try:
            cx = self._mil_to_px(float(args[0]) - translation[0])
            cy = self._mil_to_px(float(args[1]) - translation[1])
            radius = self._mil_to_px(float(args[2]))
            width = self._mil_to_px(float(args[3])) if len(args) > 3 else 1
            layer = args[4] if len(args) > 4 else "3"

            return {
                'type': 'circle',
                'coords': (cx - radius, cy - radius, cx + radius, cy + radius),
                'width': width,
                'layer': layer
            }
        except (ValueError, IndexError):
            return None

    def _parse_rect(self, args, translation):
        """Parse rectangle: x, y, width, height, layer"""
        if len(args) < 4:
            return None

        try:
            x = self._mil_to_px(float(args[0]) - translation[0])
            y = self._mil_to_px(float(args[1]) - translation[1])
            width = self._mil_to_px(float(args[2]))
            height = self._mil_to_px(float(args[3]))
            layer = args[4] if len(args) > 4 else "3"

            return {
                'type': 'rect',
                'coords': (x, y, x + width, y + height),
                'layer': layer
            }
        except (ValueError, IndexError):
            return None

    def _parse_hole(self, args, translation):
        """Parse hole: x, y, diameter"""
        if len(args) < 3:
            return None

        try:
            x = self._mil_to_px(float(args[0]) - translation[0])
            y = self._mil_to_px(float(args[1]) - translation[1])
            diameter = self._mil_to_px(float(args[2]))

            return {
                'type': 'hole',
                'coords': (x - diameter/2, y - diameter/2, x + diameter/2, y + diameter/2)
            }
        except (ValueError, IndexError):
            return None

    def _mil_to_px(self, mil_value):
        """Convert mils to pixels for preview (simplified scaling)"""
        # EasyEDA uses mils, scale to fit 400x400 preview
        # Typical footprint is ~500 mils, scale to ~200px
        return mil_value * 0.4

    def _get_layer_color(self, layer_id):
        """Get color for layer"""
        # EasyEDA layer IDs: 1=F.Cu, 2=B.Cu, 3=F.SilkS, etc.
        layer_map = {
            "1": 'pads',  # Front copper
            "2": 'pads',  # Back copper
            "3": 'silkscreen',  # Front silkscreen
            "4": 'silkscreen',  # Back silkscreen
            "12": 'fab',  # Fab layer
        }
        layer_type = layer_map.get(layer_id, 'track')
        return self.LAYER_COLORS.get(layer_type, self.LAYER_COLORS['track'])

    def _render_shapes(self, shapes):
        """Render parsed shapes to PIL image"""
        # Create image with dark background
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

        # Draw shapes (pads first, then silkscreen)
        for shape in sorted(shapes, key=lambda s: 0 if s.get('type') == 'pad' else 1):
            shape_type = shape.get('type')

            if shape_type == 'pad':
                coords = self._offset_coords(shape['coords'], offset_x, offset_y)
                color = self._get_layer_color(shape.get('layer', '1'))

                # Draw pad
                if shape.get('shape') == 'OVAL':
                    draw.ellipse(coords, fill=color)
                else:  # RECT or default
                    draw.rectangle(coords, fill=color)

                # Draw hole if THT
                if shape.get('hole_size', 0) > 0:
                    hole_size = shape['hole_size']
                    cx = (coords[0] + coords[2]) / 2
                    cy = (coords[1] + coords[3]) / 2
                    hole_coords = (cx - hole_size/2, cy - hole_size/2,
                                  cx + hole_size/2, cy + hole_size/2)
                    draw.ellipse(hole_coords, fill=self.BACKGROUND_COLOR)

            elif shape_type == 'track':
                color = self._get_layer_color(shape.get('layer', '3'))
                points = [(p[0] + offset_x, p[1] + offset_y) for p in shape['points']]
                width = max(1, int(shape.get('width', 1)))
                draw.line(points, fill=color, width=width)

            elif shape_type == 'circle':
                coords = self._offset_coords(shape['coords'], offset_x, offset_y)
                color = self._get_layer_color(shape.get('layer', '3'))
                width = max(1, int(shape.get('width', 1)))
                draw.ellipse(coords, outline=color, width=width)

            elif shape_type == 'rect':
                coords = self._offset_coords(shape['coords'], offset_x, offset_y)
                color = self._get_layer_color(shape.get('layer', '3'))
                draw.rectangle(coords, outline=color, width=2)

            elif shape_type == 'hole':
                coords = self._offset_coords(shape['coords'], offset_x, offset_y)
                draw.ellipse(coords, fill=(0, 0, 0))

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
                      outline=(100, 100, 100), width=2)

        # Draw text
        text = f"Footprint Preview\n{message}"
        draw.text((self.IMAGE_SIZE[0]//2, self.IMAGE_SIZE[1]//2), text,
                 fill=(150, 150, 150), anchor="mm")

        return self._pil_to_wx_bitmap(img)

    def _pil_to_wx_bitmap(self, pil_image):
        """Convert PIL Image to wx.Bitmap"""
        buf = io.BytesIO()
        pil_image.save(buf, format='PNG')
        buf.seek(0)

        wx_image = wx.Image(buf, wx.BITMAP_TYPE_PNG)
        return wx.Bitmap(wx_image)
