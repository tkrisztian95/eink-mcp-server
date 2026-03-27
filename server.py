import logging
import sys
from typing import Annotated, Literal, Optional, Union

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from display import EinkDisplay, NAMED_SIZES

logging.basicConfig(stream=sys.stderr, level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

mcp = FastMCP("eink-display")
_display = EinkDisplay()
log.info("eink-display MCP server started (display available: %s)", _display._available)


# ── Drawing element models ────────────────────────────────────────────────────


class TextElement(BaseModel):
    type: Literal["text"]
    text: str
    x: int
    y: int
    size: Union[int, str] = 24
    """Pixel size or named size: title(34), large(28), label(19), value(17), small(14), tiny(12)"""
    bold: bool = False
    fill: int = 0  # 0 = black, 255 = white
    font: Optional[str] = None  # path to a .ttf font file; overrides default and bold
    align: Literal["left", "center", "right"] = "left"
    max_width: Optional[int] = None
    """Width of the alignment box in pixels. For center/right align: text is positioned
    within [x, x+max_width]. Defaults to full canvas width."""


class RectElement(BaseModel):
    type: Literal["rect"]
    x0: int
    y0: int
    x1: int
    y1: int
    outline: int = 0
    fill: Optional[int] = None


class LineElement(BaseModel):
    type: Literal["line"]
    x0: int
    y0: int
    x1: int
    y1: int
    fill: int = 0
    width: int = 1


class EllipseElement(BaseModel):
    type: Literal["ellipse"]
    x0: int
    y0: int
    x1: int
    y1: int
    outline: int = 0
    fill: Optional[int] = None


class ProgressBarElement(BaseModel):
    type: Literal["progress_bar"]
    x: int
    y: int
    width: int
    height: int = 12
    value: float
    """Fill fraction, 0.0–1.0."""
    fill: int = 0
    background: int = 240
    outline: int = 100


class DividerElement(BaseModel):
    type: Literal["divider"]
    y: int
    fill: int = 0
    width: int = 1
    margin: int = 20
    """Left/right margin in pixels."""


class ImageElement(BaseModel):
    type: Literal["image"]
    path: str
    """Absolute path to a PNG, JPEG, or other Pillow-readable image file."""
    x: int = 0
    y: int = 0
    width: Optional[int] = None
    """Scale to this width, preserving aspect ratio unless height is also set."""
    height: Optional[int] = None


DrawElement = Annotated[
    Union[
        TextElement,
        RectElement,
        LineElement,
        EllipseElement,
        ProgressBarElement,
        DividerElement,
        ImageElement,
    ],
    Field(discriminator="type"),
]


# ── Tools ─────────────────────────────────────────────────────────────────────


@mcp.tool()
def get_display_info() -> dict:
    """Return the eink display dimensions and available named font sizes."""
    return {
        "width": _display.width,
        "height": _display.height,
        "named_font_sizes": NAMED_SIZES,
    }


@mcp.tool()
def clear_display() -> str:
    """Clear the eink display to white."""
    _display.clear()
    return "Display cleared."


@mcp.tool()
def draw(
    elements: list[DrawElement],
    rotation: int = 0,
    background: int = 255,
) -> str:
    """Render drawing elements onto the eink display.

    Element types and their fields:

    text:         { type, text, x, y, size=24, bold=false, fill=0, font=null, align="left", max_width=null }
    rect:         { type, x0, y0, x1, y1, outline=0, fill=null }
    line:         { type, x0, y0, x1, y1, fill=0, width=1 }
    ellipse:      { type, x0, y0, x1, y1, outline=0, fill=null }
    progress_bar: { type, x, y, width, height=12, value, fill=0, background=240, outline=100 }
    divider:      { type, y, fill=0, width=1, margin=20 }
    image:        { type, path, x=0, y=0, width=null, height=null }

    size accepts integers or named strings: title(34) large(28) label(19) value(17) small(14) tiny(12).
    align: "left"|"center"|"right" — use max_width to set the alignment box width.
    progress_bar value: 0.0–1.0 fill fraction.
    fill/outline/background: 0=black, 255=white, 0–255 greyscale.
    rotation: 0 (default), 90, 180, 270.
    background: canvas colour, default 255 (white).
    """
    raw = [el.model_dump() for el in elements]
    _display.render(raw, rotation=rotation, background=background)
    return f"Rendered {len(elements)} element(s)."


if __name__ == "__main__":
    try:
        mcp.run(transport="stdio")
    except Exception:
        log.exception("Server crashed")
