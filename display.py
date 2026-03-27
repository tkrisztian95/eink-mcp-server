import logging
import os
from typing import Optional

log = logging.getLogger(__name__)

from PIL import Image, ImageDraw, ImageFont

FONT_PATH = os.getenv("EINK_FONT_PATH", "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf")

DISPLAY_WIDTH = 800
DISPLAY_HEIGHT = 480


class EinkDisplay:
    def __init__(self):
        try:
            from waveshare_epd import epd7in5_V2

            self._epd_module = epd7in5_V2
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

    def render(self, elements: list[dict], rotation: int = 0, background: int = 255) -> None:
        if rotation in (90, 270):
            w, h = self.height, self.width
        else:
            w, h = self.width, self.height

        image = Image.new("L", (w, h), background)
        draw = ImageDraw.Draw(image)

        for el in elements:
            _draw_element(draw, el)

        if rotation != 0:
            image = image.rotate(rotation, expand=True)

        if not self._available:
            log.warning("Hardware not available — rendered %d elements (dry run)", len(elements))
            return

        epd = self._epd_module.EPD()
        epd.init()
        epd.display(epd.getbuffer(image.convert("1")))
        epd.sleep()


def _load_font(size: int, path: Optional[str] = None) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(path or FONT_PATH, size)
    except Exception:
        return ImageFont.load_default()


def _draw_element(draw: ImageDraw.ImageDraw, el: dict) -> None:
    t = el.get("type")

    if t == "text":
        font = _load_font(el.get("size", 24), el.get("font"))
        draw.text((el["x"], el["y"]), el["text"], font=font, fill=el.get("fill", 0))

    elif t == "rect":
        fill: Optional[int] = el.get("fill")
        draw.rectangle(
            [el["x0"], el["y0"], el["x1"], el["y1"]],
            outline=el.get("outline", 0),
            fill=fill,
        )

    elif t == "line":
        draw.line(
            [(el["x0"], el["y0"]), (el["x1"], el["y1"])],
            fill=el.get("fill", 0),
            width=el.get("width", 1),
        )

    elif t == "ellipse":
        fill = el.get("fill")
        draw.ellipse(
            [el["x0"], el["y0"], el["x1"], el["y1"]],
            outline=el.get("outline", 0),
            fill=fill,
        )
