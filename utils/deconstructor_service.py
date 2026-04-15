# ABOUTME: Deconstructor Service — Gemini Vision-based structural analysis of AI-generated Master Images.
# ABOUTME: Extracts bounding boxes (player zone, logos, text areas, atmosphere regions) as a MasterLayout dict.

# Standard Library
import base64
import io
import json
import logging
import os
from typing import Optional, TypedDict, List

# Third-party
from google import genai
from google.genai import types
from PIL import Image

# Project
from utils.ai_config import AI_DEFAULTS

_VISION_MODELS = [
    AI_DEFAULTS["worker"]["primary"],    # gemini-3-flash-preview
    AI_DEFAULTS["worker"]["fallback_1"], # gemini-2.5-flash
    AI_DEFAULTS["worker"]["fallback_2"], # gemini-2.5-flash-lite
]

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

class BBox(TypedDict):
    x: int
    y: int
    w: int
    h: int

class MasterLayout(TypedDict):
    player_bbox: BBox
    logo_home_bbox: BBox
    logo_away_bbox: BBox
    text_safe_area: BBox
    atmosphere_mask_regions: List[dict]  # each has {x, y, w, h, label}
    low_confidence: bool

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class DeconstructorValidationError(Exception):
    """Raised when the MasterLayout returned by Gemini Vision fails schema validation."""
    pass

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_client() -> genai.Client:
    api_key = os.environ.get("GOOGLE_API_KEY")
    return genai.Client(api_key=api_key, http_options=types.HttpOptions(api_version="v1beta"))


def _load_image_bytes(master_image_path: Optional[str], master_image_b64: Optional[str]) -> tuple[bytes, int, int]:
    """Returns (image_bytes, width, height). Path takes precedence over b64."""
    if master_image_path:
        with open(master_image_path, "rb") as f:
            image_bytes = f.read()
    elif master_image_b64:
        # Strip data URI prefix if present
        if "," in master_image_b64:
            master_image_b64 = master_image_b64.split(",", 1)[1]
        image_bytes = base64.b64decode(master_image_b64)
    else:
        raise ValueError("Either master_image_path or master_image_b64 must be provided.")

    img = Image.open(io.BytesIO(image_bytes))
    return image_bytes, img.width, img.height


_DECONSTRUCT_PROMPT = """
You are an elite visual analyst specializing in sports card design deconstruction.
Analyze this football card image and return a JSON object describing the structural layout.

Return ONLY valid JSON with this exact schema:
{
  "player_bbox": {"x": <int>, "y": <int>, "w": <int>, "h": <int>, "confidence": <float 0-1>},
  "logo_home_bbox": {"x": <int>, "y": <int>, "w": <int>, "h": <int>},
  "logo_away_bbox": {"x": <int>, "y": <int>, "w": <int>, "h": <int>},
  "text_safe_area": {"x": <int>, "y": <int>, "w": <int>, "h": <int>},
  "atmosphere_mask_regions": [
    {"x": <int>, "y": <int>, "w": <int>, "h": <int>, "label": "<smoke|particles|glare|fog>"}
  ]
}

Rules:
- All coordinates are in pixels from the top-left corner (0,0).
- player_bbox: bounding box of the central human/silhouette figure. confidence = how certain you are (0.0-1.0).
- logo_home_bbox: bottom-left logo zone.
- logo_away_bbox: bottom-right logo zone.
- text_safe_area: the primary rectangular area where text can be safely placed (avoid player and logos).
- atmosphere_mask_regions: list of regions containing smoke, particles, lens flares, or fog effects. May be empty [].
- If a zone is not clearly visible, set all values to 0 and omit the confidence key.
- Do NOT include any explanation outside the JSON.
"""


def _validate_layout(layout: dict, img_w: int, img_h: int) -> None:
    """Validates bbox values. Raises DeconstructorValidationError on any violation."""
    required_keys = ["player_bbox", "logo_home_bbox", "logo_away_bbox", "text_safe_area", "atmosphere_mask_regions"]
    for key in required_keys:
        if key not in layout:
            raise DeconstructorValidationError(f"Missing required key: '{key}'")

    bbox_keys = ["player_bbox", "logo_home_bbox", "logo_away_bbox", "text_safe_area"]
    for key in bbox_keys:
        bbox = layout[key]
        for field in ["x", "y", "w", "h"]:
            if field not in bbox:
                raise DeconstructorValidationError(f"Missing field '{key}.{field}'")
            val = bbox[field]
            if not isinstance(val, (int, float)):
                raise DeconstructorValidationError(f"'{key}.{field}' must be a number, got {type(val).__name__}")
            if val < 0:
                raise DeconstructorValidationError(f"'{key}.{field}' must be >= 0, got {val}")
        if bbox["x"] + bbox["w"] > img_w:
            raise DeconstructorValidationError(f"'{key}' extends beyond image width ({img_w}px): x={bbox['x']}, w={bbox['w']}")
        if bbox["y"] + bbox["h"] > img_h:
            raise DeconstructorValidationError(f"'{key}' extends beyond image height ({img_h}px): y={bbox['y']}, h={bbox['h']}")

    if not isinstance(layout["atmosphere_mask_regions"], list):
        raise DeconstructorValidationError("'atmosphere_mask_regions' must be a list")


