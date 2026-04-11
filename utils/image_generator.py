# ABOUTME: Backward-compatible image composition shim for legacy callbacks still importing CompositionMotor.
# ABOUTME: Bridges old card upload/export flows onto the current photo album utilities with simple dark-glass PNG outputs.

from __future__ import annotations

import logging
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from utils.image_processing import (
    MAX_PHOTOS,
    delete_player_photo,
    get_player_album,
    save_player_photo,
)

logger = logging.getLogger(__name__)


class CompositionMotor:
    """Compatibility layer for legacy player-card and prematch-card flows."""

    MAX_CUTOUTS = MAX_PHOTOS
    _SIZE_MAP = {
        "square": (1080, 1080),
        "portrait": (1080, 1350),
        "story": (1080, 1920),
        "landscape": (1920, 1080),
    }

    def process_player_photo(self, player_id: str, image_bytes: bytes) -> dict:
        """Save an uploaded player photo and its background-removed version."""
        filename = f"{player_id}_upload.png"
        return save_player_photo(player_id, image_bytes, filename)

    def get_cutouts(self, player_id: str) -> list[str]:
        """Return available background-removed cutout paths for a player."""
        album = get_player_album(player_id)
        return [item["bg_removed"] for item in album if item.get("bg_removed")]

    def delete_cutout(self, player_id: str, filename: str) -> bool:
        """Delete a cutout by filename, preserving the legacy callback contract."""
        album = get_player_album(player_id)
        for item in album:
            bg_removed = item.get("bg_removed")
            if bg_removed and Path(bg_removed).name == filename:
                return delete_player_photo(player_id, int(item["idx"]))
        return False

    def compose_player_card(
        self,
        player_id: str,
        stats: dict | None,
        club: str = "",
        size: str = "square",
    ) -> bytes:
        """Create a simple player card PNG for the legacy download flow."""
        stats = stats or {}
        width, height = self._get_canvas_size(size)
        canvas = self._build_card_shell(width, height, accent=(83, 190, 255, 255))
        self._paste_primary_cutout(canvas, player_id, width, height, max_height=int(height * 0.6))

        draw = ImageDraw.Draw(canvas)
        title_font = self._font(72)
        body_font = self._font(34)
        stat_font = self._font(42)

        name = str(stats.get("name") or player_id).upper()
        team_name = str(club or stats.get("team") or "HK PREMIER LEAGUE").upper()
        goals = stats.get("goals", 0)
        assists = stats.get("assists", 0)
        matches = stats.get("matches_played", 0)

        draw.text((60, 55), "PLAYER CARD", font=body_font, fill=(195, 235, 255, 230))
        draw.text((60, 105), name, font=title_font, fill=(255, 255, 255, 255))
        draw.text((60, 195), team_name, font=body_font, fill=(195, 195, 205, 255))

        self._draw_glass_panel(draw, 48, height - 250, width - 48, height - 60)
        self._draw_stat_block(draw, 96, height - 215, "MATCHES", matches, stat_font, body_font)
        self._draw_stat_block(draw, width // 2 - 80, height - 215, "GOALS", goals, stat_font, body_font)
        self._draw_stat_block(draw, width - 300, height - 215, "ASSISTS", assists, stat_font, body_font)

        return self._to_png_bytes(canvas)

    def compose_prematch_card(self, fixture: dict | None, size: str = "square") -> bytes:
        """Create a simple prematch social card PNG for legacy export."""
        fixture = fixture or {}
        width, height = self._get_canvas_size(size)
        canvas = self._build_card_shell(width, height, accent=(0, 214, 143, 255))
        draw = ImageDraw.Draw(canvas)

        title_font = self._font(96)
        vs_font = self._font(54)
        body_font = self._font(34)

        home = str(fixture.get("home_team") or "HOME").upper()
        away = str(fixture.get("away_team") or "AWAY").upper()
        competition = str(fixture.get("competition") or "HK PREMIER LEAGUE").upper()
        match_date = str(fixture.get("date") or fixture.get("kickoff_hkt") or "").strip()

        draw.text((60, 60), "MATCHDAY", font=body_font, fill=(210, 255, 236, 230))
        draw.text((60, 150), home, font=title_font, fill=(255, 255, 255, 255))
        draw.text((60, 270), "VS", font=vs_font, fill=(0, 214, 143, 255))
        draw.text((60, 340), away, font=title_font, fill=(255, 255, 255, 255))

        self._draw_glass_panel(draw, 48, height - 220, width - 48, height - 60)
        draw.text((86, height - 185), competition, font=body_font, fill=(255, 255, 255, 255))
        if match_date:
            draw.text((86, height - 128), match_date[:40], font=body_font, fill=(200, 200, 210, 255))

        return self._to_png_bytes(canvas)

    def compose_dossier_header(self, player_id: str, season: str) -> Image.Image:
        """Create a header image for the dossier PDF."""
        width, height = 1800, 450
        canvas = self._build_card_shell(width, height, accent=(83, 190, 255, 255))
        self._paste_primary_cutout(canvas, player_id, width, height, max_height=340, align_right=True)

        draw = ImageDraw.Draw(canvas)
        title_font = self._font(76)
        body_font = self._font(34)
        draw.text((60, 90), "PLAYER DOSSIER", font=body_font, fill=(195, 235, 255, 230))
        draw.text((60, 150), str(player_id).upper(), font=title_font, fill=(255, 255, 255, 255))
        draw.text((60, 255), f"Season {season}", font=body_font, fill=(205, 205, 215, 255))
        return canvas

    def _get_canvas_size(self, size: str) -> tuple[int, int]:
        return self._SIZE_MAP.get((size or "square").lower(), self._SIZE_MAP["square"])

    def _build_card_shell(
        self,
        width: int,
        height: int,
        accent: tuple[int, int, int, int],
    ) -> Image.Image:
        base = Image.new("RGBA", (width, height), (15, 18, 28, 255))
        overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        for y in range(height):
            mix = y / max(height - 1, 1)
            alpha = int(90 + 80 * mix)
            color = (
                int(24 + (accent[0] * 0.12)),
                int(28 + (accent[1] * 0.08)),
                int(38 + (accent[2] * 0.06)),
                alpha,
            )
            draw.line([(0, y), (width, y)], fill=color)

        draw.ellipse(
            (-int(width * 0.15), -int(height * 0.2), int(width * 0.5), int(height * 0.45)),
            fill=(accent[0], accent[1], accent[2], 44),
        )
        draw.ellipse(
            (int(width * 0.45), int(height * 0.25), int(width * 1.1), int(height * 0.95)),
            fill=(255, 255, 255, 20),
        )

        base.alpha_composite(overlay)
        return base

    def _paste_primary_cutout(
        self,
        canvas: Image.Image,
        player_id: str,
        width: int,
        height: int,
        max_height: int,
        align_right: bool = False,
    ) -> None:
        cutouts = self.get_cutouts(player_id)
        if not cutouts:
            return

        try:
            player_img = Image.open(cutouts[0]).convert("RGBA")
            scale = min(max_height / max(player_img.height, 1), (width * 0.42) / max(player_img.width, 1))
            new_size = (
                max(1, int(player_img.width * scale)),
                max(1, int(player_img.height * scale)),
            )
            player_img = player_img.resize(new_size, Image.LANCZOS)
            x = width - new_size[0] - 70 if align_right else width - new_size[0] - 40
            y = height - new_size[1] - 40
            shadow = Image.new("RGBA", (new_size[0] + 30, new_size[1] + 30), (0, 0, 0, 0))
            shadow_draw = ImageDraw.Draw(shadow)
            shadow_draw.rounded_rectangle(
                (20, 20, new_size[0] + 10, new_size[1] + 10),
                radius=24,
                fill=(0, 0, 0, 55),
            )
            canvas.alpha_composite(shadow, (x - 15, y - 10))
            canvas.paste(player_img, (x, y), player_img)
        except Exception as exc:
            logger.warning("Could not paste cutout for '%s': %s", player_id, exc)

    def _draw_glass_panel(self, draw: ImageDraw.ImageDraw, x1: int, y1: int, x2: int, y2: int) -> None:
        draw.rounded_rectangle(
            (x1, y1, x2, y2),
            radius=28,
            fill=(255, 255, 255, 22),
            outline=(255, 255, 255, 60),
            width=2,
        )

    def _draw_stat_block(
        self,
        draw: ImageDraw.ImageDraw,
        x: int,
        y: int,
        label: str,
        value: object,
        value_font: ImageFont.ImageFont,
        label_font: ImageFont.ImageFont,
    ) -> None:
        draw.text((x, y), str(value), font=value_font, fill=(255, 255, 255, 255))
        draw.text((x, y + 58), label, font=label_font, fill=(190, 190, 205, 255))

    def _font(self, size: int) -> ImageFont.ImageFont:
        try:
            return ImageFont.truetype("DejaVuSans-Bold.ttf", size)
        except Exception:
            return ImageFont.load_default()

    def _to_png_bytes(self, image: Image.Image) -> bytes:
        buffer = BytesIO()
        image.convert("RGB").save(buffer, format="PNG")
        return buffer.getvalue()
