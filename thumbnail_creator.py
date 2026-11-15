import logging
import os
import random
import re
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ThumbnailCreator")

class ThumbnailCreator:
    def __init__(self):
        self.width = 1280
        self.height = 720
        self.fonts_dir = config.FONTS_DIR

    def get_font(self, font_size: int, text: str = None):
        """
        Searches for an appropriate bold font:
        - If text contains Devanagari Hindi characters, prioritizes verified Devanagari fonts.
        - Otherwise, searches standard bold Latin display fonts, preserving English font behavior.
        - Falls back to default font if no TTF font is found.
        """
        has_devanagari = bool(text and re.search(r'[\u0900-\u097F]', text))

        if has_devanagari:
            devanagari_names = [
                "Noto Sans Devanagari Bold.ttf",
                "Noto Sans Devanagari.ttf",
                "NotoSansDevanagari-Bold.ttf",
                "NotoSansDevanagari-Regular.ttf",
                "Lohit-Devanagari.ttf",
                "Gargi.ttf",
                "gargi.ttf",
                "Nirmala.ttf",
                "NirmalaB.ttf"
            ]
            # 1. Check bundled assets fonts directory first
            for name in devanagari_names:
                asset_path = self.fonts_dir / name
                if asset_path.exists():
                    logger.info(f"Loaded bundled Devanagari font for thumbnail: {name}")
                    return ImageFont.truetype(str(asset_path), font_size)

            # Glob assets directory for any devanagari font
            if self.fonts_dir.exists():
                for f in self.fonts_dir.glob("*.*"):
                    if f.suffix.lower() in [".ttf", ".otf"] and "devanagari" in f.name.lower():
                        logger.info(f"Loaded detected Devanagari font for thumbnail: {f.name}")
                        return ImageFont.truetype(str(f), font_size)

            # 2. Check system Devanagari font paths
            devanagari_system_paths = [
                Path("/usr/share/fonts/truetype/noto"),
                Path("/usr/share/fonts/opentype/noto"),
                Path("/usr/share/fonts/truetype/lohit-devanagari"),
                Path("/usr/share/fonts/truetype/fonts-deva-extra"),
                Path("/usr/share/fonts/truetype"),
                Path("C:/Windows/Fonts")
            ]
            for p in devanagari_system_paths:
                if p.exists():
                    for name in devanagari_names:
                        font_path = p / name
                        if font_path.exists():
                            logger.info(f"Loaded system Devanagari font for thumbnail: {font_path}")
                            return ImageFont.truetype(str(font_path), font_size)
                        for file in p.rglob(name):
                            logger.info(f"Loaded system Devanagari font for thumbnail: {file}")
                            return ImageFont.truetype(str(file), font_size)

        # Standard English / Latin fonts
        font_names = [
            "impact.ttf", "arialbd.ttf", "coopbl.ttf", "trebucbd.ttf", 
            "LiberationSans-Bold.ttf", "DejaVuSans-Bold.ttf"
        ]

        # Check assets fonts first
        for name in font_names:
            asset_path = self.fonts_dir / name
            if asset_path.exists():
                return ImageFont.truetype(str(asset_path), font_size)

        # System font paths
        paths = []
        if os.name == "nt":
            paths = [Path("C:/Windows/Fonts")]
        else:
            paths = [
                Path("/usr/share/fonts/truetype"),
                Path("/usr/share/fonts/TTF"),
                Path("/usr/share/fonts/truetype/dejavu"),
                Path("/usr/share/fonts/truetype/liberation")
            ]

        for path in paths:
            if path.exists():
                for name in font_names:
                    font_path = path / name
                    if font_path.exists():
                        return ImageFont.truetype(str(font_path), font_size)
                    # Recursive search
                    for file in path.rglob(name):
                        return ImageFont.truetype(str(file), font_size)

        # Ultimate fallback
        logger.warning("No TTF fonts found. Using default low-resolution font.")
        return ImageFont.load_default()

    def create_gradient_background(self) -> Image.Image:
        """Creates a beautiful dark-to-vibrant gradient image."""
        img = Image.new("RGB", (self.width, self.height))
        draw = ImageDraw.Draw(img)
        
        # Select random nice gradient colors
        gradients = [
            ((15, 12, 75), (253, 29, 29)),    # Dark Blue to Red
            ((18, 18, 18), (33, 150, 243)),   # Black to Neon Blue
            ((44, 62, 80), (253, 116, 108)),  # Dark Gray to Pinkish-Orange
            ((0, 0, 0), (142, 68, 173))       # Black to Purple
        ]
        c1, c2 = random.choice(gradients)
        
        for y in range(self.height):
            # Interpolate colors
            r = int(c1[0] + (c2[0] - c1[0]) * (y / self.height))
            g = int(c1[1] + (c2[1] - c1[1]) * (y / self.height))
            b = int(c1[2] + (c2[2] - c1[2]) * (y / self.height))
            draw.line([(0, y), (self.width, y)], fill=(r, g, b))
            
        return img

    def draw_text_with_outline(self, draw: ImageDraw.ImageDraw, text: str, position: tuple, font, fill_color: str, outline_color: str = "black", outline_width: int = 5):
        """Draws text with a thick black outline for maximum readability."""
        x, y = position
        # Draw outline by drawing text offset in 8 directions
        for dx in range(-outline_width, outline_width + 1):
            for dy in range(-outline_width, outline_width + 1):
                if dx != 0 or dy != 0:
                    draw.text((x + dx, y + dy), text, font=font, fill=outline_color)
        # Draw main text
        draw.text((x, y), text, font=font, fill=fill_color)

    def generate_thumbnail(self, title: str, background_image_path: Path, output_path: Path) -> bool:
        """
        Generates a high-contrast thumbnail.
        If a background image path is provided, it is resized, blurred/darkened,
        and used as background. Otherwise, a gradient background is generated.
        """
        try:
            logger.info(f"Generating thumbnail to: {output_path}")
            
            # 1. Background Setup
            if background_image_path and background_image_path.exists():
                try:
                    img = Image.open(background_image_path)
                    img = img.resize((self.width, self.height), Image.Resampling.LANCZOS)
                    # Apply a light blur and darken filter to keep text readable
                    img = img.filter(ImageFilter.GaussianBlur(radius=3))
                    darken = Image.new("RGB", (self.width, self.height), (0, 0, 0))
                    img = Image.blend(img, darken, alpha=0.3)
                except Exception as e:
                    logger.error(f"Failed to load background image: {e}. Falling back to gradient.")
                    img = self.create_gradient_background()
            else:
                img = self.create_gradient_background()
                
            draw = ImageDraw.Draw(img)
            
            # 2. Text Setup & Wrapping
            font = self.get_font(80, text=title) # Big bold font size

            # Split title into lines for readability
            words = title.split()
            if len(words) <= 1:
                line1 = title
                line2 = ""
            else:
                mid = max(1, len(words) // 2)
                line1 = " ".join(words[:mid])
                line2 = " ".join(words[mid:])

            # Font metrics (handle differences in Pillow versions)
            try:
                l1_w = draw.textlength(line1, font=font)
                l2_w = draw.textlength(line2, font=font) if line2 else 0
            except AttributeError:
                # Fallback for older Pillow versions
                l1_w, _ = draw.textsize(line1, font=font)
                l2_w, _ = draw.textsize(line2, font=font) if line2 else (0, 0)

            if line2:
                # Draw Line 1 (Yellow / High Contrast)
                y1 = int(self.height * 0.35)
                x1 = int((self.width - l1_w) / 2)
                self.draw_text_with_outline(draw, line1, (x1, y1), font, "yellow", outline_width=6)

                # Draw Line 2 (White)
                y2 = int(self.height * 0.55)
                x2 = int((self.width - l2_w) / 2)
                self.draw_text_with_outline(draw, line2, (x2, y2), font, "white", outline_width=6)
            else:
                # Single line centered vertically
                y1 = int(self.height * 0.45)
                x1 = int((self.width - l1_w) / 2)
                self.draw_text_with_outline(draw, line1, (x1, y1), font, "yellow", outline_width=6)
            
            # 3. Save Thumbnail
            img.save(output_path, "JPEG")
            logger.info("Thumbnail generation successful.")
            return True
            
        except Exception as e:
            logger.error(f"Error creating thumbnail: {e}")
            return False

if __name__ == "__main__":
    tc = ThumbnailCreator()
    test_out = Path("temp") / "test_thumb.jpg"
    test_out.parent.mkdir(exist_ok=True)
    tc.generate_thumbnail("MINDBLOWING FACTS YOU DIDNT KNOW", None, test_out)
