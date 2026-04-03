# ABOUTME: Service for generating high-quality background images using Gemini (Nanobana).
# ABOUTME: Implements tier-based model selection from ai_config.

import logging
import os
from io import BytesIO
from pathlib import Path
from typing import Optional

from utils.ai_config import GOOGLE_API_KEY, AI_DEFAULTS

logger = logging.getLogger(__name__)

def generate_nanobana_background(prompt: str, tier: str = "tier_1") -> Optional[bytes]:
    """
    Generates a background image using Gemini/Imagen.
    Includes detailed debug logging of the prompt.
    """
    api_key = GOOGLE_API_KEY
    if not api_key:
        logger.error("Nanobana: GOOGLE_API_KEY not set.")
        return None

    # Using imagen-4.0-generate-001 which is available in your environment
    model_name = "imagen-4.0-generate-001" 
    
    logger.info("--- NANOBANA DEBUG ---")
    logger.info(f"Model: {model_name}")
    logger.info(f"Prompt sent to Image Gen: {prompt}")
    logger.info("----------------------")

    try:
        from google import genai
        from google.genai import types
        
        client = genai.Client(api_key=api_key, http_options={'api_version': 'v1beta'})
        
        # Imagen models usually use the 'models.generate_images' or 'models.predict'
        # In the new SDK, generate_images is the high-level API
        response = client.models.generate_images(
            model=model_name,
            prompt=prompt,
            config=types.GenerateImagesConfig(
                number_of_images=1,
                include_rai_reason=True,
                output_mime_type="image/png"
            )
        )
        
        if response.generated_images:
            logger.info("Nanobana: Image generated successfully.")
            image_data = response.generated_images[0].image.image_bytes
            return image_data
        
        logger.warning(f"Nanobana: No images generated. Response: {response}")
        return None

    except Exception as exc:
        logger.error(f"Nanobana unhandled error: {exc}")
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
