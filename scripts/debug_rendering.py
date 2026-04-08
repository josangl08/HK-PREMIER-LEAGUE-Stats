# ABOUTME: Debug script to verify the rendering of a Post-Match stage with Sofascore data.
# ABOUTME: Simulates the logic used in the player portal to ensure Scenario A is triggered.

import sys
import os
import json
from datetime import datetime

# Add root to path
sys.path.append(os.getcwd())

from utils.stage_helpers import render_post_match
from utils.db_engine import SessionFactory
from models.db_models import MatchHistory, Player

def test_render():
    # 1. Get the match data from DB
    session = SessionFactory()
    match = session.query(MatchHistory).filter(
        MatchHistory.player_id == '125040',
        MatchHistory.date == datetime(2025, 12, 11)
    ).first()
    
    player = session.get(Player, '125040')
    
    if not match:
        print("❌ Match not found in DB")
        return

    print(f"--- Rendering Match: {match.opponent} ({match.date}) ---")
    
    # 2. Build the milestone payload
    raw_data = match.raw_data or {}
    ss_intel = raw_data.get("sofascore_intelligence", {})
    heatmap = ss_intel.get("heatmap", [])
    
    print(f"Data Check: ss_intel keys: {list(ss_intel.keys())}")
    print(f"Data Check: heatmap points: {len(heatmap)}")
    
    # Simulate EXACT payload structure from TimelineAggregator
    payload = {
        "match_id": match.id,
        "opponent": match.opponent,
        "date": match.date.strftime("%Y-%m-%d"),
        "competition": match.competition_name,
        "raw_data": raw_data,
        "rating": ss_intel.get("statistics", {}).get("rating"),
        "heatmap": heatmap,
        "match_stats": ss_intel.get("statistics", {}),
        "intelligence_meta": {
            "is_high_fidelity": True if ss_intel else False,
            "has_heatmap": True if heatmap else False
        },
        "player_stats": {
            "basic_info": {"name": player.name, "position_primary": player.position_main}
        }
    }
    
    # 3. Call the helper
    component = render_post_match(payload)
    
    # 4. Analyze the result
    comp_str = str(component)
    
    print("\n--- UI Analysis ---")
    if "stage-view--postmatch" in comp_str:
        print("✅ Base container found")
        
    # Check for Scenario A specific class or labels
    # Note: str(component) might not show all classes clearly, checking specific text
    if "Datos de alta fidelidad" in comp_str:
        print("✅ Scenario A (High-Fidelity) DETECTED in text")
    else:
        print("⚠️ Scenario B (Fallback) likely active")
        
    if "Heatmap" in comp_str:
        print("✅ Heatmap label found")
    
    if "totalPasses" in comp_str or "accuratePasses" in comp_str or "Matches" not in comp_str:
        # In Scenario A we show Pro Stats, in B we show Radar
        print("✅ Pro Stats structure found")
        
    if "glass-success" in comp_str:
        print("✅ Correct semantic tint applied (Green)")

    session.close()

if __name__ == "__main__":
    test_render()
