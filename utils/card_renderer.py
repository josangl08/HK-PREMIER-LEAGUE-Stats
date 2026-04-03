# ABOUTME: Pillow-based engine for composing professional match cards with absolute positioning.
# ABOUTME: Implements 3 radical Aesthetic Themes: Clean Modern (A), Gritty Urban (B), and Brutalist (C).

import logging
import math
import os
import random
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps

logger = logging.getLogger(__name__)

# --- Constants ---

FORMAT_SIZES = {
    "1:1": (1080, 1080),
    "9:16": (1080, 1920),
    "16:9": (1920, 1080),
}

# ---------------------------------------------------------------------------
# Utility Helpers
# ---------------------------------------------------------------------------

def _hex_to_rgba(hex_color: str, alpha: int = 255) -> tuple:
    hex_color = (hex_color or "#1a1a2e").lstrip("#")
    if len(hex_color) != 6: return (10, 10, 15, alpha)
    try:
        r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
        return (r, g, b, alpha)
    except: return (10, 10, 15, alpha)

def _scale_pos(val: float, size: int) -> int:
    return int((val / 100.0) * size)

def _load_font(size: int, template="A", bold: bool = False) -> ImageFont.FreeTypeFont:
    """Loads a font based on the template's aesthetic theme."""
    paths = []
    if template == "B": # GRITTY
        paths = ["/System/Library/Fonts/Impact.ttf", "/usr/share/fonts/truetype/liberation/LiberationSansNarrow-Bold.ttf"]
    elif template == "C": # BRUTALIST
        paths = ["/System/Library/Fonts/Supplemental/Stencil.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]
    else: # MODERN
        paths = ["/System/Library/Fonts/Helvetica.ttc", "/System/Library/Fonts/Arial.ttf"]

    for path in paths:
        if os.path.exists(path):
            try: return ImageFont.truetype(path, size)
            except: continue
    return ImageFont.load_default()

def _get_element_mod(brief, key, def_x, def_y, def_scale=100):
    mods = (brief.get("layout_modifiers") or {}).get(key, {})
    return (
        mods.get("x", def_x),
        mods.get("y", def_y),
        mods.get("scale", def_scale) / 100.0,
        mods.get("visible", True)
    )

# ---------------------------------------------------------------------------
# Theme-Specific Backgrounds & Textures
# ---------------------------------------------------------------------------

def _apply_theme_background(img: Image.Image, template: str, background_path: str = None, design: dict = None):
    w, h = img.size
    
    # 1. Base
    if background_path and os.path.exists(background_path):
        bg = Image.open(background_path).convert("RGBA").resize((w, h), Image.LANCZOS)
    else:
        layers = (design or {}).get("layers") or {}
        c1 = _hex_to_rgba(layers.get("gradient", {}).get("color1", "#1a1a2e"))
        bg = Image.new("RGBA", (w, h), c1)

    # 2. Theme Processing
    if template == "B": # Gritty Urban
        bg = bg.filter(ImageFilter.EDGE_ENHANCE_MORE)
        bg = ImageOps.colorize(ImageOps.grayscale(bg), black="#000000", white="#444444")
        bg = bg.convert("RGBA")
        # Add grain
        overlay = Image.new("RGBA", (w, h), (0,0,0,0))
        d = ImageDraw.Draw(overlay)
        for _ in range(int(w * h * 0.01)):
            x, y = random.randint(0, w-1), random.randint(0, h-1)
            d.point((x,y), fill=(255,255,255, random.randint(5, 25)))
        bg = Image.alpha_composite(bg, overlay)
        
    elif template == "C": # Brutalist Data
        bg = ImageOps.grayscale(bg).convert("RGBA")
        # Add Grid
        grid = Image.new("RGBA", (w, h), (0,0,0,0))
        gd = ImageDraw.Draw(grid)
        step = 40
        for x in range(0, w, step): gd.line([(x, 0), (x, h)], fill=(255,255,255, 20), width=1)
        for y in range(0, h, step): gd.line([(0, y), (w, y)], fill=(255,255,255, 20), width=1)
        bg = Image.alpha_composite(bg, grid)

    return bg

# ---------------------------------------------------------------------------
# Dynamic Layer Rendering
# ---------------------------------------------------------------------------

def _render_headline(img: Image.Image, brief: dict):
    w, h = img.size
    x, y, sc, vis = _get_element_mod(brief, "headline", 50, 20, 100)
    if not vis: return img

    text = str(brief.get("narrative", {}).get("headline", "MATCHDAY")).upper()
    template = brief.get("template", "A")
    font = _load_font(int(140 * sc), template=template, bold=True)
    
    cx, cy = _scale_pos(x, w), _scale_pos(y, h)
    layer = Image.new("RGBA", (w, h), (0,0,0,0))
    draw = ImageDraw.Draw(layer)
    
    # Shadow logic based on theme
    sh_off = int(8 * sc)
    if template == "C": # Flat offset shadow
        draw.text((cx + sh_off, cy + sh_off), text, font=font, fill=(0, 242, 255, 255), anchor="mm")
    else:
        draw.text((cx + sh_off, cy + sh_off), text, font=font, fill=(0,0,0,180), anchor="mm")
        
    draw.text((cx, cy), text, font=font, fill=(255,255,255,255), anchor="mm")
    return Image.alpha_composite(img, layer)

def _render_player_photo(img: Image.Image, photo_path, brief: dict):
    if not photo_path or not os.path.exists(photo_path): return img
    w, h = img.size
    x, y, sc, vis = _get_element_mod(brief, "player_photo", 50, 95, 100)
    if not vis: return img

    photo = Image.open(photo_path).convert("RGBA")
    nh = int(h * 0.9 * sc)
    nw = int(photo.size[0] * nh / photo.size[1])
    photo = photo.resize((nw, nh), Image.LANCZOS)
    
    cx, cy = _scale_pos(x, w), _scale_pos(y, h)
    px, py = cx - nw // 2, cy - nh
    
    # Shadow
    sl = Image.new("RGBA", (w, h), (0,0,0,0))
    s = Image.new("RGBA", (nw, nh), (0,0,0, 180))
    sl.paste(s, (px, py), mask=photo.split()[3])
    sl = sl.filter(ImageFilter.GaussianBlur(radius=30))
    
    res = Image.alpha_composite(img, sl)
    res.paste(photo, (px, py), mask=photo)
    return res

def _render_team_logos(img: Image.Image, match_payload: dict, brief: dict):
    w, h = img.size
    x, y, sc, vis = _get_element_mod(brief, "home_logo", 15, 12, 100)
    if not vis: return img

    layer = Image.new("RGBA", (w, h), (0,0,0,0))
    h_path = match_payload.get("home_logo")
    a_path = match_payload.get("away_logo")
    
    def paste(path, ox):
        if not path or not os.path.exists(path): return
        logo = Image.open(path).convert("RGBA")
        sz = int(160 * sc)
        logo.thumbnail((sz, sz), Image.LANCZOS)
        px = _scale_pos(x + ox, w) - logo.size[0] // 2
        py = _scale_pos(y, h) - logo.size[1] // 2
        layer.paste(logo, (px, py), logo)

    paste(h_path, 0)
    paste(a_path, 15)
    return Image.alpha_composite(img, layer)

def _render_match_info(img: Image.Image, match_payload: dict, brief: dict):
    w, h = img.size
    x, y, sc, vis = _get_element_mod(brief, "match_info", 50, 95, 100)
    if not vis: return img
    
    text = f"{match_payload.get('stadium', 'HK')} • {match_payload.get('kickoff_display', '')}".upper()
    font = _load_font(int(28 * sc), template=brief.get("template"))
    draw = ImageDraw.Draw(img)
    draw.text((_scale_pos(x, w), _scale_pos(y, h)), text, font=font, fill=(255,255,255,200), anchor="mm")
    return img

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compose_card(design_brief, player_photo_path=None, output_dir=".", format="1:1", 
                 background_image_path=None, match_payload=None) -> Path:
    size = FORMAT_SIZES.get(format, (1080, 1080))
    out_path = Path(output_dir) / "card_final.png"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    canvas = Image.new("RGBA", size, (0,0,0,0))
    m_payload = match_payload or {}
    template = design_brief.get("template", "A")
    
    try:
        canvas = _apply_theme_background(canvas, template, background_image_path, design_brief.get("design"))
        canvas = _render_headline(canvas, design_brief)
        canvas = _render_player_photo(canvas, player_photo_path, design_brief)
        canvas = _render_team_logos(canvas, m_payload, design_brief)
        canvas = _render_match_info(canvas, m_payload, design_brief)
    except Exception as e:
        logger.error(f"Composer failed: {e}")

    canvas.convert("RGB").save(str(out_path), "PNG")
    return out_path
