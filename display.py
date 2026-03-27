import importlib
import io
import logging
import os
from typing import Optional, Union

from PIL import Image, ImageDraw, ImageFont

log = logging.getLogger(__name__)

FONT_PATH = os.getenv("EINK_FONT_PATH", "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf")
FONT_PATH_BOLD = os.getenv(
    "EINK_FONT_PATH_BOLD",
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
)

# Registry of known Waveshare display models → (width, height).
# Add entries here when new models are needed.
DISPLAY_MODELS: dict[str, tuple[int, int]] = {
    "epd7in5_V2": (800, 480),
    "epd7in5_V3": (800, 480),
    "epd7in5": (640, 384),
    "epd5in83_V2": (648, 480),
    "epd4in2": (400, 300),
    "epd4in2_V2": (400, 300),
    "epd2in13_V4": (122, 250),
    "epd2in7": (176, 264),
    "epd1in54_V2": (200, 200),
}

DISPLAY_MODEL = os.getenv("EINK_DISPLAY_MODEL", "epd7in5_V2")
_dims = DISPLAY_MODELS.get(DISPLAY_MODEL)
if _dims is None:
    log.warning("Unknown EINK_DISPLAY_MODEL %r — falling back to 800×480", DISPLAY_MODEL)
    _dims = (800, 480)
DISPLAY_WIDTH, DISPLAY_HEIGHT = _dims

# Named font sizes — match the eink-claude-usage conventions
NAMED_SIZES: dict[str, int] = {
    "title": 34,
    "large": 28,
    "label": 19,
    "value": 17,
    "small": 14,
    "tiny": 12,
}


class EinkDisplay:
    def __init__(self):
        try:
            self._epd_module = importlib.import_module(f"waveshare_epd.{DISPLAY_MODEL}")
            self._available = True
        except Exception:
            self._epd_module = None
            self._available = False

    @property
    def width(self) -> int:
        return DISPLAY_WIDTH

    @property
    def height(self) -> int:
        return DISPLAY_HEIGHT

    def clear(self) -> None:
        if not self._available:
            log.warning("Hardware not available — skipping clear")
            return
        epd = self._epd_module.EPD()
        epd.init()
        epd.Clear()
        epd.sleep()

    def send(self, image: Image.Image) -> None:
        """Send a fully prepared PIL image to the hardware."""
        if not self._available:
            log.warning("Hardware not available — skipping send")
            return
        epd = self._epd_module.EPD()
        epd.init()
        epd.display(epd.getbuffer(image.convert("1")))
        epd.sleep()

    def render(self, elements: list[dict], rotation: int = 0, background: int = 255) -> None:
        if rotation in (90, 270):
            w, h = self.height, self.width
        else:
            w, h = self.width, self.height

        image = Image.new("L", (w, h), background)
        draw = ImageDraw.Draw(image)

        for el in elements:
            _draw_element(draw, el, w, h)

        if rotation != 0:
            image = image.rotate(rotation, expand=True)

        if not self._available:
            log.warning("Hardware not available — rendered %d elements (dry run)", len(elements))
            return
        self.send(image)


def _resolve_size(size: Union[int, str]) -> int:
    if isinstance(size, str):
        return NAMED_SIZES.get(size, 24)
    return size


def _load_font(
    size: Union[int, str], path: Optional[str] = None, bold: bool = False
) -> ImageFont.FreeTypeFont:
    px = _resolve_size(size)
    font_path = path or (FONT_PATH_BOLD if bold else FONT_PATH)
    try:
        return ImageFont.truetype(font_path, px)
    except Exception:
        return ImageFont.load_default()


def _text_size(
    draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont
) -> tuple[int, int]:
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def _draw_element(draw: ImageDraw.ImageDraw, el: dict, canvas_w: int, canvas_h: int) -> None:
    t = el.get("type")

    if t == "text":
        font = _load_font(el.get("size", 24), el.get("font"), el.get("bold", False))
        text = el["text"]
        x, y = el["x"], el["y"]
        align = el.get("align", "left")

        if align in ("center", "right"):
            max_width = el.get("max_width", canvas_w)
            tw, _ = _text_size(draw, text, font)
            if align == "center":
                x = x + (max_width - tw) // 2
            else:
                x = x + max_width - tw

        draw.text((x, y), text, font=font, fill=el.get("fill", 0))

    elif t == "rect":
        draw.rectangle(
            [el["x0"], el["y0"], el["x1"], el["y1"]],
            outline=el.get("outline", 0),
            fill=el.get("fill"),
        )

    elif t == "line":
        draw.line(
            [(el["x0"], el["y0"]), (el["x1"], el["y1"])],
            fill=el.get("fill", 0),
            width=el.get("width", 1),
        )

    elif t == "ellipse":
        draw.ellipse(
            [el["x0"], el["y0"], el["x1"], el["y1"]],
            outline=el.get("outline", 0),
            fill=el.get("fill"),
        )

    elif t == "progress_bar":
        x, y = el["x"], el["y"]
        w, h = el["width"], el.get("height", 12)
        value = max(0.0, min(1.0, el.get("value", 0.0)))
        draw.rectangle(
            [x, y, x + w, y + h], outline=el.get("outline", 100), fill=el.get("background", 240)
        )
        filled = int(w * value)
        if filled > 0:
            draw.rectangle([x, y, x + filled, y + h], fill=el.get("fill", 0))

    elif t == "divider":
        y = el["y"]
        margin = el.get("margin", 20)
        draw.line(
            [(margin, y), (canvas_w - margin, y)],
            fill=el.get("fill", 0),
            width=el.get("width", 1),
        )

    elif t == "image":
        try:
            path = el["path"]
            if path.lower().endswith(".svg"):
                import cairosvg

                target_w, target_h = el.get("width"), el.get("height")
                png_bytes = cairosvg.svg2png(
                    url=path,
                    output_width=target_w,
                    output_height=target_h,
                )
                img = Image.open(io.BytesIO(png_bytes)).convert("L")
                draw._image.paste(img, (el.get("x", 0), el.get("y", 0)))
                return
            img = Image.open(path).convert("L")
            target_w, target_h = el.get("width"), el.get("height")
            if target_w or target_h:
                orig_w, orig_h = img.size
                if target_w and target_h:
                    img = img.resize((target_w, target_h), Image.LANCZOS)
                elif target_w:
                    img = img.resize((target_w, int(orig_h * target_w / orig_w)), Image.LANCZOS)
                else:
                    img = img.resize((int(orig_w * target_h / orig_h), target_h), Image.LANCZOS)
            draw._image.paste(img, (el.get("x", 0), el.get("y", 0)))
        except Exception as e:
            log.warning("image element failed: %s", e)
