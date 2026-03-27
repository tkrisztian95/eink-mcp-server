import logging
import sys
from typing import Annotated, Literal, Optional, Union

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from display import NAMED_SIZES, EinkDisplay

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


# ── Layout section models ─────────────────────────────────────────────────────


class HeaderSection(BaseModel):
    type: Literal["header"]
    title: str
    subtitle: Optional[str] = None
    """Optional right-aligned subtitle (e.g. timestamp)."""


class DividerSection(BaseModel):
    type: Literal["divider"]
    light: bool = False
    """Light grey rule (fill=160). Default is solid black."""
    bold: bool = False
    """Thicker rule (width=2). Takes precedence over light."""
    fill: Optional[int] = None
    line_width: Optional[int] = None
    margin_before: int = 4
    margin_after: int = 6


class StatBlockSection(BaseModel):
    type: Literal["stat_block"]
    label: str
    value: Optional[str] = None
    """Right-aligned summary value (e.g. '1.2K tok')."""
    progress: Optional[float] = None
    """Fill fraction 0.0–1.0. Omit to hide the progress bar."""
    detail: Optional[str] = None
    """Small sub-line below the bar (e.g. '987 in / 247 out')."""
    badge: Optional[str] = None
    """Small label to the right of the bar (e.g. 'Resets 13h')."""


class TextRowSection(BaseModel):
    type: Literal["text_row"]
    left: Optional[str] = None
    right: Optional[str] = None
    size: Union[int, str] = "value"
    bold: bool = False
    fill: int = 0


class SpacerSection(BaseModel):
    type: Literal["spacer"]
    height: int = 10


class BarDataPoint(BaseModel):
    label: str
    value: float


class BarChartSection(BaseModel):
    type: Literal["bar_chart"]
    data: list[BarDataPoint]
    title: Optional[str] = None
    """Must be the last section — fills all remaining vertical space."""


class ImageBlockSection(BaseModel):
    type: Literal["image_block"]
    path: str
    width: Optional[int] = None
    """Scale to this width, preserving aspect ratio. Defaults to full content width."""


LayoutSection = Annotated[
    Union[
        HeaderSection,
        DividerSection,
        StatBlockSection,
        TextRowSection,
        SpacerSection,
        BarChartSection,
        ImageBlockSection,
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

    text:         { type, text, x, y, size=24, bold=false, fill=0, font=null, align="left",
                    max_width=null }
    rect:         { type, x0, y0, x1, y1, outline=0, fill=null }
    line:         { type, x0, y0, x1, y1, fill=0, width=1 }
    ellipse:      { type, x0, y0, x1, y1, outline=0, fill=null }
    progress_bar: { type, x, y, width, height=12, value, fill=0, background=240, outline=100 }
    divider:      { type, y, fill=0, width=1, margin=20 }
    image:        { type, path, x=0, y=0, width=null, height=null }

    size accepts integers or named strings: title(34) large(28) label(19) value(17) small(14)
    tiny(12).
    align: "left"|"center"|"right" — use max_width to set the alignment box width.
    progress_bar value: 0.0–1.0 fill fraction.
    fill/outline/background: 0=black, 255=white, 0–255 greyscale.
    rotation: 0 (default), 90, 180, 270.
    background: canvas colour, default 255 (white).
    """
    raw = [el.model_dump() for el in elements]
    _display.render(raw, rotation=rotation, background=background)
    return f"Rendered {len(elements)} element(s)."


@mcp.tool()
def render_layout(
    sections: list[LayoutSection],
    padding: int = 20,
    rotation: int = 0,
    background: int = 255,
) -> str:
    """Render a structured dashboard layout onto the eink display.

    Sections stack vertically — no x/y coordinate math required.

    Section types:

    header:      { type, title, subtitle=null }
    divider:     { type, light=false, bold=false, margin_before=4, margin_after=6 }
    stat_block:  { type, label, value=null, progress=null, detail=null, badge=null }
    text_row:    { type, left=null, right=null, size="value", bold=false, fill=0 }
    spacer:      { type, height=10 }
    bar_chart:   { type, data=[{label, value},...], title=null }
    image_block: { type, path, width=null }

    bar_chart must be the last section — it fills all remaining vertical space.
    progress: 0.0–1.0 fill fraction.
    size: integer pixels or named — title(34) large(28) label(19) value(17) small(14) tiny(12).
    """
    from PIL import Image

    from layout import render_layout as _render_layout

    if rotation in (90, 270):
        w, h = _display.height, _display.width
    else:
        w, h = _display.width, _display.height

    image = Image.new("L", (w, h), background)
    _render_layout(image, [s.model_dump() for s in sections], padding)

    if rotation != 0:
        image = image.rotate(rotation, expand=True)

    if not _display._available:
        log.warning("Hardware not available — layout rendered (dry run)")
        return f"Layout rendered (dry run): {len(sections)} section(s)."

    _display.send(image)
    return f"Layout rendered: {len(sections)} section(s)."


if __name__ == "__main__":
    try:
        mcp.run(transport="stdio")
    except Exception:
        log.exception("Server crashed")
