# ABOUTME: Simple matchday card generator — Gemini image-generation models receive design references + player context directly.
# ABOUTME: Single API call: references + player photos + match context → professional card PNG. No intermediate prompt step.

import logging
import os
from pathlib import Path

from google.genai import types

from data.competition_registry import get_competition_display_name
from utils.runtime_storage import PLAYER_CARDS_RUNTIME_ROOT

logger = logging.getLogger(__name__)

_DESIGN_REF_PATHS = [
    "assets/design_references/Sports Design - Official Matchday.jpg",
    "assets/design_references/Matchday _ Gameday _ Poster _ Sports graphic….jpg",
    "assets/design_references/OFFICIAL MATTHIAS GINTER'S MATCHDAY GRAPHIC….jpg",
]

_EXT_MIME = {
    "jpg": "image/jpeg", "jpeg": "image/jpeg",
    "png": "image/png", "webp": "image/webp", "avif": "image/avif",
}

# Gemini image-generation models in priority order — loaded from ai_config (Nano Banana tiers)
def _get_image_gen_models() -> list[str]:
    try:
        from utils.ai_config import AI_DEFAULTS
        ig = AI_DEFAULTS.get("image_gen", {})
        return [ig["tier_1"], ig["tier_2"], ig["tier_3"]]
    except Exception:
        return [
            "gemini-3-pro-image-preview",
            "gemini-3.1-flash-image-preview",
            "gemini-2.5-flash-image",
        ]

# Aspect ratio → canvas size for saving
_FORMAT_SIZES = {"1:1": (1080, 1080), "9:16": (1080, 1920), "16:9": (1920, 1080)}


