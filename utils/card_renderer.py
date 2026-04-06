# ABOUTME: Elite Compositor Engine (Pillow) - Agency Grade.
# ABOUTME: Implements the 12-layer sandwich: Triple Shadow, Z-Depth Typography, and Atmospheric Glue.
# ABOUTME: Percentage-based coordinate system (0-100) for multi-format consistency.

import logging
import math
import os
import random
from pathlib import Path
from typing import Optional, Dict, Any, List, Union
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

def compose_card(design_brief, player_photo_path=None, output_dir=".", format="1:1", 
                 background_image_path=None, match_payload=None, player_name: str = "PLAYER",
                 output_filename: str = "card_final.png") -> Path:
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
