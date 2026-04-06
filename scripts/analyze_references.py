# ABOUTME: Automated reverse-engineering script for sports design references.
# ABOUTME: Extracts layout patterns and compositor rules using Gemini 3 Pro Vision.

import base64
import os
import json
from pathlib import Path
from google import genai
from google.genai import types

def analyze():
    print("Initiating Elite Reverse Engineering...")
    api_key = os.environ.get('GOOGLE_API_KEY')
    if not api_key:
        print("Error: GOOGLE_API_KEY not found in environment.")
        return

    client = genai.Client(api_key=api_key, http_options=types.HttpOptions(api_version='v1beta'))
    ref_dir = Path('assets/design_references')
    
    contents = [
        "Act as an Elite Creative Director for a top sports brand (like Nike or the Premier League).",
        "Perform a rigorous reverse-engineering analysis (tear-down) of the provided professional matchday posters."
    ]

    valid_exts = ['.png', '.jpg', '.jpeg', '.webp']
    loaded_count = 0
    for img_path in sorted(ref_dir.glob('*')):
        if img_path.suffix.lower() in valid_exts:
            try:
                with open(img_path, 'rb') as f:
                    data = f.read()
                ext = img_path.suffix[1:].replace('jpg', 'jpeg')
                contents.append(types.Part.from_bytes(data=data, mime_type=f"image/{ext}"))
                print(f"Loaded {img_path.name}")
                loaded_count += 1
            except Exception as e:
                print(f"Skipped {img_path.name}: {e}")

    if loaded_count == 0:
        print("No valid images found to analyze.")
        return

    contents.append("""
    Please analyze these designs and extract the ultimate Anatomy of an Elite Matchday Poster.
    Provide a highly detailed Markdown report detailing:
    1. The Layer Hierarchy (The Sandwich): Exactly what layers exist from back to front?
    2. Common Layout Archetypes: Where are logos, match details, and the player usually placed? Give me exact X, Y, Scale percentage estimates (0-100%).
    3. Integration Effects: How do they avoid the sticker effect? What specific lighting, shadows, rims, textures, or atmospheric effects (smoke, fog, gradients) are used to blend the player into the background?
    4. Typography: Scale, weight, placement, contrast, and negative space usage.
    5. The Pro vs Amateur Difference: What elevates these?

    Keep it extremely actionable for a developer building a Python (Pillow) rendering pipeline. Give me exact structural rules and coordinate ideas for the engine.
    """)

    print("\nSending images to Gemini 3 Pro Vision for analysis. Please wait...\n")
    try:
        response = client.models.generate_content(
            model='gemini-3-pro-preview',
            contents=contents
        )
        
        out_file = Path("docs/design_teardown.md")
        out_file.parent.mkdir(parents=True, exist_ok=True)
        with open(out_file, "w") as f:
            f.write(response.text)
            
        print(f"Analysis complete! 🚀\nReport saved to: {out_file}")
        
    except Exception as e:
        print('API Error:', e)

if __name__ == "__main__":
    analyze()
