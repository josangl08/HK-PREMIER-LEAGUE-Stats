# ABOUTME: Verification script for the elite card agency and visual library.
# ABOUTME: Simulates a "Save Style" action to verify JSON and thumbnail generation.

import os
import sys
import json
from pathlib import Path

# Add project root to path
sys.path.append(os.getcwd())

from utils.card_renderer import compose_card
from utils.image_processing import get_team_assets

def verify_system():
    player_id = "manuelbleda"
    milestone_id = "verify_test_match"
    tmpl_id = "template_verification_run"
    
    # 1. Setup mock template directory
    tmpl_dir = Path(f"data/player_cards/{player_id}/templates")
    tmpl_dir.mkdir(parents=True, exist_ok=True)
    
    # 2. Mock Design Brief (simulating Option 1 / "Epic" concept)
    mock_brief = {
        "template": "A",
        "narrative": {
            "headline": "VERIFICATION",
            "supporting_story": "SYSTEM STATUS: OPTIMIZED",
            "caption": "Testing the new visual library system. #HKPL #EliteAgency",
            "emotion": "hype"
        },
        "design": {
            "layers": {
                "base_color": "#1a1a2e",
                "gradient": {"color1": "#00f2ff", "color2": "#000000"}
            },
            "typography": {
                "headline": {"rotation": -2, "stroke_width": 2, "stroke_fill": "#000000"}
            }
        },
        "layout_modifiers": {
            "headline": {"x": 50, "y": 25, "scale": 120, "visible": True},
            "player_photo": {"x": 50, "y": 95, "scale": 100, "visible": True},
            "home_logo": {"x": 15, "y": 15, "scale": 100, "visible": True},
            "away_logo": {"x": 85, "y": 15, "scale": 100, "visible": True},
            "home_jersey": {"x": 25, "y": 75, "scale": 80, "visible": True},
            "away_jersey": {"x": 75, "y": 75, "scale": 80, "visible": True}
        }
    }
    
    # 3. Mock Match Payload
    match_payload = {
        "home_team": "kitchee",
        "away_team": "eastern",
        "stadium": "Mong Kok Stadium",
        "kickoff_display": "20:00 HKT",
        "home_logo": "assets/team_logos/kitchee.png",
        "away_logo": "assets/team_logos/eastern.png",
        "competition_logo": "assets/competition_logos/hong_kong_premier_league.png"
    }

    print(f"--- VERIFICATION RUN: {tmpl_id} ---")
    
    # 4. Save JSON
    json_path = tmpl_dir / f"{tmpl_id}.json"
    with open(json_path, "w") as f:
        json.dump(mock_brief, f, indent=4)
    print(f"1. Saved JSON Template: {json_path}")

    # 5. Generate Visual Thumbnail (mimicking the callback logic)
    print("2. Generating PNG Thumbnail...", end=" ", flush=True)
    try:
        # We pass output_filename starting with 'template_' to trigger the thumbnail optimization
        img_path = compose_card(
            design_brief=mock_brief,
            player_photo_path=None, # Use None for test or find a sample
            output_dir=str(tmpl_dir),
            format="1:1",
            match_payload=match_payload,
            player_name="MANUEL BLEDA",
            output_filename=f"{tmpl_id}.png"
        )
        print(f"Done: {img_path}")
        
        # Verify sizes
        if img_path.exists():
            from PIL import Image
            with Image.open(img_path) as img:
                print(f"3. Verification Result: Thumbnail size is {img.size} (Expected 300x300 approx)")
                if img.size[0] <= 300:
                    print("SUCCESS: Visual Library optimization is working.")
                else:
                    print("WARNING: Thumbnail was not resized.")
    except Exception as e:
        print(f"Failed: {e}")

if __name__ == "__main__":
    verify_system()
