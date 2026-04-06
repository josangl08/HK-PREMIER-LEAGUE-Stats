# ABOUTME: Elite Compositor Engine (Pillow) — V2 (12-layer archetype) + V3 (Master Image dynamic layout).
# ABOUTME: V3 adds compose_from_master() with screen-blend atmosphere overlays and pixel-precise placement.
# ABOUTME: V2 compose_card() preserved for backward compatibility; V3 activated via card_design_agent V3 pipeline.

import logging
import math
import os
import random
from pathlib import Path
from typing import Optional, Dict, Any, List, Union
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps

from utils.image_processing import get_team_assets

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

def _hex_to_rgba(hex_color: Union[str, List[str]], alpha: int = 255) -> tuple:
    if isinstance(hex_color, list) and len(hex_color) > 0:
        hex_color = hex_color[0]
    hex_color = (hex_color or "#1a1a2e").lstrip("#")
    if len(hex_color) != 6: return (10, 10, 15, alpha)
    try:
        r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
        return (r, g, b, alpha)
    except: return (10, 10, 15, alpha)

def _scale_pos(val: float, size: int) -> int:
    return int((val / 100.0) * size)

def _load_font(size: int, style: str = "bold") -> ImageFont.FreeTypeFont:
    # Sports standards: Heavy, Condensed, Bold
    paths = [
        "/System/Library/Fonts/Impact.ttf", # Standard Elite
        "/System/Library/Fonts/Helvetica.ttc",
        "/usr/share/fonts/truetype/liberation/LiberationSansNarrow-Bold.ttf"
    ]
    for path in paths:
        if os.path.exists(path):
            try: return ImageFont.truetype(path, size)
            except: continue
    return ImageFont.load_default()

# ---------------------------------------------------------------------------
# Elite Card Renderer
# ---------------------------------------------------------------------------

