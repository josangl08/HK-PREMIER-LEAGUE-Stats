# ABOUTME: One-time script to remove backgrounds from all jersey assets.
# ABOUTME: Uses the rembg integration from utils.image_processing.

import os
import sys
from pathlib import Path

# Add project root to path
sys.path.append(os.getcwd())

from utils.image_processing import remove_background

JERSEY_DIR = Path("assets/team_jersey")

def main():
    if not JERSEY_DIR.exists():
        print(f"Error: {JERSEY_DIR} not found.")
        return

    print(f"Starting background removal for jerseys in {JERSEY_DIR}...")
    
    # Filter for .png files
    images = sorted(list(JERSEY_DIR.glob("*.png")))
    
    for img_path in images:
        print(f"Processing {img_path.name}...", end=" ", flush=True)
        try:
            with open(img_path, "rb") as f:
                img_bytes = f.read()
            
            # Use rembg utility
            bgrm_bytes = remove_background(img_bytes)
            
            # Overwrite original with background-removed PNG
            with open(img_path, "wb") as f:
                f.write(bgrm_bytes)
            print("Done.")
        except Exception as e:
            print(f"Failed: {e}")

    print("\nBackground removal complete.")

if __name__ == "__main__":
    main()
