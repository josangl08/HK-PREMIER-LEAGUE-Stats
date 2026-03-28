# ABOUTME: Pillow-based engine for composing professional match cards from Design Brief JSON.
# ABOUTME: Supports multiple formats (1:1, 9:16, 16:9) and dynamic layout templates (A/B/C).

# Standard Library
import logging
import math
import os
from pathlib import Path

# Third-party
from PIL import Image, ImageDraw, ImageFont, ImageFilter

logger = logging.getLogger(__name__)

# --- Constants & Mappings ---

FORMAT_SIZES = {
    "1:1": (1080, 1080),
    "9:16": (1080, 1920),
    "16:9": (1920, 1080),
}

# Template Layout Constants (normalised 0.0–1.0 ratios, applied to actual size at render time)
# photo_box: (left, top, right, bottom) as fractions of (width, height)
# text_area: (left, top, right, bottom) as fractions
LAYOUTS = {
    "A": {  # Centred — player photo occupying ~65% of height
        "photo_box": (0.15, 0.10, 0.85, 0.75),
        "text_area": (0.05, 0.77, 0.95, 0.97),
        "glow_center": (0.5, 0.425),
        "glow_radius": 0.32,
        "hero_stat_pos": (0.5, 0.83),  # centre of hero stat block
        "font_sizes": {"title": 80, "stats": 60, "caption": 40},
        "use_photo": True,
    },
    "B": {  # Split-horizontal — stats left, photo right
        "photo_box": (0.52, 0.10, 0.97, 0.90),
        "text_area": (0.03, 0.10, 0.48, 0.90),
        "glow_center": (0.75, 0.5),
        "glow_radius": 0.28,
        "hero_stat_pos": (0.25, 0.45),
        "font_sizes": {"title": 90, "stats": 70, "caption": 45},
        "use_photo": True,
    },
    "C": {  # Minimalist — no photo, large typography
        "photo_box": None,
        "text_area": (0.08, 0.18, 0.92, 0.82),
        "glow_center": (0.5, 0.5),
        "glow_radius": 0.40,
        "hero_stat_pos": (0.5, 0.50),
        "font_sizes": {"title": 120, "stats": 80, "caption": 50},
        "use_photo": False,
    },
}

_DEFAULT_DARK = (26, 26, 46, 255)   # #1a1a2e
_BRAND_WATERMARK = "HK PREMIER LEAGUE"


def _hex_to_rgba(hex_color: str, alpha: int = 255) -> tuple:
    """Converts a #RRGGBB hex string to an RGBA tuple."""
    hex_color = (hex_color or "#1a1a2e").lstrip("#")
    if len(hex_color) != 6:
        return _DEFAULT_DARK[:3] + (alpha,)
    try:
        r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
        return (r, g, b, alpha)
    except ValueError:
        return _DEFAULT_DARK[:3] + (alpha,)


def _pt_to_px(pt: float, dpi: int = 96) -> int:
    """Converts point size to pixels at given DPI."""
    return max(8, int(pt * dpi / 72))


def _scale(val: float, size: int) -> int:
    return int(val * size)