class CardRenderer:
    def __init__(self, brief: Dict, format: str = "1:1"):
        self.brief = brief
        self.size = FORMAT_SIZES.get(format, (1080, 1080))
        self.w, self.h = self.size
        self.canvas = Image.new("RGBA", self.size, (0, 0, 0, 255))
        
        # Design State from Art Director
        design = brief.get("design", {})
        layers = design.get("layers", {})
        self.base_color = layers.get("base_color", "#050505")
        self.glow_color = layers.get("glow_color", "#ffffff")
        
        # Concept Flags
        self.archetype = brief.get("layout_modifiers", {}).get("archetype", "god_mode")
        self.use_stadium = brief.get("use_stadium", True)
        self.fx_type = brief.get("fx_type", "fog")
        self.headline_depth = brief.get("headline_depth", "behind") 

    def _get_mod(self, key: str, def_x: float, def_y: float, def_sc: float = 100):
        mods = (self.brief.get("layout_modifiers") or {}).get(key, {})
        return (
            mods.get("x", def_x),
            mods.get("y", def_y),
            mods.get("scale", def_sc) / 100.0,
            mods.get("visible", True)
        )

    # --- LAYER 0: Base Canvas ---
    def render_base_canvas(self):
        if isinstance(self.base_color, list) and len(self.base_color) >= 2:
            bg = Image.new("RGBA", self.size, (0, 0, 0, 255))
            draw = ImageDraw.Draw(bg)
            c1, c2 = _hex_to_rgba(self.base_color[0]), _hex_to_rgba(self.base_color[1])
            for y in range(self.h):
                r = int(c1[0] + (c2[0] - c1[0]) * y / self.h)
                g = int(c1[1] + (c2[1] - c1[1]) * y / self.h)
                b = int(c1[2] + (c2[2] - c1[2]) * y / self.h)
                draw.line([(0, y), (self.w, y)], fill=(r, g, b, 255))
            self.canvas = bg
        else:
            self.canvas = Image.new("RGBA", self.size, _hex_to_rgba(self.base_color))

    # --- LAYER 1: Texture & Grunge ---
    def apply_textures(self):
        noise = Image.new("RGBA", self.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(noise)
        for _ in range(int(self.w * self.h * 0.05)):
            x, y = random.randint(0, self.w - 1), random.randint(0, self.h - 1)
            alpha = random.randint(5, 15)
            d.point((x, y), fill=(255, 255, 255, alpha))
        self.canvas = Image.alpha_composite(self.canvas, noise)

    # --- LAYER 2: Ghost Environment ---
    def render_ghost_environment(self, background_path: Optional[str] = None):
        if not self.use_stadium: return
        if background_path and os.path.exists(background_path):
            bg = Image.open(background_path).convert("RGBA").resize(self.size, Image.LANCZOS)
            bg = bg.filter(ImageFilter.GaussianBlur(radius=3))
            self.canvas = Image.blend(self.canvas, bg, alpha=0.4)
            return
        home_team = self.brief.get("match_payload", {}).get("home_team")
        path = get_team_assets(home_team).get("stadium") if home_team else None
        if path and os.path.exists(path):
            stadium = Image.open(path).convert("RGBA").resize(self.size, Image.LANCZOS)
            stadium = stadium.filter(ImageFilter.GaussianBlur(radius=10))
            stadium = ImageOps.grayscale(stadium).convert("RGBA")
            self.canvas = Image.blend(self.canvas, stadium, alpha=0.15)

    # --- LAYER 3: BG Typography (Z-Behind) ---
    def render_bg_typography(self):
        if self.headline_depth == "front": return
        x, y, sc, vis = self._get_mod("headline", 50, 35, 180)
        if not vis: return
        text = str(self.brief.get("narrative", {}).get("headline", "MATCHDAY")).upper()
        font = _load_font(int(220 * sc))
        cx, cy = _scale_pos(x, self.w), _scale_pos(y, self.h)
        overlay = Image.new("RGBA", self.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        draw.text((cx, cy), text, font=font, fill=(255, 255, 255, 40), anchor="mm")
        self.canvas = Image.alpha_composite(self.canvas, overlay)

    # --- LAYER 4: Graphic Elements (Patterns) ---
    def render_graphic_elements(self):
        overlay = Image.new("RGBA", self.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        accent = _hex_to_rgba(self.glow_color, 30)
        
        # Pattern Variety based on Archetype
        if self.archetype == "minimalist":
            # Subtle Grid
            for i in range(0, self.w, 60): draw.line([(i, 0), (i, self.h)], fill=accent, width=1)
            for i in range(0, self.h, 60): draw.line([(0, i), (self.w, i)], fill=accent, width=1)
        elif self.archetype == "editorial":
            # Halftone-style Dots
            for x in range(0, self.w, 40):
                for y in range(0, self.h, 40):
                    draw.ellipse([x, y, x+4, y+4], fill=accent)
        else:
            # Diagonal Slash (Classic Elite)
            points = [(0, self.h * 0.7), (self.w, self.h * 0.3), (self.w, self.h * 0.35), (0, self.h * 0.75)]
            draw.polygon(points, fill=accent)
            
        self.canvas = Image.alpha_composite(self.canvas, overlay)

    # --- LAYER 5-7: Triple Shadow Pass ---
    def _render_triple_shadow(self, player_mask, pos: tuple, size: tuple):
        px, py = pos
        s1 = Image.new("RGBA", self.size, (0, 0, 0, 0))
        s1.paste((0, 0, 0, 200), (px, py + 5), mask=player_mask)
        s1 = s1.filter(ImageFilter.GaussianBlur(radius=5))
        self.canvas = Image.alpha_composite(self.canvas, s1)
        s2 = Image.new("RGBA", self.size, (0, 0, 0, 0))
        s2.paste((0, 0, 0, 100), (px, py + 20), mask=player_mask)
        s2 = s2.filter(ImageFilter.GaussianBlur(radius=25))
        self.canvas = Image.alpha_composite(self.canvas, s2)
        s3 = Image.new("RGBA", self.size, (0, 0, 0, 0))
        s3.paste((0, 0, 0, 50), (px, py + 50), mask=player_mask)
        s3 = s3.filter(ImageFilter.GaussianBlur(radius=60))
        self.canvas = Image.alpha_composite(self.canvas, s3)

    # --- LAYER 8: Primary Subject (Player Hero) ---
    def render_player_hero(self, photo_path: str):
        if not photo_path or not os.path.exists(photo_path): return
        x, y, sc, vis = self._get_mod("player_photo", 50, 95, 100)
        if not vis: return
        photo = Image.open(photo_path).convert("RGBA")
        nh = int(self.h * 0.85 * sc)
        nw = int(photo.size[0] * nh / photo.size[1])
        photo = photo.resize((nw, nh), Image.LANCZOS)
        enhancer = ImageOps.autocontrast(photo.convert("RGB"), cutoff=0.5).convert("RGBA")
        photo.paste(enhancer, (0,0), mask=photo.split()[3])
        cx, cy = _scale_pos(x, self.w), _scale_pos(y, self.h)
        px, py = cx - nw // 2, cy - nh
        self._render_triple_shadow(photo.split()[3], (px, py), (nw, nh))
        glow_rgba = _hex_to_rgba(self.glow_color, 120)
        rim = Image.new("RGBA", self.size, (0, 0, 0, 0))
        rim.paste(glow_rgba, (px, py), mask=photo.split()[3])
        rim = rim.filter(ImageFilter.GaussianBlur(radius=10))
        self.canvas = Image.alpha_composite(self.canvas, rim)
        self.canvas.paste(photo, (px, py), mask=photo)

    # --- LAYER 9: Atmospheric Glue ---
    def render_atmospheric_glue(self):
        glue = Image.new("RGBA", self.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(glue)
        base_rgba = _hex_to_rgba(self.base_color)
        glow_rgba = _hex_to_rgba(self.glow_color)
        if self.fx_type == "smoke":
            for _ in range(15):
                sx, sy = random.randint(0, self.w), random.randint(int(self.h * 0.7), self.h)
                r, alpha = random.randint(100, 250), random.randint(30, 100)
                draw.ellipse([sx-r, sy-r//2, sx+r, sy+r//2], fill=(base_rgba[0], base_rgba[1], base_rgba[2], alpha))
            glue = glue.filter(ImageFilter.GaussianBlur(radius=50))
        elif self.fx_type == "particles":
            for _ in range(60):
                px, py = random.randint(0, self.w), random.randint(0, self.h)
                r, alpha = random.randint(1, 4), random.randint(100, 200)
                draw.ellipse([px-r, py-r, px+r, py+r], fill=(glow_rgba[0], glow_rgba[1], glow_rgba[2], alpha))
            glue = glue.filter(ImageFilter.GaussianBlur(radius=2))
        elif self.fx_type == "lens_flares":
            flare = Image.new("RGBA", self.size, (0, 0, 0, 0))
            fd = ImageDraw.Draw(flare)
            fd.ellipse([-200, -200, 600, 600], fill=(glow_rgba[0], glow_rgba[1], glow_rgba[2], 40))
            flare = flare.filter(ImageFilter.GaussianBlur(radius=100))
            self.canvas = Image.alpha_composite(self.canvas, flare)
            return
        else:
            fog_h = int(self.h * 0.4)
            for i in range(fog_h):
                alpha = int((i / fog_h) * 180)
                y_pos = self.h - i
                draw.line([(0, y_pos), (self.w, y_pos)], fill=(base_rgba[0], base_rgba[1], base_rgba[2], alpha))
            glue = glue.filter(ImageFilter.GaussianBlur(radius=40))
        self.canvas = Image.alpha_composite(self.canvas, glue)

    # --- LAYER 10: FG Typography (Z-Front) ---
    def render_fg_typography(self):
        if self.headline_depth == "behind": return
        x, y, sc, vis = self._get_mod("headline", 50, 35, 180)
        if not vis: return
        text = str(self.brief.get("narrative", {}).get("headline", "MATCHDAY")).upper()
        font = _load_font(int(220 * sc))
        cx, cy = _scale_pos(x, self.w), _scale_pos(y, self.h)
        overlay = Image.new("RGBA", self.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        if self.headline_depth == "sandwich":
            draw.text((cx, cy), text, font=font, fill=None, outline=(255, 255, 255, 180), stroke_width=2, anchor="mm")
        else:
            draw.text((cx, cy), text, font=font, fill=(255, 255, 255, 220), anchor="mm")
        self.canvas = Image.alpha_composite(self.canvas, overlay)

    # --- LAYER 11: UI Elements ---
    def render_ui_elements(self, player_name: str):
        nx, ny, nsc, nvis = self._get_mod("player_name", 50, 85, 100)
        if nvis:
            font = _load_font(int(90 * nsc))
            draw = ImageDraw.Draw(self.canvas)
            cx, cy = _scale_pos(nx, self.w), _scale_pos(ny, self.h)
            tw, th = draw.textbbox((0, 0), player_name.upper(), font=font)[2:]
            draw.rectangle([cx - tw//2 - 30, cy - th//2 - 10, cx + tw//2 + 30, cy + th//2 + 20], fill=(0,0,0,230))
            draw.text((cx, cy), player_name.upper(), font=font, fill=(255, 255, 255, 255), anchor="mm")
        m_payload = self.brief.get("match_payload", {})
        for key, def_pos in [("home_logo", (15, 15)), ("away_logo", (85, 15))]:
            path = m_payload.get(key)
            if path and os.path.exists(path):
                lx, ly, lsc, lvis = self._get_mod(key, def_pos[0], def_pos[1], 100)
                if lvis: self._render_icon(path, lx, ly, lsc)

    def _render_icon(self, path: str, x: float, y: float, sc: float):
        img = Image.open(path).convert("RGBA")
        size = int(self.h * 0.12 * sc)
        img.thumbnail((size, size), Image.LANCZOS)
        cx, cy = _scale_pos(x, self.w), _scale_pos(y, self.h)
        self.canvas.paste(img, (cx - img.size[0]//2, cy - img.size[1]//2), mask=img)

    # --- LAYER 12: Global Post-Processing ---
    def apply_post_processing(self):
        vignette = Image.new("RGBA", self.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(vignette)
        for i in range(200):
            alpha = int(120 * (i / 200)**2)
            draw.ellipse([i, i, self.w - i, self.h - i], outline=(0, 0, 0, alpha))
        self.canvas = Image.alpha_composite(self.canvas, vignette)
        
        # Dual-tone Color Grading (Warm Highlights, Cool Shadows)
        res = self.canvas.convert("RGB")
        res = ImageOps.autocontrast(res, cutoff=0.5)
        return res

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def _screen_blend(base: np.ndarray, overlay: np.ndarray) -> np.ndarray:
    """Screen blend: 1 - (1 - a) * (1 - b) on RGB channels; overlay alpha preserved in base alpha."""
    base_f = base.astype(np.float32) / 255.0
    overlay_f = overlay.astype(np.float32) / 255.0
    # Use overlay alpha to weight the blend
    ov_alpha = overlay_f[:, :, 3:4]  # (h, w, 1)
    blended_rgb = 1.0 - (1.0 - base_f[:, :, :3]) * (1.0 - overlay_f[:, :, :3] * ov_alpha)
    blended_rgb = np.clip(blended_rgb, 0.0, 1.0)
    result = np.copy(base_f)
    result[:, :, :3] = blended_rgb
    return (result * 255.0).astype(np.uint8)


def compose_from_master(
    master_layout: dict,
    bg_inpainted_path: str,
    player_photo_path: str,
    atmosphere_overlays: List[str],
    ui_brief: dict,
    output_dir: str,
    format: str = "1:1",
) -> Path:
    """
    V3 Compositor: assembles the final card from Master Image assets.

    Layer order:
      0. Inpainted background (resized to format)
      1. Player photo (rembg-cut, placed at master_layout["player_bbox"])
      2. Atmosphere overlays (screen blend)
      3. UI elements (player name, logos from master_layout bboxes)

    Returns:
        Path to the saved card PNG.
    """
    size = FORMAT_SIZES.get(format, (1080, 1080))
    w, h = size

    # --- Layer 0: Inpainted background ---
    if bg_inpainted_path and os.path.exists(bg_inpainted_path):
        canvas = Image.open(bg_inpainted_path).convert("RGBA").resize(size, Image.LANCZOS)
    else:
        canvas = Image.new("RGBA", size, (10, 10, 15, 255))

    # --- Layer 1: Player photo at player_bbox ---
    player_bbox = master_layout.get("player_bbox", {})
    if player_photo_path and os.path.exists(player_photo_path) and player_bbox:
        photo = Image.open(player_photo_path).convert("RGBA")
        px, py = int(player_bbox.get("x", 0)), int(player_bbox.get("y", 0))
        pw, ph = int(player_bbox.get("w", 540)), int(player_bbox.get("h", 700))
        if pw > 0 and ph > 0:
            photo = photo.resize((pw, ph), Image.LANCZOS)
            # Position relative to the formatted canvas (master was 1080-based, scale if needed)
            scale_x = w / 1080
            scale_y = h / 1080
            px_scaled = int(px * scale_x)
            py_scaled = int(py * scale_y)
            photo_scaled = photo.resize((int(pw * scale_x), int(ph * scale_y)), Image.LANCZOS)
            canvas.paste(photo_scaled, (px_scaled, py_scaled), mask=photo_scaled.split()[3])

    # --- Layer 2: Atmosphere overlays (screen blend) ---
    canvas_np = np.array(canvas)
    for overlay_path in (atmosphere_overlays or []):
        if not overlay_path or not os.path.exists(overlay_path):
            continue
        try:
            ov = Image.open(overlay_path).convert("RGBA").resize(size, Image.LANCZOS)
            ov_np = np.array(ov)
            canvas_np = _screen_blend(canvas_np, ov_np)
        except Exception as e:
            logger.warning(f"compose_from_master: failed to apply overlay {overlay_path}: {e}")
    canvas = Image.fromarray(canvas_np, "RGBA")

    # --- Layer 3: UI elements ---
    player_name = ui_brief.get("player_name", "PLAYER")
    match_payload = ui_brief.get("match_payload", {})
    text_area = master_layout.get("text_safe_area", {})

    # Player name bar in text_safe_area
    if text_area and player_name:
        tx = int(text_area.get("x", int(w * 0.05)) * w / 1080)
        ty = int(text_area.get("y", int(h * 0.8)) * h / 1080)
        font_size = max(40, int(h * 0.05))
        font = _load_font(font_size)
        draw = ImageDraw.Draw(canvas)
        tw, th = draw.textbbox((0, 0), player_name.upper(), font=font)[2:]
        draw.rectangle([tx - 10, ty - 8, tx + tw + 10, ty + th + 8], fill=(0, 0, 0, 200))
        draw.text((tx, ty), player_name.upper(), font=font, fill=(255, 255, 255, 255))

    # Team logos at master_layout logo bboxes
    for key, logo_path_key in [("logo_home_bbox", "home_logo"), ("logo_away_bbox", "away_logo")]:
        bbox = master_layout.get(key, {})
        logo_path = match_payload.get(logo_path_key)
        if bbox and logo_path and os.path.exists(logo_path):
            lx = int(bbox.get("x", 0) * w / 1080)
            ly = int(bbox.get("y", 0) * h / 1080)
            lw = max(1, int(bbox.get("w", 80) * w / 1080))
            lh = max(1, int(bbox.get("h", 80) * h / 1080))
            try:
                logo = Image.open(logo_path).convert("RGBA").resize((lw, lh), Image.LANCZOS)
                canvas.paste(logo, (lx, ly), mask=logo.split()[3])
            except Exception as e:
                logger.warning(f"compose_from_master: failed to render logo {logo_path}: {e}")

    # --- Save ---
    out_path = Path(output_dir) / "card_v3.png"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    result = canvas.convert("RGB")
    result.save(str(out_path), "PNG", quality=95)
    return out_path


def compose_card(design_brief, player_photo_path=None, output_dir=".", format="1:1",
                 background_image_path=None, match_payload=None, player_name: str = "PLAYER",
                 output_filename: str = "card_final.png") -> Path:
    # V2 — preserved for backward compatibility
    out_path = Path(output_dir) / output_filename
    out_path.parent.mkdir(parents=True, exist_ok=True)
    renderer = CardRenderer(design_brief, format=format)
    renderer.render_base_canvas()
    renderer.apply_textures()
    renderer.render_ghost_environment(background_image_path)
    renderer.render_bg_typography()
    renderer.render_graphic_elements()
    renderer.render_player_hero(player_photo_path)
    renderer.render_atmospheric_glue()
    renderer.render_fg_typography()
    renderer.render_ui_elements(player_name)
    result = renderer.apply_post_processing()
    if output_filename.startswith("template_"):
        result.thumbnail((300, 300), Image.LANCZOS)
    result.save(str(out_path), "PNG", quality=95)
    return out_path
