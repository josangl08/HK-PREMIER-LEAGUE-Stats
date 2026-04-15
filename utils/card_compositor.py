# ABOUTME: Precision Pillow compositor for fallback performance cards with high legibility.
# ABOUTME: Used when Nano Banana fails and now renders a post-match editorial summary instead of a generic matchday card.

import logging
import os
import time
from pathlib import Path
from typing import Optional, Dict, Any, Union

from PIL import Image, ImageDraw, ImageFont, ImageOps
import requests

from utils.image_processing import get_team_assets

logger = logging.getLogger(__name__)

# --- Configuration ---
FORMAT_SIZES = {
    "1:1": (1080, 1080),
    "9:16": (1080, 1920),
    "16:9": (1920, 1080),
}

_FONT_CACHE_DIR = Path("cache/fonts")
_FONT_CACHE: dict[tuple, ImageFont.FreeTypeFont] = {}

# --- Font Management ---
def _get_font_path(filename: str, url: str) -> Optional[Path]:
    _FONT_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    dest = _FONT_CACHE_DIR / filename
    if dest.exists(): return dest
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        dest.write_bytes(r.content)
        return dest
    except: return None

def _load_font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont:
    # Defaulting to a high-impact sports font (Oswald)
    filename = "Oswald-Bold.ttf" if bold else "Oswald-Regular.ttf"
    url = f"https://github.com/googlefonts/OswaldFont/raw/main/fonts/ttf/{filename}"
    
    font_path = _get_font_path(filename, url)
    try:
        return ImageFont.truetype(str(font_path), size) if font_path else ImageFont.load_default()
    except:
        return ImageFont.load_default()

# --- Compositor Logic ---
def compose_precision_card(
    background_image_path: Optional[str],
    player_photo_path: Optional[str],
    match_payload: Dict,
    player_name: str,
    output_dir: str,
    card_format: str = "9:16",
    narrative: Optional[Dict] = None,
    **kwargs
) -> Path:
    """Creates a minimal but coherent post-match performance card when AI generation fails."""
    size = FORMAT_SIZES.get(card_format, (1080, 1920))
    w, h = size
    
    # 1. Background
    if background_image_path and os.path.exists(background_image_path):
        canvas = Image.open(background_image_path).convert("RGBA").resize(size, Image.LANCZOS)
    else:
        # Gradient Fallback (Brand Red to Dark)
        canvas = Image.new("RGBA", size, (26, 26, 28, 255))
        draw = ImageDraw.Draw(canvas)
        top_color = (147, 49, 42, 255) # HKPL Red
        for y in range(int(h * 0.4)):
            alpha = int(255 * (1 - y / (h * 0.4)))
            draw.line([(0, y), (w, y)], fill=(*top_color[:3], alpha))

    # 2. Player Photo
    if player_photo_path and os.path.exists(player_photo_path):
        player = Image.open(player_photo_path).convert("RGBA")
        # Scale to ~70% of height
        p_w, p_h = player.size
        new_h = int(h * 0.75)
        new_w = int(p_w * (new_h / p_h))
        player = player.resize((new_w, new_h), Image.LANCZOS)
        # Paste centered at bottom
        canvas.alpha_composite(player, ((w - new_w) // 2, h - new_h))

    # 3. Text & Info
    draw = ImageDraw.Draw(canvas)
    editorial = narrative if isinstance(narrative, dict) else {}
    selected_stats = editorial.get("selected_stats") if isinstance(editorial.get("selected_stats"), list) else []
    headline = str(editorial.get("headline") or "PERFORMANCE").upper()
    subheadline = str(editorial.get("subheadline") or "").upper()
    story_angle = str(editorial.get("story_angle") or "").replace("_", " ").upper()
    
    # Title
    font_main = _load_font(int(h * 0.075))
    draw.text((w // 2, int(h * 0.12)), headline, font=font_main, fill="white", anchor="mm")
    if story_angle:
        font_kicker = _load_font(int(h * 0.02), bold=False)
        draw.text((w // 2, int(h * 0.06)), story_angle, font=font_kicker, fill=(180, 220, 255, 255), anchor="mm")
    
    # Player Name (Bottom)
    font_name = _load_font(int(h * 0.05))
    draw.text((w // 2, int(h * 0.89)), player_name.upper(), font=font_name, fill="white", anchor="mm")
    
    # Match Details
    home = match_payload.get("home_team", "HOME")
    away = match_payload.get("away_team", "AWAY")
    match_date = match_payload.get("date", "")
    
    font_vs = _load_font(int(h * 0.03), bold=False)
    draw.text((w // 2, int(h * 0.83)), f"{home} VS {away}", font=font_vs, fill="white", anchor="mm")
    
    if match_date:
        font_date = _load_font(int(h * 0.025), bold=False)
        draw.text((w // 2, int(h * 0.18)), str(match_date).upper(), font=font_date, fill=(200, 200, 200, 255), anchor="mm")
    if subheadline:
        font_sub = _load_font(int(h * 0.024), bold=False)
        draw.text((w // 2, int(h * 0.22)), subheadline, font=font_sub, fill=(220, 220, 220, 255), anchor="mm")

    # Stat panel
    if selected_stats:
        panel_top = int(h * 0.58)
        panel_height = int(h * 0.13)
        panel_width = int(w * 0.84)
        panel_left = (w - panel_width) // 2
        overlay = Image.new("RGBA", (panel_width, panel_height), (0, 0, 0, 150))
        border = Image.new("RGBA", (panel_width, panel_height), (0, 0, 0, 0))
        border_draw = ImageDraw.Draw(border)
        border_draw.rounded_rectangle((0, 0, panel_width - 1, panel_height - 1), radius=24, outline=(120, 220, 255, 140), width=2)
        canvas.alpha_composite(overlay, (panel_left, panel_top))
        canvas.alpha_composite(border, (panel_left, panel_top))

        stat_draw = ImageDraw.Draw(canvas)
        card_count = min(len(selected_stats), 5)
        col_width = panel_width / max(card_count, 1)
        font_stat_value = _load_font(int(h * 0.03))
        font_stat_label = _load_font(int(h * 0.014), bold=False)
        for idx, stat in enumerate(selected_stats[:5]):
            center_x = int(panel_left + (idx + 0.5) * col_width)
            stat_draw.text((center_x, panel_top + int(panel_height * 0.38)), str(stat.get("value") or ""), font=font_stat_value, fill="white", anchor="mm")
            stat_draw.text((center_x, panel_top + int(panel_height * 0.72)), str(stat.get("label") or "").upper(), font=font_stat_label, fill=(200, 200, 200, 255), anchor="mm")

    # 4. Save
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    out_path = Path(output_dir) / f"fallback_{int(time.time())}.png"
    canvas.save(out_path)
    
    return out_path
