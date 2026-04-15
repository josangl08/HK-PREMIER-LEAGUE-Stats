# ABOUTME: Surgeon Service — Imagen 3 Edit API wrapper for player-zone inpainting and atmosphere overlay extraction.
# ABOUTME: Provides inpaint_background() with exponential-backoff retry and graceful fallback, plus extract_atmosphere_overlays().

# Standard Library
import io
import logging
import os
import time
from pathlib import Path
from typing import List, Optional

# Third-party
from google import genai
from google.genai import types
from PIL import Image

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_RETRIES = 3
_BACKOFF_SECONDS = [1, 2, 4]

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class InpaintingServiceError(Exception):
    """Raised when all Imagen 3 Edit API retries are exhausted."""
    pass

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_client() -> genai.Client:
    api_key = os.environ.get("GOOGLE_API_KEY")
    return genai.Client(api_key=api_key, http_options=types.HttpOptions(api_version="v1beta"))


def _build_inpaint_mask(img_w: int, img_h: int, player_bbox: dict) -> Image.Image:
    """Creates a white-on-black mask image where the player bbox region is white (to be inpainted)."""
    mask = Image.new("RGB", (img_w, img_h), (0, 0, 0))
    x, y, w, h = int(player_bbox["x"]), int(player_bbox["y"]), int(player_bbox["w"]), int(player_bbox["h"])
    # Draw white rectangle for the area to inpaint
    from PIL import ImageDraw
    draw = ImageDraw.Draw(mask)
    draw.rectangle([x, y, x + w, y + h], fill=(255, 255, 255))
    return mask


def _call_imagen_inpaint(client: genai.Client, image_bytes: bytes, mask_bytes: bytes, img_w: int, img_h: int) -> bytes:
    """Calls the Imagen 3 Edit API and returns the inpainted image bytes."""
    response = client.models.edit_image(
        model="imagen-3.0-capability-001",
        prompt="Seamlessly fill the masked region with a realistic, coherent sports card background that matches the surrounding environment, lighting, and color palette. No human figures in the filled area.",
        reference_images=[
            types.RawReferenceImage(
                reference_id=1,
                reference_image=types.Image(image_bytes=image_bytes, mime_type="image/png"),
            ),
            types.MaskReferenceImage(
                reference_id=2,
                reference_image=types.Image(image_bytes=mask_bytes, mime_type="image/png"),
                config=types.MaskReferenceConfig(
                    mask_mode="MASK_MODE_USER_PROVIDED",
                ),
            ),
        ],
        config=types.EditImageConfig(
            edit_mode="EDIT_MODE_INPAINT_REMOVAL",
            number_of_images=1,
            output_mime_type="image/png",
        ),
    )
    if not response.generated_images:
        raise InpaintingServiceError("Imagen 3 returned no generated images.")
    return response.generated_images[0].image.image_bytes


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def inpaint_background(
    master_image_path: str,
    player_bbox: dict,
    fallback: bool = False,
) -> Path:
    """
    Inpaints the player zone in the Master Image using Imagen 3 Edit API.

    Saves the result as `<stem>_bg_inpainted.png` in the same directory.

    Parameters:
        master_image_path: Path to the Master Image PNG.
        player_bbox: Bounding box dict {x, y, w, h} in pixels.
        fallback: If True and all retries fail, log a WARNING and return the original
                  master_image_path instead of raising InpaintingServiceError.

    Returns:
        Path to the inpainted PNG (or original path on fallback failure).

    Raises:
        InpaintingServiceError: If all retries fail and fallback=False.
    """
    master_path = Path(master_image_path)
    output_path = master_path.parent / f"{master_path.stem}_bg_inpainted.png"

    with open(master_path, "rb") as f:
        image_bytes = f.read()

    img = Image.open(io.BytesIO(image_bytes))
    img_w, img_h = img.width, img.height

    mask = _build_inpaint_mask(img_w, img_h, player_bbox)
    mask_buffer = io.BytesIO()
    mask.save(mask_buffer, format="PNG")
    mask_bytes = mask_buffer.getvalue()

    client = _get_client()
    last_error: Optional[Exception] = None

    _VERTEX_ONLY_MSG = "only supported in the Vertex AI client"

    for attempt in range(MAX_RETRIES):
        try:
            result_bytes = _call_imagen_inpaint(client, image_bytes, mask_bytes, img_w, img_h)
            result_img = Image.open(io.BytesIO(result_bytes))
            # Preserve original dimensions
            if result_img.size != (img_w, img_h):
                result_img = result_img.resize((img_w, img_h), Image.LANCZOS)
            result_img.save(str(output_path), "PNG")
            return output_path
        except Exception as e:
            last_error = e
            logger.warning(f"inpaint_background attempt {attempt + 1}/{MAX_RETRIES} failed: {e}")
            # edit_image is Vertex AI-only — no point retrying with api_key client
            if _VERTEX_ONLY_MSG in str(e):
                logger.warning("inpaint_background: edit_image requires Vertex AI client (AI_METHOD=vertexai). Skipping retries.")
                break
            if attempt < MAX_RETRIES - 1:
                time.sleep(_BACKOFF_SECONDS[attempt])

    error_msg = f"Inpainting failed. Last error: {last_error}"
    if fallback:
        logger.warning(f"inpaint_background fallback: {error_msg}. Returning original master image.")
        return master_path
    raise InpaintingServiceError(error_msg) from last_error


def extract_atmosphere_overlays(
    master_image_path: str,
    atmosphere_regions: list,
) -> List[Path]:
    """
    Crops atmosphere overlay regions from the Master Image with RGBA preservation.

    Saves each crop as `<stem>_<label>_overlay.png` in the same directory.

    Parameters:
        master_image_path: Path to the Master Image PNG.
        atmosphere_regions: List of dicts with {x, y, w, h, label} in pixels.

    Returns:
        List of Paths to the saved overlay PNGs. Empty list if atmosphere_regions is empty.
    """
    if not atmosphere_regions:
        return []

    master_path = Path(master_image_path)
    img = Image.open(master_path).convert("RGBA")
    saved_paths: List[Path] = []

    for region in atmosphere_regions:
        x = int(region.get("x", 0))
        y = int(region.get("y", 0))
        w = int(region.get("w", 0))
        h = int(region.get("h", 0))
        label = str(region.get("label", "overlay")).replace(" ", "_")

        if w <= 0 or h <= 0:
            logger.warning(f"extract_atmosphere_overlays: skipping region with invalid dimensions w={w}, h={h}")
            continue

        crop = img.crop((x, y, x + w, y + h))
        out_path = master_path.parent / f"{master_path.stem}_{label}_overlay.png"
        crop.save(str(out_path), "PNG")
        saved_paths.append(out_path)

    return saved_paths