def _apply_fallbacks(layout: dict, img_w: int, img_h: int) -> tuple[dict, bool]:
    """Applies confidence-based and missing-zone fallbacks. Returns (layout, low_confidence)."""
    low_confidence = False

    # Player bbox fallback
    player_conf = layout.get("player_bbox", {}).get("confidence", 1.0)
    if player_conf < 0.6:
        logger.warning(f"Deconstructor: player_bbox confidence={player_conf:.2f} < 0.6, using centre-column defaults")
        layout["player_bbox"] = {"x": int(img_w * 0.25), "y": int(img_h * 0.2), "w": int(img_w * 0.5), "h": int(img_h * 0.65)}
        low_confidence = True

    # Logo fallbacks — if a logo bbox is all zeros, use corner quadrant defaults (15% of dims)
    logo_size = int(min(img_w, img_h) * 0.15)
    if layout.get("logo_home_bbox", {}).get("w", 0) == 0:
        logger.warning("Deconstructor: logo_home_bbox absent, using bottom-left corner default")
        layout["logo_home_bbox"] = {"x": 0, "y": img_h - logo_size, "w": logo_size, "h": logo_size}
    if layout.get("logo_away_bbox", {}).get("w", 0) == 0:
        logger.warning("Deconstructor: logo_away_bbox absent, using bottom-right corner default")
        layout["logo_away_bbox"] = {"x": img_w - logo_size, "y": img_h - logo_size, "w": logo_size, "h": logo_size}

    # Ensure text_safe_area has a reasonable default if empty
    if layout.get("text_safe_area", {}).get("w", 0) == 0:
        layout["text_safe_area"] = {"x": int(img_w * 0.05), "y": int(img_h * 0.75), "w": int(img_w * 0.9), "h": int(img_h * 0.2)}

    # Clean confidence fields from bboxes (not part of the final MasterLayout schema)
    for key in ["player_bbox", "logo_home_bbox", "logo_away_bbox", "text_safe_area"]:
        layout[key].pop("confidence", None)

    # Coerce all bbox values to int
    for key in ["player_bbox", "logo_home_bbox", "logo_away_bbox", "text_safe_area"]:
        for field in ["x", "y", "w", "h"]:
            layout[key][field] = int(layout[key][field])

    return layout, low_confidence


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def deconstruct_master_image(
    master_image_path: Optional[str] = None,
    master_image_b64: Optional[str] = None,
) -> dict:
    """
    Analyses a Master Image using Gemini Vision and returns a MasterLayout dict.

    Parameters:
        master_image_path: Filesystem path to the Master Image (takes precedence over b64).
        master_image_b64: Base64-encoded image string (with or without data URI prefix).

    Returns:
        A MasterLayout dict with keys: player_bbox, logo_home_bbox, logo_away_bbox,
        text_safe_area, atmosphere_mask_regions, low_confidence.

    Raises:
        DeconstructorValidationError: If the Gemini response fails schema or bounds validation.
        ValueError: If neither input parameter is provided.
    """
    image_bytes, img_w, img_h = _load_image_bytes(master_image_path, master_image_b64)
    mime_type = "image/png"

    client = _get_client()
    image_part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)

    _DEFAULT_LAYOUT = {
        "player_bbox": {"x": 0, "y": 0, "w": 0, "h": 0, "confidence": 0.0},
        "logo_home_bbox": {"x": 0, "y": 0, "w": 0, "h": 0},
        "logo_away_bbox": {"x": 0, "y": 0, "w": 0, "h": 0},
        "text_safe_area": {"x": 0, "y": 0, "w": 0, "h": 0},
        "atmosphere_mask_regions": [],
    }
    layout = None
    for model_name in _VISION_MODELS:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=[_DECONSTRUCT_PROMPT, image_part],
                config=types.GenerateContentConfig(response_mime_type="application/json"),
            )
            layout = json.loads(response.text)
            break
        except json.JSONDecodeError as e:
            raise DeconstructorValidationError(f"Gemini returned non-JSON response: {e}") from e
        except Exception as e:
            err_str = str(e)
            if "404" in err_str or "NOT_FOUND" in err_str or "503" in err_str or "UNAVAILABLE" in err_str:
                logger.warning(f"Deconstructor: model {model_name} unavailable, trying next. ({e})")
                continue
            if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str or "spending cap" in err_str.lower():
                logger.warning(f"Deconstructor: Gemini Vision quota exhausted — using default layout.")
                layout = _DEFAULT_LAYOUT
                break
            raise DeconstructorValidationError(f"Gemini Vision call failed: {e}") from e
    if layout is None:
        logger.warning("Deconstructor: all vision models unavailable — using default layout.")
        layout = _DEFAULT_LAYOUT

    if not isinstance(layout, dict):
        raise DeconstructorValidationError(f"Expected a JSON object, got {type(layout).__name__}")

    # Apply fallbacks before validation (fallbacks produce valid values)
    layout, low_confidence = _apply_fallbacks(layout, img_w, img_h)

    # Validate the final layout
    _validate_layout(layout, img_w, img_h)

    layout["low_confidence"] = low_confidence
    return layout
