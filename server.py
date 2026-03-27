import logging
import sys
from typing import Annotated, Literal, Optional, Union

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from display import EinkDisplay

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
    size: int = 24
    fill: int = 0  # 0 = black, 255 = white
    font: Optional[str] = None  # path to a .ttf font file; defaults to DejaVuSansMono


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


DrawElement = Annotated[
    Union[TextElement, RectElement, LineElement, EllipseElement],
    Field(discriminator="type"),
]


# ── Tools ─────────────────────────────────────────────────────────────────────


@mcp.tool()
def get_display_info() -> dict:
    """Return the eink display dimensions (width and height in pixels)."""
    return {"width": _display.width, "height": _display.height}


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

    Each element must have a `type` field: "text", "rect", "line", or "ellipse".

    text:    { type, text, x, y, size=24, fill=0 }
    rect:    { type, x0, y0, x1, y1, outline=0, fill=null }
    line:    { type, x0, y0, x1, y1, fill=0, width=1 }
    ellipse: { type, x0, y0, x1, y1, outline=0, fill=null }

    fill values: 0 = black, 255 = white, or any 0–255 greyscale value.
    rotation: 0 (default), 90, 180, or 270 degrees.
    background: canvas background colour, default 255 (white).
    """
    raw = [el.model_dump() for el in elements]
    _display.render(raw, rotation=rotation, background=background)
    return f"Rendered {len(elements)} element(s)."
