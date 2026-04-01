import json
import logging
import os
import sys
from pathlib import Path
from typing import Annotated, Literal, Optional, Union

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from display import NAMED_SIZES, EinkDisplay

logging.basicConfig(stream=sys.stderr, level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

mcp = FastMCP("eink-display")
_display = EinkDisplay()
_default_rotation = int(os.getenv("EINK_ROTATION", 0))
log.info("eink-display MCP server started (display available: %s)", _display._available)

# ── Display state ─────────────────────────────────────────────────────────────

_STATE_PATH = os.getenv("EINK_STATE_PATH", "/tmp/eink_state.json")

try:
    with open(_STATE_PATH) as _f:
        _display_state: dict | None = json.load(_f)
    log.info("Loaded display state from %s", _STATE_PATH)
except Exception:
    _display_state = None


def _save_state(state: dict | None) -> None:
    global _display_state
    _display_state = state
    try:
        if state is None:
            if os.path.exists(_STATE_PATH):
                os.remove(_STATE_PATH)
        else:
            with open(_STATE_PATH, "w") as f:
                json.dump(state, f)
    except Exception as e:
        log.warning("Could not persist display state: %s", e)


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
    """Anchor behaviour: "left" → x is the left edge; "center" → x is the center point;
    "right" → x is the right edge."""


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
    """Absolute path to a PNG, JPEG, SVG, or other Pillow-readable image file."""
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
    global _display_state
    _display.clear()
    _save_state(None)
    return "Display cleared."


@mcp.tool()
def draw(
    elements: list[DrawElement],
    rotation: Optional[int] = None,
    background: int = 255,
) -> str:
    """Render drawing elements onto the eink display.

    TOOL SELECTION GUIDE — choose the right approach before calling:
    • Artistic / scenic content (landscapes, illustrations, portraits, animals,
      nature scenes, abstract art): generate the image externally and display it
      via an `image` element. Do NOT attempt to approximate art with primitives.
    • Structured / geometric content (charts, diagrams, icons, UI widgets,
      technical drawings): use the primitive elements (rect, line, ellipse, text).
    • Mixed content: combine an `image` element as background with text/rect
      overlays on top.

    Element types and their fields:

    image:        { type, path, x=0, y=0, width=null, height=null }
                  — PREFERRED for any pictorial or artistic content.
                    path must be an absolute path to a PNG/JPEG/SVG/Pillow-readable file.
                    SVG files are rasterised automatically via cairosvg.
                    width/height are optional; omit both to use the file's native size.
    text:         { type, text, x, y, size=24, bold=false, fill=0, font=null, align="left" }
    rect:         { type, x0, y0, x1, y1, outline=0, fill=null }
    line:         { type, x0, y0, x1, y1, fill=0, width=1 }
    ellipse:      { type, x0, y0, x1, y1, outline=0, fill=null }
    progress_bar: { type, x, y, width, height=12, value, fill=0, background=240, outline=100 }
    divider:      { type, y, fill=0, width=1, margin=20 }

    size accepts integers or named strings: title(34) large(28) label(19) value(17) small(14)
    tiny(12).
    align: "left"=x is left edge, "center"=x is center point, "right"=x is right edge.
    progress_bar value: 0.0–1.0 fill fraction.
    fill/outline/background: 0=black, 255=white, 0–255 greyscale.
    rotation: omit to use EINK_ROTATION env var; only pass to override. Values: 0, 90, 180, 270.
    background: canvas colour, default 255 (white).
    """
    raw = [el.model_dump() for el in elements]
    r = rotation if rotation is not None else _default_rotation
    _display.render(raw, rotation=r, background=background)
    _save_state({"tool": "draw", "elements": raw, "rotation": r, "background": background})
    return f"Rendered {len(elements)} element(s) at rotation={r}."


@mcp.tool()
def render_layout(
    sections: list[LayoutSection],
    padding: int = 20,
    rotation: Optional[int] = None,
    background: int = 255,
) -> str:
    """Render a structured dashboard layout onto the eink display.

    TOOL SELECTION GUIDE:
    • Use render_layout for dashboard-style output: stats, text lists, charts,
      timelines, activity summaries. Sections auto-stack — no coordinate math.
    • Use draw() instead when you need pixel-precise positioning, layered elements,
      or a full-canvas artistic image (via its `image` element type).
    • For pictorial/scenic content inside a layout (e.g. a photo with a caption),
      use an `image_block` section — supply a pre-existing image file path.

    Sections stack vertically — no x/y coordinate math required.

    Section types:

    header:      { type, title, subtitle=null }
    divider:     { type, light=false, bold=false, margin_before=4, margin_after=6 }
    stat_block:  { type, label, value=null, progress=null, detail=null, badge=null }
    text_row:    { type, left=null, right=null, size="value", bold=false, fill=0 }
    spacer:      { type, height=10 }
    bar_chart:   { type, data=[{label, value},...], title=null }
    image_block: { type, path, width=null }
                 — use for pictorial/scenic content; path must be an absolute
                   path to a PNG/JPEG/Pillow-readable file.

    bar_chart must be the last section — it fills all remaining vertical space.
    progress: 0.0–1.0 fill fraction.
    size: integer pixels or named — title(34) large(28) label(19) value(17) small(14) tiny(12).
    rotation: omit to use EINK_ROTATION env var; only pass to override. Values: 0, 90, 180, 270.
    """
    from PIL import Image

    from layout import render_layout as _render_layout

    if rotation is None:
        rotation = _default_rotation

    if rotation in (90, 270):
        w, h = _display.height, _display.width
    else:
        w, h = _display.width, _display.height

    raw_sections = [s.model_dump() for s in sections]
    image = Image.new("L", (w, h), background)
    _render_layout(image, raw_sections, padding)

    if rotation != 0:
        image = image.rotate(rotation, expand=True)

    _save_state(
        {
            "tool": "render_layout",
            "sections": raw_sections,
            "padding": padding,
            "rotation": rotation,
            "background": background,
        }
    )

    if not _display._available:
        log.warning("Hardware not available — layout rendered (dry run)")
        return f"Layout rendered (dry run): {len(sections)} section(s)."

    _display.send(image)
    return f"Layout rendered: {len(sections)} section(s)."


_TEMPLATES_DIR = Path(__file__).parent / "templates"


def _resolve_asset_paths(obj: object) -> object:
    """Recursively resolve relative 'path' values in a template spec to absolute paths.

    Template authors write paths relative to the templates/ directory
    (e.g. "assets/github-mark.svg"). This expands them so draw() and
    render_layout() receive absolute paths as required.
    """
    if isinstance(obj, dict):
        return {
            k: (
                str((_TEMPLATES_DIR / v).resolve())
                if k == "path" and isinstance(v, str) and not Path(v).is_absolute()
                else _resolve_asset_paths(v)
            )
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [_resolve_asset_paths(item) for item in obj]
    return obj


@mcp.tool()
def list_templates() -> str:
    """Return all available display templates as a JSON array.

    Call this when the user asks to display something that might match a known
    layout (e.g. "show me the weather", "display a clock", "show system stats").

    Each template includes:
    - name: unique identifier
    - description: what it shows and when to use it
    - tags: keywords for matching user intent
    - tool: which tool to call — "draw" or "render_layout"
    - spec: the full parameter object to pass to that tool (with placeholder
            values like "NN°C" or 0.0 that you should replace with real data).
            Asset paths (images, icons) are already resolved to absolute paths.

    Workflow:
    1. Call list_templates() to discover options.
    2. Pick the template whose description/tags best match the user's intent.
    3. Fetch any real data needed to fill in the placeholders.
    4. Call draw() or render_layout() with the spec, substituting real values.
       You may add, remove, or reorder sections/elements to better fit the content.
    """
    templates = []
    for path in sorted(_TEMPLATES_DIR.glob("*.json")):
        try:
            template = json.loads(path.read_text())
            template["spec"] = _resolve_asset_paths(template.get("spec", {}))
            templates.append(template)
        except Exception as e:
            log.warning("Could not load template %s: %s", path.name, e)
    return json.dumps(templates)


@mcp.tool()
def get_display_state() -> dict:
    """Return the spec of what is currently shown on the eink display.

    Returns the full elements (for draw) or sections (for render_layout) that
    were last sent, along with rotation, background, and padding. Returns
    {"empty": true} if the display has been cleared or nothing has been drawn.

    Use this before iterating on a layout — fetch the current spec, modify it,
    then call draw() or render_layout() again.
    """
    if _display_state is None:
        return {"empty": True}
    return _display_state


if __name__ == "__main__":
    try:
        mcp.run(transport="stdio")
    except Exception:
        log.exception("Server crashed")
