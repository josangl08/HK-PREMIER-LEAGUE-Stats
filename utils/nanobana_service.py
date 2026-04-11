# ABOUTME: Service for generating high-quality background images using Gemini image generation models.
# ABOUTME: Uses ai_config image_gen tier hierarchy (Nano Banana Pro → Nano Banana 2 → Nano Banana → Imagen 4).

import json
import logging
import os
import time
from io import BytesIO
from pathlib import Path
from typing import Optional

from utils.ai_config import GOOGLE_API_KEY, AI_DEFAULTS

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Exhaustion cache — persists across app restarts with a TTL
# ---------------------------------------------------------------------------

_EXHAUSTION_CACHE_PATH = Path("cache/nanobana_exhausted.json")
_EXHAUSTION_TTL_SECONDS = 3600  # fallback TTL — overridden by Retry-After when present

# In-memory mirror (model_name → expiry timestamp)
_EXHAUSTED_UNTIL: dict[str, float] = {}


def _load_exhaustion_cache() -> None:
    """Populate in-memory dict from disk cache on first call."""
    if not _EXHAUSTION_CACHE_PATH.exists():
        return
    try:
        with open(_EXHAUSTION_CACHE_PATH, "r") as f:
            data = json.load(f)
        now = time.time()
        for model, expiry in data.items():
            if expiry > now:
                _EXHAUSTED_UNTIL[model] = expiry
    except Exception:
        pass  # corrupt cache — start fresh


def _parse_retry_after(exc: Exception) -> float:
    """Extract Retry-After seconds from a Google API 429 exception.
    Falls back to _EXHAUSTION_TTL_SECONDS if not found.
    """
    import re as _re
    err_str = str(exc)
    # Google API: "retryDelay":"30s"
    m = _re.search(r'"retryDelay"\s*:\s*"(\d+)', err_str)
    if m:
        return float(m.group(1))
    # Generic Retry-After: header value in seconds
    m = _re.search(r"[Rr]etry[_-]?[Aa]fter[\"']?\s*[=:]\s*[\"']?(\d+)", err_str)
    if m:
        return float(m.group(1))
    return float(_EXHAUSTION_TTL_SECONDS)


def _mark_exhausted(model_name: str, exc: Exception = None) -> None:
    """Mark a model as exhausted in memory and on disk, using Retry-After TTL when available."""
    ttl = _parse_retry_after(exc) if exc else float(_EXHAUSTION_TTL_SECONDS)
    expiry = time.time() + ttl
    _EXHAUSTED_UNTIL[model_name] = expiry
    try:
        _EXHAUSTION_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        existing: dict = {}
        if _EXHAUSTION_CACHE_PATH.exists():
            with open(_EXHAUSTION_CACHE_PATH, "r") as f:
                existing = json.load(f)
        existing[model_name] = expiry
        with open(_EXHAUSTION_CACHE_PATH, "w") as f:
            json.dump(existing, f)
    except Exception as e:
        logger.warning(f"Nanobana: could not persist exhaustion cache: {e}")


def _is_exhausted(model_name: str) -> bool:
    """Return True if the model is still in its exhaustion window."""
    expiry = _EXHAUSTED_UNTIL.get(model_name)
    if expiry is None:
        return False
    if time.time() < expiry:
        return True
    # TTL expired — remove entry
    _EXHAUSTED_UNTIL.pop(model_name, None)
    return False


# Load persisted cache at import time
_load_exhaustion_cache()

# ---------------------------------------------------------------------------
# Model tier list
# ---------------------------------------------------------------------------

_IMAGE_GEN_TIERS = [
    ("nanobana_pro", AI_DEFAULTS["image_gen"]["tier_1"], "gemini"),   # gemini-3-pro-image-preview
    ("nanobana_2",   AI_DEFAULTS["image_gen"]["tier_2"], "gemini"),   # gemini-3.1-flash-image-preview
    ("nanobana",     AI_DEFAULTS["image_gen"]["tier_3"], "gemini"),   # gemini-2.5-flash-image
    ("imagen_4",     "imagen-4.0-generate-001",          "imagen"),   # Last resort
]


# ---------------------------------------------------------------------------
# Generation helpers
# ---------------------------------------------------------------------------

def _generate_with_gemini_image(
    client, model_name: str, prompt: str, extra_images: list[dict] | None = None
) -> Optional[bytes]:
    """Calls a Gemini image-generation model via generate_content with IMAGE modality.

    extra_images: list of {"data": bytes, "mime": str} dicts prepended before the prompt
    (design references, team badges, player photo for style/color context).
    Note: response_mime_type must NOT be set for native image models — images are
    returned as inline_data, not as a MIME-typed response body.
    """
    from google.genai import types
    contents: list = []
    for img in (extra_images or []):
        contents.append(types.Part.from_bytes(data=img["data"], mime_type=img["mime"]))
    contents.append(prompt)
    response = client.models.generate_content(
        model=model_name,
        contents=contents,
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE"],
        ),
    )
    for part in (response.candidates[0].content.parts if response.candidates else []):
        if part.inline_data and part.inline_data.mime_type.startswith("image/"):
            return part.inline_data.data
    return None