def generate_matchday_card(
    player_id: str,
    match_payload: dict,
    player_profile: dict,
    player_photos: list,
    card_format: str = "1:1",
    output_dir: str = str(PLAYER_CARDS_RUNTIME_ROOT),
    progress_cb=None,
) -> Path:
    """
    Generate a professional matchday card in a single Gemini image-generation call.

    The model receives:
      - Design reference images (style transfer)
      - Player photos if available (appearance reference)
      - Match context as text
    And produces a ready-to-download card PNG.

    Args:
        player_id:      logged-in user/player id (for output path)
        match_payload:  dict with home_team, away_team, competition, date, etc.
        player_profile: dict with name, position, nationality, age
        player_photos:  list of dicts {'original': path, 'bg_removed': path}
        card_format:    '1:1' | '9:16' | '16:9'
        output_dir:     root directory for saving the card

    Returns:
        Path to the generated PNG.
    """
    from google import genai

    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY not set")

    client = genai.Client(api_key=api_key)
    if progress_cb:
        progress_cb(25, "Preparando referencias de diseño...")
    content_parts = _build_content_parts(match_payload, player_profile, player_photos)

    if progress_cb:
        progress_cb(45, "Enviando a Nano Banana...")
    image_bytes = _call_image_gen(client, content_parts, progress_cb=progress_cb)

    out_dir = Path(output_dir) / str(player_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    card_path = out_dir / "card_generated.png"
    card_path.write_bytes(image_bytes)
    logger.info("Card saved → %s", card_path)
    return card_path


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_content_parts(match_payload: dict, player_profile: dict, player_photos: list) -> list:
    """Assembles the multimodal content list: references + photos + instruction text."""
    from google.genai import types

    parts = []

    # 1. Design references (style transfer)
    loaded_refs = 0
    for ref_path in _DESIGN_REF_PATHS:
        p = Path(ref_path)
        if not p.exists():
            continue
        mime = _EXT_MIME.get(p.suffix.lower().lstrip("."), "image/jpeg")
        try:
            parts.append(types.Part.from_bytes(data=p.read_bytes(), mime_type=mime))
            loaded_refs += 1
        except Exception as e:
            logger.warning("Could not load design reference %s: %s", p, e)

    # 2. Player photos (appearance reference, max 2)
    player_name = player_profile.get("name", "the player")
    has_photos = False
    for photo in (player_photos or [])[:2]:
        path_str = photo.get("original") or photo.get("bg_removed")
        if not path_str:
            continue
        p = Path(path_str)
        if not p.exists():
            continue
        mime = "image/png" if p.suffix.lower() == ".png" else "image/jpeg"
        try:
            parts.append(types.Part.from_bytes(data=p.read_bytes(), mime_type=mime))
            has_photos = True
        except Exception as e:
            logger.warning("Could not load player photo %s: %s", p, e)

    # 3. Instruction prompt
    home = match_payload.get("home_team") or "Home FC"
    away = match_payload.get("away_team") or "Away FC"
    competition = get_competition_display_name(match_payload.get("competition") or "League")
    date = match_payload.get("date") or ""
    position = player_profile.get("position") or "Footballer"
    nationality = player_profile.get("nationality") or ""

    if has_photos:
        player_line = (
            f"The central hero is {player_name} ({position}"
            + (f", {nationality}" if nationality else "")
            + f") — use the player photos provided above as reference for their appearance. "
            f"Show them in a powerful dynamic action pose, cleanly cut out against the atmospheric background."
        )
    else:
        player_line = (
            "Include a dramatic dark silhouette of a professional footballer "
            "as the central element. Do NOT show a face."
        )

    instruction = f"""
You are an elite sports graphic designer. The images above are professional football matchday card design references (first {loaded_refs} images) {"and the player's photos (last images)" if has_photos else ""}.

Create a professional matchday card with EXACTLY this style and quality:

MATCH:
- {home} vs {away}
- Competition: {competition}
{"- Date: " + date if date else ""}
- Player: {player_name}

DESIGN (match the references precisely):
- Dark, cinematic atmosphere — stadium environment, dramatic lighting
- Large bold "MATCH DAY" typography as a dominant background element
- Team names displayed prominently: {home} / {away}
- Color palette derived from the teams' brand colors
- Smoke, haze and light-ray atmospheric effects
- {player_line}
- Full-bleed composition, no borders, photorealistic 4K quality
- Social media ready (professional sports broadcast aesthetic)

Generate the card image directly. Do not add any text explanation.
""".strip()

    parts.append(instruction)
    return parts


_IMAGE_GEN_TIMEOUT = 90  # seconds per model attempt


def _call_image_gen(client, content_parts: list, progress_cb=None) -> bytes:
    """
    Tries each Gemini image-generation model in priority order.
    Each attempt has a hard timeout of _IMAGE_GEN_TIMEOUT seconds.
    progress_cb(pct, label) is called periodically so the UI stays alive.
    Returns raw PNG bytes of the generated image.
    """
    import threading
    from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
    from google.genai import types

    def _attempt(model_name: str) -> bytes:
        response = client.models.generate_content(
            model=model_name,
            contents=content_parts,
            config=types.GenerateContentConfig(
                response_modalities=["image"],
            ),
        )
        for part in response.candidates[0].content.parts:
            if part.inline_data and part.inline_data.data:
                return part.inline_data.data
        raise RuntimeError("Model returned no image data in parts")

    last_exc = None
    models = _get_image_gen_models()
    for i, model_name in enumerate(models):
        logger.info("Trying Nano Banana model %d/%d: %s", i + 1, len(models), model_name)
        if progress_cb:
            progress_cb(50 + i * 10, f"Generando con {model_name.split('-')[1]}...")

        # Pulse a heartbeat thread so poll sees movement
        _stop = threading.Event()

        def _heartbeat(pct_start=50 + i * 10):
            tick = 0
            while not _stop.is_set():
                _stop.wait(6)
                if _stop.is_set():
                    break
                tick += 1
                if progress_cb:
                    progress_cb(min(pct_start + tick * 3, 88), f"Generando con IA... ({tick * 6}s)")

        hb = threading.Thread(target=_heartbeat, daemon=True)
        hb.start()

        try:
            with ThreadPoolExecutor(max_workers=1) as ex:
                future = ex.submit(_attempt, model_name)
                result = future.result(timeout=_IMAGE_GEN_TIMEOUT)
            _stop.set()
            logger.info("Image generated successfully by %s", model_name)
            return result
        except FuturesTimeout:
            _stop.set()
            logger.warning("Model %s timed out after %ds", model_name, _IMAGE_GEN_TIMEOUT)
            last_exc = TimeoutError(f"{model_name} timed out after {_IMAGE_GEN_TIMEOUT}s")
        except Exception as e:
            _stop.set()
            logger.warning("Model %s failed: %s", model_name, e)
            last_exc = e

    raise RuntimeError(f"All Nano Banana models failed. Last error: {last_exc}")
