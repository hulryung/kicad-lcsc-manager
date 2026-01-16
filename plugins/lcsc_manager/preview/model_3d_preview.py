"""
3D Model Preview Handler

Downloads and displays 3D model thumbnails from EasyEDA.
"""
from typing import Dict, Any, Optional
from PIL import Image, ImageDraw
import io
import requests
import wx
from ..utils.logger import get_logger

logger = get_logger()


class Model3DPreviewRenderer:
    """Handles 3D model thumbnail display"""

    # Preview image settings
    IMAGE_SIZE = (400, 400)
    BACKGROUND_COLOR = (50, 50, 50)  # Dark gray

    def __init__(self):
        self.logger = get_logger("model_3d_preview")

    def render(self, easyeda_data: Dict[str, Any]) -> Optional[wx.Bitmap]:
        """
        Download and display 3D model thumbnail

        Args:
            easyeda_data: Complete EasyEDA API response

        Returns:
            wx.Bitmap for display, or None if not available
        """
        try:
            self.logger.debug(f"3D model render called, data keys: {list(easyeda_data.keys())}")

            # Try to get thumbnail URL from EasyEDA response
            thumb_url = easyeda_data.get("thumb")
            self.logger.debug(f"Main thumb URL: {thumb_url}")

            if not thumb_url:
                # Try packageDetail if main response doesn't have it
                package_detail = easyeda_data.get("packageDetail", {})
                thumb_url = package_detail.get("thumb")
                self.logger.debug(f"PackageDetail thumb URL: {thumb_url}")

            if not thumb_url:
                self.logger.debug("No 3D model thumbnail URL found")
                return self._create_placeholder("3D model available\n(No preview)")

            # Convert relative URL to absolute URL
            if thumb_url.startswith("/"):
                self.logger.debug(f"Converting relative URL to absolute: {thumb_url}")
                thumb_url = "https://easyeda.com" + thumb_url
                self.logger.debug(f"Absolute URL: {thumb_url}")

            # Download thumbnail
            return self._download_thumbnail(thumb_url)

        except Exception as e:
            self.logger.error(f"3D model preview failed: {e}", exc_info=True)
            return self._create_placeholder("Preview unavailable")

    def _download_thumbnail(self, url: str) -> wx.Bitmap:
        """Download thumbnail image from URL"""
        try:
            self.logger.debug(f"Downloading 3D thumbnail: {url}")

            # Download image
            response = requests.get(url, timeout=10)
            response.raise_for_status()

            # Load image with PIL
            image_data = io.BytesIO(response.content)
            pil_image = Image.open(image_data)

            # Resize to fit preview size while maintaining aspect ratio
            pil_image.thumbnail(self.IMAGE_SIZE, Image.Resampling.LANCZOS)

            # Create centered image on background
            final_image = Image.new('RGB', self.IMAGE_SIZE, self.BACKGROUND_COLOR)
            offset = (
                (self.IMAGE_SIZE[0] - pil_image.size[0]) // 2,
                (self.IMAGE_SIZE[1] - pil_image.size[1]) // 2
            )
            final_image.paste(pil_image, offset)

            # Convert to wx.Bitmap
            return self._pil_to_wx_bitmap(final_image)

        except requests.RequestException as e:
            self.logger.warning(f"Failed to download thumbnail: {e}")
            return self._create_placeholder("Download failed")
        except Exception as e:
            self.logger.error(f"Failed to process thumbnail: {e}")
            return self._create_placeholder("Processing failed")

    def _create_placeholder(self, message: str) -> wx.Bitmap:
        """Create a placeholder image with message"""
        img = Image.new('RGB', self.IMAGE_SIZE, self.BACKGROUND_COLOR)
        draw = ImageDraw.Draw(img)

        # Draw 3D box icon (simple representation)
        box_size = 100
        center_x = self.IMAGE_SIZE[0] // 2
        center_y = self.IMAGE_SIZE[1] // 2 - 30

        # Draw simple 3D box
        color = (150, 150, 150)

        # Front face
        draw.polygon([
            (center_x - box_size//2, center_y),
            (center_x + box_size//2, center_y),
            (center_x + box_size//2, center_y + box_size),
            (center_x - box_size//2, center_y + box_size)
        ], outline=color, width=2)

        # Top face (isometric)
        draw.polygon([
            (center_x - box_size//2, center_y),
            (center_x, center_y - box_size//4),
            (center_x + box_size//2 + box_size//4, center_y - box_size//4),
            (center_x + box_size//2, center_y)
        ], outline=color, width=2)

        # Right face (isometric)
        draw.polygon([
            (center_x + box_size//2, center_y),
            (center_x + box_size//2 + box_size//4, center_y - box_size//4),
            (center_x + box_size//2 + box_size//4, center_y + box_size - box_size//4),
            (center_x + box_size//2, center_y + box_size)
        ], outline=color, width=2)

        # Draw text
        text = f"3D Model\n{message}"
        draw.text((center_x, center_y + box_size + 40), text,
                 fill=(180, 180, 180), anchor="mm")

        return self._pil_to_wx_bitmap(img)

    def _pil_to_wx_bitmap(self, pil_image):
        """Convert PIL Image to wx.Bitmap"""
        buf = io.BytesIO()
        pil_image.save(buf, format='PNG')
        buf.seek(0)

        wx_image = wx.Image(buf, wx.BITMAP_TYPE_PNG)
        return wx.Bitmap(wx_image)