def _generate_with_imagen(client, model_name: str, prompt: str) -> Optional[bytes]:
    """Calls Imagen via generate_images (separate API path)."""
    from google.genai import types
    response = client.models.generate_images(
        model=model_name,
        prompt=prompt,
        config=types.GenerateImagesConfig(
            number_of_images=1,
            include_rai_reason=True,
            output_mime_type="image/png",
        ),
    )
    if response.generated_images:
        return response.generated_images[0].image.image_bytes
    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_nanobana_image(parts: list) -> Optional[bytes]:
    """
    V4 Entry Point: Generates a 100% integrated card from a list of parts (bytes + strings).
    Tries the same tier hierarchy as background generation.
    """
    api_key = GOOGLE_API_KEY
    if not api_key:
        logger.error("Nanobana: GOOGLE_API_KEY not set.")
        return None

    from google import genai
    from google.genai import types as _types
    client = genai.Client(
        api_key=api_key,
        http_options=_types.HttpOptions(api_version="v1beta", timeout=120_000), # Extended timeout for high-fidelity
    )

    available = [
        (label, model, kind) for label, model, kind in _IMAGE_GEN_TIERS
        if not _is_exhausted(model) and kind == "gemini" # One-shot requires multimodal Gemini
    ]

    if not available:
        logger.warning("Nanobana: No multimodal models available for One-shot.")
        return None

    for label, model_name, _ in available:
        logger.info(f"Nanobana V4: trying {label} ({model_name})")
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=parts,
                config=_types.GenerateContentConfig(
                    response_modalities=["IMAGE"],
                ),
            )
            for part in (response.candidates[0].content.parts if response.candidates else []):
                if part.inline_data and part.inline_data.mime_type.startswith("image/"):
                    logger.info(f"Nanobana V4: Image generated via {label}.")
                    return part.inline_data.data
        except Exception as exc:
            err_str = str(exc)
            if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                _mark_exhausted(model_name, exc)
                continue
            logger.error(f"Nanobana V4: {label} error: {exc}")
            continue
    return None

def generate_nanobana_background(
    prompt: str,
    extra_images: list[dict] | None = None,
) -> Optional[bytes]:
    """
    Generates a background/card image using the Gemini image-gen tier hierarchy.
    Tries Nano Banana Pro → Nano Banana 2 → Nano Banana → Imagen 4.

    extra_images: list of {"data": bytes, "mime": str} — design references,
    team badges, player photo — passed to Gemini models as multimodal context.
    Ignored for Imagen (text-only API).

    Exhausted models are persisted to disk with a 1-hour TTL so subsequent
    calls (including after app restart) skip them immediately.
    """
    api_key = GOOGLE_API_KEY
    if not api_key:
        logger.error("Nanobana: GOOGLE_API_KEY not set.")
        return None

    from google import genai
    from google.genai import types as _types
    client = genai.Client(
        api_key=api_key,
        http_options=_types.HttpOptions(api_version="v1beta", timeout=90_000),  # 90s timeout
    )

    available = [
        (label, model, kind) for label, model, kind in _IMAGE_GEN_TIERS
        if not _is_exhausted(model)
    ]

    if not available:
        remaining = min(
            (exp - time.time() for exp in _EXHAUSTED_UNTIL.values() if exp > time.time()),
            default=0,
        )
        logger.warning(
            f"Nanobana: all image gen models exhausted (quota resets in ~{int(remaining/60)}m). "
            "Using gradient fallback."
        )
        return None

    n_refs = len(extra_images) if extra_images else 0
    logger.info(f"Nanobana: starting generation (extra_images={n_refs})")

    for label, model_name, kind in available:
        logger.info(f"Nanobana: trying {label} ({model_name})")
        try:
            if kind == "gemini":
                image_bytes = _generate_with_gemini_image(client, model_name, prompt, extra_images)
            else:
                # Imagen only accepts text — skip extra_images
                image_bytes = _generate_with_imagen(client, model_name, prompt)

            if image_bytes:
                logger.info(f"Nanobana: image generated via {label}.")
                return image_bytes
            logger.warning(f"Nanobana: {label} returned no image data.")

        except Exception as exc:
            err_str = str(exc)
            if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str or "spending cap" in err_str.lower():
                ttl = _parse_retry_after(exc)
                _mark_exhausted(model_name, exc)
                logger.warning(f"Nanobana: {label} quota exhausted — retry in ~{int(ttl//60)}m.")
                continue
            if "504" in err_str or "DEADLINE_EXCEEDED" in err_str or "timed out" in err_str.lower():
                logger.warning(f"Nanobana: {label} timed out — trying next tier.")
                continue
            if "503" in err_str or "UNAVAILABLE" in err_str:
                logger.warning(f"Nanobana: {label} unavailable — trying next tier.")
                continue
            logger.error(f"Nanobana: {label} unexpected error: {exc}")
            continue

    logger.error("Nanobana: all tiers failed.")
    return None


def save_nanobana_background(milestone_id: str, image_bytes: bytes) -> str:
    """
    Saves the generated background to the milestone's card directory.
    Returns the relative path to the saved image.
    """
    from callbacks.card_editor_callbacks import _CARD_DATA_ROOT
    from flask_login import current_user

    player_id = str(current_user.id) if current_user and current_user.is_authenticated else "unknown"
    bg_dir = _CARD_DATA_ROOT / player_id / milestone_id / "backgrounds"
    bg_dir.mkdir(parents=True, exist_ok=True)

    bg_path = bg_dir / "nanobana_bg.png"
    with open(bg_path, "wb") as f:
        f.write(image_bytes)

    return str(bg_path)
