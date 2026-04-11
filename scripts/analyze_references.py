# ABOUTME: Automated Design Deconstructor — Converts image references into usable Trend JSONs.
# ABOUTME: Each image in assets/design_references becomes a style template in assets/design_trends.

import base64
import os
import json
from pathlib import Path
from google import genai
from google.genai import types

def analyze_and_generate_trends():
    print("🚀 Starting Visual Intelligence Extraction...")
    api_key = os.environ.get('GOOGLE_API_KEY')
    if not api_key:
        print("❌ Error: GOOGLE_API_KEY not found.")
        return

    client = genai.Client(api_key=api_key, http_options=types.HttpOptions(api_version='v1beta'))
    ref_dir = Path('assets/design_references')
    trend_dir = Path('assets/design_trends')
    trend_dir.mkdir(parents=True, exist_ok=True)
    
    valid_exts = ['.png', '.jpg', '.jpeg', '.webp']
    
    for img_path in sorted(ref_dir.glob('*')):
        if img_path.suffix.lower() not in valid_exts:
            continue

        print(f"🎨 Analyzing: {img_path.name}...")
        
        with open(img_path, 'rb') as f:
            img_data = f.read()
        
        ext = img_path.suffix[1:].replace('jpg', 'jpeg')
        
        prompt = """
        Act as an Elite Sports Graphic Designer. Deconstruct this image into a JSON trend specification.
        The JSON must follow this exact structure:
        {
          "name": "Short Descriptive Name",
          "description": "Brief artistic summary",
          "visual_identity": {
            "typography": {"primary": "style desc", "style": "casing/spacing"},
            "color_mood": "describe lighting and palette",
            "composition": "rule of thirds, centered, etc."
          },
          "nanobana_prompt_injection": "A highly detailed, technical prompt fragment for an AI to replicate this lighting, atmosphere, and texture. Focus on materials like fog, neon, concrete, or cinematic light.",
          "archetype_rules": "where should the player and text be placed based on this design?"
        }
        Return ONLY the raw JSON.
        """

        try:
            response = client.models.generate_content(
                model='gemini-2.0-flash', # Fast and great for vision
                contents=[
                    types.Part.from_bytes(data=img_data, mime_type=f"image/{ext}"),
                    prompt
                ],
                config=types.GenerateContentConfig(response_mime_type="application/json")
            )
            
            trend_data = json.loads(response.text)
            
            # Save JSON with same name as image
            json_name = f"trend_{img_path.stem.lower().replace(' ', '_')}.json"
            with open(trend_dir / json_name, "w") as f:
                json.dump(trend_data, f, indent=2)
                
            print(f"✅ Generated: {json_name}")
            
        except Exception as e:
            print(f"⚠️ Failed {img_path.name}: {e}")

if __name__ == "__main__":
    analyze_and_generate_trends()
