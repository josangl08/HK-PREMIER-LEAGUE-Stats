# ABOUTME: Standalone script to extract design styles from reference images.
# ABOUTME: Deconstructs posters into JSON trends and synchronizes filenames for the Elite Agency.

import os
import io
import json
import logging
import re
import sys
from pathlib import Path
from typing import Optional, Dict, Any

# Ensure project root is in sys.path for internal imports
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Project imports
from utils.ai_config import GOOGLE_API_KEY, AI_DEFAULTS

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("DesignExtractor")

# --- Configuration ---
REF_DIR = Path("assets/design_references")
TREND_DIR = Path("assets/design_trends")

# Model to use for Vision analysis
ANALYSIS_MODEL = "gemini-3.1-pro-preview" # Ultra-high precision for Art Direction

# --- Schema Definition (Prompt) ---
EXTRACTION_PROMPT = """
You are an Elite Sports Art Director. Analyze the provided sports poster image and deconstruct its visual system.
Return STRICTLY a JSON object following this exact schema:

{
  "name": "A catchy, short name for this design style (e.g., 'Neon Stadium', 'Classic Editorial')",
  "description": "A brief one-sentence overview of the vibe.",
  "visual_identity": {
    "typography": {
      "primary": "Main fonts used (e.g., Impact, Helvetica Bold)",
      "secondary": "Support fonts",
      "style": "How the text is rendered (e.g., 'Glowy neon', 'Weathered', 'Clean uppercase')"
    },
    "color_palette": {
      "base": "Primary background/mood colors",
      "accents": ["HEX_CODE_1", "HEX_CODE_2"],
      "usage": "How accents are used (e.g., 'Spotlights and text highlights')"
    },
    "elements": {
      "background": "Description of the background scene",
      "overlays": ["Effect 1", "Effect 2"],
      "composition": "Rules for layout (e.g., 'Centered focus', 'Asymmetric with large text')"
    }
  },
  "nanobana_prompt_injection": "A highly optimized comma-separated list of keywords for an image generator to replicate this exact look.",
  "archetypes": ["Suitable match types, choose from: Epic, Derby, Tactical, Rivalry, Signing"]
}

Rules:
1. Return ONLY the JSON. No markdown blocks, no preamble.
2. Be technically precise with color descriptions and typography.
3. Identify the core 'DNA' that makes this specific design look professional.
"""

# --- Utility Functions ---

def slugify(text: str) -> str:
    """Converts a string into a safe snake_case filename."""
    text = text.lower()
    text = re.sub(r'[^\w\s-]', '', text)
    return re.sub(r'[-\s]+', '_', text).strip('-_')

def get_gemini_client():
    """Initializes the Google GenAI client."""
    if not GOOGLE_API_KEY:
        raise ValueError("GOOGLE_API_KEY not found in environment.")
    
    from google import genai
    from google.genai import types
    return genai.Client(
        api_key=GOOGLE_API_KEY,
        http_options=types.HttpOptions(api_version="v1beta")
    )

def analyze_image(client, image_path: Path) -> Optional[Dict[str, Any]]:
    """Sends the image to Gemini for deconstruction."""
    from google.genai import types
    
    logger.info(f"Analyzing: {image_path.name}")
    
    try:
        with open(image_path, "rb") as f:
            image_bytes = f.read()
            
        mime_type = "image/jpeg"
        if image_path.suffix.lower() == ".png": mime_type = "image/png"
        if image_path.suffix.lower() == ".webp": mime_type = "image/webp"

        response = client.models.generate_content(
            model=ANALYSIS_MODEL,
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                EXTRACTION_PROMPT
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.2
            )
        )
        
        return json.loads(response.text)
    except Exception as e:
        logger.error(f"Failed to analyze {image_path.name}: {e}")
        return None

# --- Main Execution ---

def run_extractor():
    """Scans for new images, analyzes them, and syncs filenames."""
    if not REF_DIR.exists():
        logger.error(f"Reference directory {REF_DIR} does not exist.")
        return

    TREND_DIR.mkdir(parents=True, exist_ok=True)
    
    client = get_gemini_client()
    
    # Supported image extensions
    extensions = {".jpg", ".jpeg", ".png", ".webp", ".avif"}
    
    all_files = list(REF_DIR.iterdir())
    all_images = [p for p in all_files if p.suffix.lower() in extensions]
    other_files = [p for p in all_files if p.is_file() and p.suffix.lower() not in extensions and not p.name.startswith('.')]
    
    logger.info(f"Found {len(all_images)} supported images in {REF_DIR}")
    if other_files:
        logger.info(f"Ignoring {len(other_files)} files with unsupported extensions: {[f.suffix for f in other_files]}")

    processed_count = 0
    skipped_count = 0

    for img_path in all_images:
        # 1. Check if already synchronized
        json_path = TREND_DIR / f"{img_path.stem}.json"
        if json_path.exists():
            skipped_count += 1
            continue

        # 2. Extract Style
        result = analyze_image(client, img_path)
        if not result:
            continue

        # 3. Process Result
        style_name = result.get("name", "Unknown Style")
        style_id = slugify(style_name)
        
        # 4. Save JSON
        new_json_path = TREND_DIR / f"{style_id}.json"
        with open(new_json_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=4)
            
        # 5. Rename Image to Match
        new_img_path = REF_DIR / f"{style_id}{img_path.suffix}"
        
        # If the name changed, rename it
        if img_path != new_img_path:
            # Check for collision
            if new_img_path.exists():
                logger.warning(f"Collision: {new_img_path.name} already exists. Appending timestamp.")
                import time
                style_id = f"{style_id}_{int(time.time())}"
                new_json_path = TREND_DIR / f"{style_id}.json"
                new_img_path = REF_DIR / f"{style_id}{img_path.suffix}"
                # Save again with new ID
                with open(new_json_path, "w", encoding="utf-8") as f:
                    json.dump(result, f, indent=4)

            img_path.rename(new_img_path)
            logger.info(f"Synchronized: {img_path.name} -> {new_img_path.name}")
        else:
            logger.info(f"Created trend for: {img_path.name}")

        processed_count += 1

    logger.info(f"Finished. Processed: {processed_count}, Skipped: {skipped_count}")

if __name__ == "__main__":
    try:
        run_extractor()
    except Exception as e:
        logger.error(f"Fatal error: {e}")
