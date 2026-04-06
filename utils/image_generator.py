# ABOUTME: Image composition engine for social media cards and PDF dossier headers.
# ABOUTME: Uses Pillow for layered composition and rembg for player photo background removal.

# Standard Library
import json
import logging
import os
import uuid
from io import BytesIO
from pathlib import Path
from typing import Optional

# Third-party
from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)


class CompositionMotor:
    """
    Layered image composition engine for HKPL content generation.

    Produces:
      - Player cards (Feature A): cutout photo + stats + club logo + branding
      - Pre-match social cards (Feature B): team logos + fixture info
      - Dossier header images (Feature C, PDF integration)

    All templates are driven by JSON configs in assets/templates/.
    """

    CUTOUT_DIR = "data/cache/cutouts"
    MAX_CUTOUTS = 5
    SOCIAL_SIZES = {
        "square": (1080, 1080),
        "story": (1080, 1920),
    }
    TEMPLATES_DIR = Path("assets/templates")
    LOGOS_DIR = Path("assets/team_logos")
    FONTS_DIR = Path("assets/fonts")

    def __init__(self):
        os.makedirs(self.CUTOUT_DIR, exist_ok=True)
        self._player_cfg = self._load_config("player_card_config.json")
        self._prematch_cfg = self._load_config("prematch_card_config.json")

    # ──────────────────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────────────────

    def process_player_photo(self, player_id: str, image_bytes: bytes) -> str:
        """
        Remove background with rembg, cache result as PNG.

        Enforces MAX_CUTOUTS per player (oldest deleted when limit reached).
        Returns path to saved cutout.
        """
        try:
            import rembg
        except ImportError:
            raise RuntimeError("rembg not installed. Run: pip install rembg")

        player_dir = Path(self.CUTOUT_DIR) / player_id
        player_dir.mkdir(parents=True, exist_ok=True)

        # Enforce quota: remove oldest if at limit
        existing = sorted(player_dir.glob("*.png"), key=lambda p: p.stat().st_mtime)
        while len(existing) >= self.MAX_CUTOUTS:
            existing[0].unlink()
            logger.info(f"Removed oldest cutout for quota: {existing[0].name}")
            existing = existing[1:]

        output_bytes = rembg.remove(image_bytes)

        filename = f"{uuid.uuid4().hex}.png"
        output_path = player_dir / filename
        with open(output_path, "wb") as f:
            f.write(output_bytes)

        logger.info(f"Saved cutout for player '{player_id}': {output_path}")
        return str(output_path)

    def get_cutouts(self, player_id: str) -> list:
        """Return list of cached cutout paths for a player, newest first."""
        player_dir = Path(self.CUTOUT_DIR) / player_id
        if not player_dir.exists():
            return []
        return sorted(
            [str(p) for p in player_dir.glob("*.png")],
            key=lambda p: Path(p).stat().st_mtime,
            reverse=True,
        )

    def delete_cutout(self, player_id: str, filename: str) -> bool:
        """
        Delete a specific cutout PNG.
        Validates path stays within CUTOUT_DIR to prevent traversal.
        """
        try:
            base = Path(self.CUTOUT_DIR).resolve()
            target = (base / player_id / filename).resolve()
            if not str(target).startswith(str(base)):
                logger.warning(f"Path traversal blocked for filename={filename!r}")
                return False
            if target.exists() and target.suffix == ".png":
                target.unlink()
                return True
        except Exception as e:
            logger.error(f"Error deleting cutout '{filename}': {e}")
        return False

    def compose_player_card(
        self,
        player_id: str,
        stats: dict,
        club: str,
        size: str = "square",
    ) -> bytes:
        """
        Compose a player card image.

        Layer order: background → gradient → stats block → cutout → logo → name → branding
        Returns PNG bytes.
        """
        cfg = self._player_cfg
        dims = self._dims(cfg, size)
        colors = cfg.get("colors", {})
        elements = cfg.get("elements", {})

        img = self._make_background(dims, colors)
        draw = ImageDraw.Draw(img)

        self._draw_gradient_overlay(img, colors, dims)
        self._draw_stats_block(draw, stats, elements.get("stats_block", {}), dims, colors)

        cutouts = self.get_cutouts(player_id)
        if cutouts:
            self._paste_cutout(img, cutouts[0], elements.get("cutout", {}), dims)

        self._paste_logo(img, club, elements.get("club_logo", {}), dims)

        name = (stats.get("name") or player_id).upper()
        self._draw_text(
            draw, name, elements.get("name", {}), dims,
            self._color(colors, "text_primary"), bold=True,
        )

        branding_cfg = elements.get("branding", {})
        if branding_cfg:
            self._draw_text(
                draw,
                branding_cfg.get("text", "HK PREMIER LEAGUE"),
                branding_cfg,
                dims,
                self._color(colors, "text_secondary"),
                opacity=branding_cfg.get("opacity", 150),
            )

        return self._to_png_bytes(img)

    def compose_prematch_card(self, fixture: dict, size: str = "square") -> bytes:
        """
        Compose a pre-match social card.
        Returns PNG bytes.
        """
        cfg = self._prematch_cfg
        dims = self._dims(cfg, size)
        colors = cfg.get("colors", {})
        elements = cfg.get("elements", {})

        img = self._make_background(dims, colors)
        draw = ImageDraw.Draw(img)
        self._draw_gradient_overlay(img, colors, dims)

        # Competition badge
        badge_cfg = elements.get("competition_badge", {"pos": [0.5, 0.2], "font_size": 35, "anchor": "mm"})
        competition = (fixture.get("competition") or "HK PREMIER LEAGUE").upper()
        self._draw_text(draw, competition, badge_cfg, dims, self._color(colors, "text_secondary"))

        # Home team
        home_cfg = elements.get("home_team", {})
        self._draw_team(img, draw, fixture.get("home_team", ""), fixture.get("home_logo_url"),
                        home_cfg, dims, colors)

        # Away team
        away_cfg = elements.get("away_team", {})
        self._draw_team(img, draw, fixture.get("away_team", ""), fixture.get("away_logo_url"),
                        away_cfg, dims, colors)

        # VS
        vs_cfg = elements.get("vs_text", {"pos": [0.5, 0.5], "font_size": 120, "anchor": "mm"})
        self._draw_text(draw, "VS", vs_cfg, dims,
                        self._color(colors, "vs_color", fallback=(255, 255, 255)), bold=True)

        # Match info
        parts = [p for p in [fixture.get("kickoff_display"), fixture.get("stadium")] if p]
        if parts:
            info_cfg = elements.get("match_info", {"pos": [0.5, 0.75], "font_size": 40, "anchor": "mm"})
            self._draw_text(draw, "  |  ".join(parts), info_cfg, dims,
                            self._color(colors, "text_secondary"))

        return self._to_png_bytes(img)

    def compose_dossier_header(self, player_id: str, season: str) -> Image.Image:
        """
        Compose a small header image for embedding into PDF dossiers.
        Returns a PIL Image (RGB).
        """
        dims = (800, 200)
        img = Image.new("RGBA", dims, (20, 20, 25, 255))
        draw = ImageDraw.Draw(img)

        # Accent bar
        draw.rectangle([(0, 0), (8, 200)], fill=(147, 49, 42, 255))

        # Cutout thumbnail
        cutouts = self.get_cutouts(player_id)
        if cutouts:
            try:
                cutout = Image.open(cutouts[0]).convert("RGBA")
                cutout.thumbnail((160, 160))
                img.paste(cutout, (620, 20), cutout)
            except Exception as e:
                logger.warning(f"Could not embed cutout in dossier header: {e}")

        # Text
        font_s = self._load_font(40)
        font_xs = self._load_font(28)
        draw.text((30, 70), player_id.upper(), fill=(255, 255, 255, 255), font=font_s)
        draw.text((30, 125), f"Season: {season}", fill=(200, 200, 200, 255), font=font_xs)
        draw.text((30, 160), "HK PREMIER LEAGUE", fill=(147, 49, 42, 255), font=font_xs)

        return img.convert("RGB")

    # ──────────────────────────────────────────────────────────────────────────
    # Private helpers
    # ──────────────────────────────────────────────────────────────────────────

    def _load_config(self, filename: str) -> dict:
        path = self.TEMPLATES_DIR / filename
        try:
            with open(path) as f:
                return json.load(f)
        except Exception as e:
            logger.debug(f"Template config '{filename}' not found, using defaults: {e}")
            return {}

    def _dims(self, cfg: dict, size: str) -> tuple:
        raw = cfg.get("dimensions", {}).get(size, self.SOCIAL_SIZES.get(size, (1080, 1080)))
        return tuple(raw)

    def _color(self, colors: dict, key: str, fallback: tuple = (255, 255, 255)) -> tuple:
        raw = colors.get(key, [*fallback, 255])
        return tuple(raw[:3])

    def _make_background(self, dims: tuple, colors: dict) -> Image.Image:
        bg = self._color(colors, "background", (20, 20, 25))
        return Image.new("RGBA", dims, (*bg, 255))

    def _draw_gradient_overlay(self, img: Image.Image, colors: dict, dims: tuple) -> None:
        """Subtle radial gradient using accent color."""
        accent = self._color(colors, "accent", (147, 49, 42))
        overlay = Image.new("RGBA", dims, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        w, h = dims
        cx, cy = w // 2, h // 2
        for i in range(15):
            alpha = int(60 * (1 - i / 15))
            r = int(min(w, h) * 0.55 * (i / 15))
            draw.ellipse([(cx - r, cy - r), (cx + r, cy + r)], fill=(*accent, alpha))
        img.alpha_composite(overlay)

    def _draw_stats_block(self, draw: ImageDraw.ImageDraw, stats: dict,
                          cfg: dict, dims: tuple, colors: dict) -> None:
        if not stats or not cfg:
            return
        pos = cfg.get("pos", [0.5, 0.85])
        font_size = cfg.get("font_size", 40)
        spacing = cfg.get("spacing", 50)
        cx = int(pos[0] * dims[0])
        cy = int(pos[1] * dims[1])

        stat_keys = [("goals", "GOL"), ("assists", "AST"), ("matches_played", "PJ")]
        total = len(stat_keys)
        for idx, (key, label) in enumerate(stat_keys):
            x = cx + int((idx - total / 2 + 0.5) * spacing * 2)
            val = str(stats.get(key, "-"))
            font_val = self._load_font(font_size, bold=True)
            font_lbl = self._load_font(max(16, font_size // 2))
            draw.text((x, cy), val, fill=(255, 255, 255, 255), font=font_val, anchor="mm")
            draw.text((x, cy + font_size), label, fill=(200, 200, 200, 200), font=font_lbl, anchor="mm")

    def _paste_cutout(self, img: Image.Image, cutout_path: str,
                      cfg: dict, dims: tuple) -> None:
        try:
            cutout = Image.open(cutout_path).convert("RGBA")
            scale = cfg.get("scale", 0.8)
            max_h = int(dims[1] * scale)
            ratio = max_h / cutout.height
            new_w = int(cutout.width * ratio)
            cutout = cutout.resize((new_w, max_h), Image.LANCZOS)
            pos = cfg.get("pos", [0.5, 0.45])
            x = int(pos[0] * dims[0] - new_w / 2)
            y = int(pos[1] * dims[1] - max_h / 2)
            img.paste(cutout, (x, y), cutout)
        except Exception as e:
            logger.warning(f"Could not paste cutout '{cutout_path}': {e}")

    def _paste_logo(self, img: Image.Image, club: str, cfg: dict, dims: tuple) -> None:
        if not cfg.get("visible", True):
            return
        size = tuple(cfg.get("size", [120, 120]))
        pos = cfg.get("pos", [0.05, 0.05])
        # Try exact slug then partial match
        slug = club.lower().replace(" ", "_") + ".png"
        logo_path = self.LOGOS_DIR / slug
        if not logo_path.exists():
            candidates = list(self.LOGOS_DIR.glob(f"*{club.split()[0].lower()}*.png")) if club else []
            if not candidates:
                return
            logo_path = candidates[0]
        self._paste_image_at(img, str(logo_path), pos, dims, size)

    def _draw_team(self, img: Image.Image, draw: ImageDraw.ImageDraw,
                   name: str, logo_url: Optional[str],
                   cfg: dict, dims: tuple, colors: dict) -> None:
        """Draw team logo + name for prematch card."""
        if logo_url:
            slug = logo_url.split("/")[-1]
            logo_path = self.LOGOS_DIR / slug
            if logo_path.exists():
                logo_size = tuple(cfg.get("logo_size", [300, 300]))
                logo_pos = cfg.get("logo_pos", [0.25, 0.45])
                self._paste_image_at(img, str(logo_path), logo_pos, dims, logo_size)
        name_cfg = {
            "pos": cfg.get("name_pos", [0.25, 0.6]),
            "font_size": cfg.get("font_size", 50),
            "anchor": cfg.get("anchor", "mm"),
        }
        self._draw_text(draw, name, name_cfg, dims, self._color(colors, "text_primary"))

    def _paste_image_at(self, img: Image.Image, path: str,
                        pos: list, dims: tuple, size: tuple) -> None:
        try:
            asset = Image.open(path).convert("RGBA")
            asset = asset.resize(size, Image.LANCZOS)
            x = int(pos[0] * dims[0] - size[0] / 2)
            y = int(pos[1] * dims[1] - size[1] / 2)
            img.paste(asset, (x, y), asset)
        except Exception as e:
            logger.warning(f"Could not paste image '{path}': {e}")

    def _draw_text(self, draw: ImageDraw.ImageDraw, text: str, cfg: dict,
                   dims: tuple, color: tuple,
                   bold: bool = False, opacity: Optional[int] = None) -> None:
        if not text:
            return
        pos = cfg.get("pos", [0.5, 0.5])
        font_size = cfg.get("font_size", 40)
        anchor = cfg.get("anchor", "mm")
        x = int(pos[0] * dims[0])
        y = int(pos[1] * dims[1])
        final_color = (*color, opacity if opacity is not None else 255)
        font = self._load_font(font_size, bold=bold)
        draw.text((x, y), text, fill=final_color, font=font, anchor=anchor)

    def _load_font(self, size: int, bold: bool = False) -> ImageFont.ImageFont:
        """Try to load Montserrat, fall back to PIL default."""
        name = "Montserrat-Bold.ttf" if bold else "Montserrat-Regular.ttf"
        candidates = [
            self.FONTS_DIR / name,
            self.FONTS_DIR / "Montserrat-Bold.ttf",
        ]
        for path in candidates:
            if path.exists():
                try:
                    return ImageFont.truetype(str(path), size)
                except Exception:
                    pass
        try:
            return ImageFont.load_default(size=size)
        except TypeError:
            return ImageFont.load_default()

    def _to_png_bytes(self, img: Image.Image) -> bytes:
        buf = BytesIO()
        img.convert("RGB").save(buf, format="PNG", optimize=True)
        buf.seek(0)
        return buf.read()
