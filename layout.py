"""
Layout engine for render_layout. Sections stack vertically — no coordinate math needed.
"""

from PIL import Image, ImageDraw

from display import _load_font, _text_size

_GAP = 4  # standard internal gap between rows within a section


def render_layout(image: Image.Image, sections: list[dict], padding: int) -> None:
    draw = ImageDraw.Draw(image)
    w, h = image.size
    y = padding

    for section in sections:
        t = section.get("type")
        if t == "header":
            y = _header(draw, section, padding, y, w)
        elif t == "divider":
            y = _divider(draw, section, padding, y, w)
        elif t == "stat_block":
            y = _stat_block(draw, section, padding, y, w)
        elif t == "text_row":
            y = _text_row(draw, section, padding, y, w)
        elif t == "spacer":
            y += section.get("height", 10)
        elif t == "bar_chart":
            _bar_chart(draw, section, padding, y, w, h)
            break  # fills remaining space — must be last
        elif t == "image_block":
            y = _image_block(draw, section, padding, y, w)


# ── Section renderers ─────────────────────────────────────────────────────────


def _header(draw: ImageDraw.ImageDraw, s: dict, pad: int, y: int, w: int) -> int:
    font_title = _load_font("title", bold=True)
    font_sub = _load_font("small")

    title = s.get("title", "")
    subtitle = s.get("subtitle", "")

    draw.text((pad, y), title, font=font_title, fill=0)

    if subtitle:
        th = _text_size(draw, title, font_title)[1]
        sw, sh = _text_size(draw, subtitle, font_sub)
        draw.text((w - pad - sw, y + (th - sh) // 2), subtitle, font=font_sub, fill=80)

    return y + _text_size(draw, title or "A", font_title)[1] + _GAP


def _divider(draw: ImageDraw.ImageDraw, s: dict, pad: int, y: int, w: int) -> int:
    light = s.get("light", False)
    bold = s.get("bold", False)
    fill = s.get("fill", 160 if light else 0)
    lw = s.get("line_width", 2 if bold else 1)
    before = s.get("margin_before", 4)
    after = s.get("margin_after", 6)

    y += before
    draw.line([(pad, y), (w - pad, y)], fill=fill, width=lw)
    return y + lw + after


def _stat_block(draw: ImageDraw.ImageDraw, s: dict, pad: int, y: int, w: int) -> int:
    font_label = _load_font("label", bold=True)
    font_value = _load_font("value")
    font_small = _load_font("small")

    label = s.get("label", "")
    value = s.get("value", "")
    progress = s.get("progress")
    detail = s.get("detail", "")
    badge = s.get("badge", "")

    # Row 1: label (left) + value (right)
    draw.text((pad, y), label, font=font_label, fill=0)
    if value:
        vw, _ = _text_size(draw, value, font_label)
        draw.text((w - pad - vw, y), value, font=font_label, fill=0)
    y += _text_size(draw, label or "A", font_label)[1] + _GAP

    # Row 2: progress bar + optional badge
    if progress is not None:
        bar_right = w - pad
        if badge:
            bw, bh = _text_size(draw, badge, font_small)
            bar_right = w - pad - bw - 8
            draw.text((bar_right + 8, y + (12 - bh) // 2), badge, font=font_small, fill=60)

        bar_w = bar_right - pad
        val = max(0.0, min(1.0, progress))
        draw.rectangle([pad, y, pad + bar_w, y + 12], outline=100, fill=240)
        filled = int(bar_w * val)
        if filled > 0:
            draw.rectangle([pad, y, pad + filled, y + 12], fill=0)
        y += 12 + _GAP

    # Row 3: detail text
    if detail:
        draw.text((pad, y), detail, font=font_value, fill=80)
        y += _text_size(draw, detail, font_value)[1] + _GAP

    return y + 2


def _text_row(draw: ImageDraw.ImageDraw, s: dict, pad: int, y: int, w: int) -> int:
    font = _load_font(s.get("size", "value"), bold=s.get("bold", False))
    fill = s.get("fill", 0)
    left = s.get("left", "")
    right = s.get("right", "")

    if left:
        draw.text((pad, y), left, font=font, fill=fill)
    if right:
        rw, _ = _text_size(draw, right, font)
        draw.text((w - pad - rw, y), right, font=font, fill=fill)

    ref = left or right or "A"
    return y + _text_size(draw, ref, font)[1] + _GAP


def _bar_chart(draw: ImageDraw.ImageDraw, s: dict, pad: int, y: int, w: int, canvas_h: int) -> None:
    font_lbl = _load_font("tiny")
    data = s.get("data", [])
    title = s.get("title", "")

    if not data:
        return

    if title:
        draw.text((pad, y), title, font=font_lbl, fill=60)
        y += _text_size(draw, title, font_lbl)[1] + 4

    content_w = w - 2 * pad
    chart_bottom = canvas_h - pad - 14
    bar_area_h = max(1, chart_bottom - y)
    max_val = max(d.get("value", 0) for d in data) or 1
    n = len(data)
    slot_w = content_w / n
    bar_w = max(4, int(slot_w * 0.55))

    for i, item in enumerate(data):
        label = item.get("label", "")
        val = item.get("value", 0)
        cx = int(pad + slot_w * i + slot_w / 2)
        filled_h = int((val / max_val) * bar_area_h)
        bx0, bx1 = cx - bar_w // 2, cx + bar_w // 2

        draw.rectangle([bx0, y, bx1, chart_bottom], outline=160, fill=240)
        if filled_h > 0:
            draw.rectangle([bx0, chart_bottom - filled_h, bx1, chart_bottom], fill=0)

        if label:
            lw, _ = _text_size(draw, label, font_lbl)
            draw.text((cx - lw // 2, chart_bottom + 2), label, font=font_lbl, fill=0)

        val_lbl = _fmt_value(val)
        if val > 0 and filled_h > 14:
            vlw, _ = _text_size(draw, val_lbl, font_lbl)
            draw.text((cx - vlw // 2, chart_bottom - filled_h - 13), val_lbl, font=font_lbl, fill=0)


def _image_block(draw: ImageDraw.ImageDraw, s: dict, pad: int, y: int, w: int) -> int:
    from PIL import Image as PILImage

    try:
        img = PILImage.open(s["path"]).convert("L")
        target_w = s.get("width", w - 2 * pad)
        orig_w, orig_h = img.size
        target_h = int(orig_h * target_w / orig_w)
        img = img.resize((target_w, target_h), PILImage.LANCZOS)
        x = pad + (w - 2 * pad - target_w) // 2
        draw._image.paste(img, (x, y))
        return y + target_h + _GAP
    except Exception:
        return y


def _fmt_value(n: float) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(int(n))