def _load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    """Loads a system font at the given pixel size, falling back to default."""
    candidates = [
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


# ---------------------------------------------------------------------------
# Layer renderers
# ---------------------------------------------------------------------------

def _layer_base_color(img: Image.Image, brief: dict) -> Image.Image:
    """Layer 1: Solid base colour from Design Brief."""
    layers = (brief.get("design") or {}).get("layers") or {}
    color = _hex_to_rgba(layers.get("base_color", "#1a1a2e"))
    base = Image.new("RGBA", img.size, color)
    return Image.alpha_composite(img, base)


def _layer_gradient(img: Image.Image, brief: dict) -> Image.Image:
    """Layer 2: Linear gradient overlay using team colours."""
    w, h = img.size
    layers = (brief.get("design") or {}).get("layers") or {}
    gradient_cfg = layers.get("gradient") or {}

    c1_hex = gradient_cfg.get("color1") or "#1a6b3c"
    c2_hex = gradient_cfg.get("color2") or "#1a1a2e"
    opacity = float(gradient_cfg.get("opacity") or 0.75)
    direction = (gradient_cfg.get("direction") or "135deg").replace("deg", "").strip()
    try:
        angle = float(direction)
    except ValueError:
        angle = 135.0

    c1 = _hex_to_rgba(c1_hex)[:3]
    c2 = _hex_to_rgba(c2_hex)[:3]
    alpha_val = int(opacity * 255)

    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    rad = math.radians(angle)
    cos_a, sin_a = math.cos(rad), math.sin(rad)

    for y in range(h):
        for x in range(w):
            # Project (x,y) onto gradient direction
            t = (x * sin_a + y * cos_a) / (w * abs(sin_a) + h * abs(cos_a) + 1e-9)
            t = max(0.0, min(1.0, t))
            r = int(c1[0] + t * (c2[0] - c1[0]))
            g = int(c1[1] + t * (c2[1] - c1[1]))
            b = int(c1[2] + t * (c2[2] - c1[2]))
            draw.point((x, y), fill=(r, g, b, alpha_val))

    return Image.alpha_composite(img, overlay)


def _layer_gradient_fast(img: Image.Image, brief: dict) -> Image.Image:
    """Layer 2 (fast): Linear gradient using row-by-row fill (no per-pixel loop)."""
    w, h = img.size
    layers = (brief.get("design") or {}).get("layers") or {}
    gradient_cfg = layers.get("gradient") or {}

    c1_hex = gradient_cfg.get("color1") or "#1a6b3c"
    c2_hex = gradient_cfg.get("color2") or "#1a1a2e"
    opacity = float(gradient_cfg.get("opacity") or 0.75)

    c1 = _hex_to_rgba(c1_hex)[:3]
    c2 = _hex_to_rgba(c2_hex)[:3]
    alpha_val = int(opacity * 255)

    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # Top-to-bottom gradient (approximates 135deg at scale)
    for y in range(h):
        t = y / max(h - 1, 1)
        r = int(c1[0] + t * (c2[0] - c1[0]))
        g = int(c1[1] + t * (c2[1] - c1[1]))
        b = int(c1[2] + t * (c2[2] - c1[2]))
        draw.line([(0, y), (w, y)], fill=(r, g, b, alpha_val))

    return Image.alpha_composite(img, overlay)


def _layer_hex_pattern(img: Image.Image) -> Image.Image:
    """Layer 3: Subtle hexagonal dot pattern."""
    w, h = img.size
    pattern = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(pattern)

    hex_size = max(12, w // 30)
    row_h = int(hex_size * 1.73)
    col_w = hex_size * 2

    for row in range(-1, h // row_h + 2):
        for col in range(-1, w // col_w + 2):
            cx = col * col_w + (hex_size if row % 2 else 0)
            cy = row * row_h
            r_dot = max(2, hex_size // 6)
            draw.ellipse(
                [cx - r_dot, cy - r_dot, cx + r_dot, cy + r_dot],
                fill=(255, 255, 255, 18),
            )

    return Image.alpha_composite(img, pattern)


def _layer_atmospheric_glow(img: Image.Image, brief: dict, layout: dict) -> Image.Image:
    """Layer 4: Soft atmospheric glow ellipse at the photo centre position."""
    w, h = img.size
    layers = (brief.get("design") or {}).get("layers") or {}
    glow_hex = layers.get("glow_color") or layers.get("base_color") or "#1a6b3c"
    glow_color = _hex_to_rgba(glow_hex, 90)

    cx = _scale(layout["glow_center"][0], w)
    cy = _scale(layout["glow_center"][1], h)
    radius = _scale(layout["glow_radius"], min(w, h))

    glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(glow)
    # Draw concentric ellipses for soft falloff
    for i in range(5):
        factor = 1.0 - i * 0.18
        rx = int(radius * factor * 1.2)
        ry = int(radius * factor)
        alpha = max(0, glow_color[3] - i * 15)
        draw.ellipse(
            [cx - rx, cy - ry, cx + rx, cy + ry],
            fill=(glow_color[0], glow_color[1], glow_color[2], alpha),
        )
    glow = glow.filter(ImageFilter.GaussianBlur(radius=radius // 3))
    return Image.alpha_composite(img, glow)


def _layer_team_logos(img: Image.Image, brief: dict) -> Image.Image:
    """Layer 5: Team logos from TheSportsDB cache (graceful skip if unavailable)."""
    w, h = img.size
    match = (brief.get("narrative") or {})
    # Logo paths would come from brief in production; skip gracefully if not present
    # This layer is a no-op stub — logos are rendered as text badges instead
    logo_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(logo_layer)

    # Render team name text badges as stand-ins
    home = str(brief.get("match_context", {}).get("home_team") or "")
    away = str(brief.get("match_context", {}).get("away_team") or "")
    if home or away:
        font = _load_font(max(14, w // 60))
        badge_text = f"{home} vs {away}" if home and away else home or away
        draw.text((w // 2, _scale(0.04, h)), badge_text, font=font,
                  fill=(255, 255, 255, 160), anchor="mm")

    return Image.alpha_composite(img, logo_layer)


def _layer_player_photo(img: Image.Image, player_photo_path, layout: dict) -> Image.Image:
    """Layer 6: RGBA player photo (bg-removed) pasted at template position."""
    photo_box = layout.get("photo_box")
    if not photo_box or not player_photo_path:
        return img

    photo_path = str(player_photo_path) if player_photo_path else ""
    if not photo_path or not Path(photo_path).exists():
        return img

    try:
        w, h = img.size
        photo = Image.open(photo_path).convert("RGBA")

        # Compute bounding box in pixels
        x1 = _scale(photo_box[0], w)
        y1 = _scale(photo_box[1], h)
        x2 = _scale(photo_box[2], w)
        y2 = _scale(photo_box[3], h)
        box_w, box_h = x2 - x1, y2 - y1

        # Scale photo to fit box while preserving aspect ratio
        photo_w, photo_h = photo.size
        scale = min(box_w / max(photo_w, 1), box_h / max(photo_h, 1))
        new_w = int(photo_w * scale)
        new_h = int(photo_h * scale)
        photo = photo.resize((new_w, new_h), Image.LANCZOS)

        # Centre within box
        paste_x = x1 + (box_w - new_w) // 2
        paste_y = y1 + (box_h - new_h) // 2

        result = img.copy()
        result.paste(photo, (paste_x, paste_y), mask=photo)
        return result
    except Exception as exc:
        logger.warning(f"_layer_player_photo error: {exc}")
        return img


def _layer_geometric_elements(img: Image.Image, brief: dict) -> Image.Image:
    """Layer 7: Decorative geometric shapes (lines, corners)."""
    w, h = img.size
    geom = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(geom)

    # Accent lines at top and bottom
    line_color = (255, 255, 255, 60)
    line_h = max(2, h // 200)
    draw.rectangle([0, 0, w, line_h], fill=line_color)
    draw.rectangle([0, h - line_h, w, h], fill=line_color)

    # Corner brackets
    corner = max(20, w // 30)
    thick = max(2, w // 200)
    corners = [(0, 0), (w, 0), (0, h), (w, h)]
    directions = [(1, 1), (-1, 1), (1, -1), (-1, -1)]
    for (cx, cy), (dx, dy) in zip(corners, directions):
        draw.rectangle([cx, cy, cx + dx * corner, cy + dy * thick], fill=(255, 255, 255, 80))
        draw.rectangle([cx, cy, cx + dx * thick, cy + dy * corner], fill=(255, 255, 255, 80))

    return Image.alpha_composite(img, geom)


def _layer_info_hierarchy(img: Image.Image, brief: dict, layout: dict) -> Image.Image:
    """Layer 8: Hero stat + secondary stats rendered as text."""
    w, h = img.size
    text_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(text_layer)

    typography = (brief.get("design") or {}).get("typography") or {}
    hero = typography.get("hero_stat") or {}
    secondary = typography.get("secondary_stats") or []

    # Hero stat (value + label)
    hero_px = _pt_to_px(96)
    label_px = _pt_to_px(28)
    font_hero = _load_font(hero_px, bold=True)
    font_label = _load_font(label_px)

    hero_cx = _scale(layout["hero_stat_pos"][0], w)
    hero_cy = _scale(layout["hero_stat_pos"][1], h)

    hero_color = _hex_to_rgba(hero.get("color", "#ffffff"), 255)[:3] + (255,)
    hero_value = str(hero.get("value") or "—")
    hero_label = str(hero.get("label") or "")

    draw.text((hero_cx, hero_cy), hero_value, font=font_hero, fill=hero_color, anchor="mm")
    if hero_label:
        draw.text(
            (hero_cx, hero_cy + hero_px // 2 + label_px),
            hero_label,
            font=font_label,
            fill=(200, 200, 200, 200),
            anchor="mm",
        )

    # Secondary stats
    if secondary:
        sec_px = _pt_to_px(22)
        font_sec = _load_font(sec_px)
        sec_start_x = _scale(0.10, w)
        sec_y = _scale(0.90, h)
        spacing = (w - 2 * sec_start_x) // max(len(secondary), 1)
        for i, stat in enumerate(secondary[:4]):
            sx = sec_start_x + i * spacing
            val = str(stat.get("value") or "—")
            key = str(stat.get("label") or stat.get("key") or "")
            draw.text((sx, sec_y), val, font=font_sec, fill=(255, 255, 255, 220), anchor="ms")
            draw.text((sx, sec_y + sec_px + 4), key, font=font_sec,
                      fill=(180, 180, 180, 180), anchor="ms")

    return Image.alpha_composite(img, text_layer)


def _layer_typography_accents(img: Image.Image, brief: dict, layout: dict) -> Image.Image:
    """Layer 9: Headline, match info, and caption text."""
    w, h = img.size
    text_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(text_layer)

    narrative = brief.get("narrative") or {}
    headline = str(narrative.get("headline") or "")
    key_moment = str(narrative.get("key_moment") or "")

    headline_px = _pt_to_px(28)
    sub_px = _pt_to_px(16)
    font_headline = _load_font(headline_px, bold=True)
    font_sub = _load_font(sub_px)

    # Headline at top area
    if headline:
        draw.text(
            (w // 2, _scale(0.07, h)),
            headline.upper(),
            font=font_headline,
            fill=(255, 255, 255, 230),
            anchor="mm",
        )

    # Key moment below headline
    if key_moment and key_moment != "—":
        draw.text(
            (w // 2, _scale(0.12, h)),
            key_moment,
            font=font_sub,
            fill=(200, 200, 200, 180),
            anchor="mm",
        )

    return Image.alpha_composite(img, text_layer)


def _layer_brand_watermark(img: Image.Image) -> Image.Image:
    """Layer 10: Subtle brand watermark at bottom centre."""
    w, h = img.size
    wm_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(wm_layer)

    wm_px = _pt_to_px(11)
    font_wm = _load_font(wm_px)
    draw.text(
        (w // 2, h - _scale(0.025, h)),
        _BRAND_WATERMARK,
        font=font_wm,
        fill=(255, 255, 255, 60),
        anchor="mm",
    )
    return Image.alpha_composite(img, wm_layer)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compose_card(
    design_brief: dict,
    player_photo_path=None,
    output_dir="data/player_cards",
    format: str = "1:1",
) -> Path:
    """
    Composes a match card PNG from a Design Brief using a 10-layer Pillow pipeline.
    Creates output_dir lazily. Returns the path to the saved PNG.

    Args:
        design_brief: DesignBrief dict from run_card_design_agent().
        player_photo_path: Path to RGBA bg-removed player photo (optional).
        output_dir: Directory to write the PNG into.
        format: One of "1:1", "9:16", "16:9".

    Returns:
        Path to the saved PNG file.
    """
    size = FORMAT_SIZES.get(format, (1080, 1080))
    safe_format = format.replace(":", "_")
    output_path = Path(output_dir) / f"card_{safe_format}.png"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    template = (design_brief.get("design") or {}).get("template", "A")
    # Template C never uses player photo
    if template == "C":
        player_photo_path = None

    layout = LAYOUTS.get(template, LAYOUTS["A"])

    # Start with a transparent canvas
    canvas = Image.new("RGBA", size, (0, 0, 0, 0))

    # 10-layer composition pipeline
    try:
        canvas = _layer_base_color(canvas, design_brief)
        canvas = _layer_gradient_fast(canvas, design_brief)
        canvas = _layer_hex_pattern(canvas)
        canvas = _layer_atmospheric_glow(canvas, design_brief, layout)
        canvas = _layer_team_logos(canvas, design_brief)
        canvas = _layer_player_photo(canvas, player_photo_path, layout)
        canvas = _layer_geometric_elements(canvas, design_brief)
        canvas = _layer_info_hierarchy(canvas, design_brief, layout)
        canvas = _layer_typography_accents(canvas, design_brief, layout)
        canvas = _layer_brand_watermark(canvas)
    except Exception as exc:
        logger.error(f"compose_card pipeline error: {exc}")
        # Save whatever we have so far
        pass

    # Convert to RGB for PNG output (flatten alpha onto dark bg)
    bg = Image.new("RGB", size, (26, 26, 46))
    if canvas.mode == "RGBA":
        bg.paste(canvas, mask=canvas.split()[3])
    else:
        bg.paste(canvas)

    bg.save(str(output_path), "PNG")
    logger.info(f"compose_card saved: {output_path}")
    return output_path
