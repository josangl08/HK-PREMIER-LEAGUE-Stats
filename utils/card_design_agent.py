# ABOUTME: Elite One-Shot Design Agency Agent — V4 (Integrated Multimodal Generation).
# ABOUTME: Flow: Match Intelligence → Art Director → Design Studio (Nano Banana) → Validator.
# ABOUTME: Nano Banana generates 100% of the card (integrated subject, badges, and text).

import json
import logging
import os
import base64
import time
import random
from pathlib import Path
from datetime import datetime, timezone
from typing import TypedDict, List, Optional, Dict, Any, Union, Callable

# Third-party
from langgraph.graph import StateGraph, END
from google import genai
from google.genai import types

# Project
from utils.ai_config import AI_DEFAULTS
from utils.image_processing import get_player_album, get_team_assets

logger = logging.getLogger(__name__)

# --- State Definition ---
class AgentState(TypedDict):
    # Context
    match_payload: Dict[str, Any]
    player_profile: Dict[str, Any]
    is_post_game: bool
    format: str # Added format
    
    # Intelligence
    match_intelligence: Dict[str, Any]
    design_strategy: Dict[str, Any]
    
    # Artifacts
    player_photo_path: Optional[str]
    generated_card_path: Optional[str]
    agency_status: str
    progress: Dict[str, Any]
    on_progress: Optional[Callable[[Dict[str, Any]], None]]
    error: Optional[str]

# --- Node 1: Match Intelligence Collector ---
def match_intelligence_node(state: AgentState) -> AgentState:
    """Gathers all game/player context (teams, venue, time, colors, and post-game stats)."""
    p = {"phase": "Analizando inteligencia del partido...", "pct": 10}
    state["progress"] = p
    if state.get("on_progress"): state["on_progress"](p)

    match = state["match_payload"]
    player_id = match.get("player_id", "unknown")
    
    # 1. Determine if it's pre or post game (based on existence of goals/minutes or explicit flag)
    is_post = state.get("is_post_game", False) or (match.get("minutes_played") is not None)
    
    # 2. Get Team Branding
    from callbacks.player_portal_callbacks import _get_team_colors
    home_team = match.get("home_team", "Home Team")
    away_team = match.get("away_team", "Away Team")
    
    intel = {
        "is_post_game": is_post,
        "home": {"name": home_team, "colors": _get_team_colors(home_team)},
        "away": {"name": away_team, "colors": _get_team_colors(away_team)},
        "venue": match.get("venue", "Stadium"),
        "date": match.get("date", "TBD"),
        "competition": match.get("competition", "HKPL"),
    }
    
    # 3. Add Performance Stats for Post-Game
    if is_post:
        intel["stats"] = {
            "score": f"{match.get('home_score', 0)} - {match.get('away_score', 0)}",
            "rating": match.get("rating", 0.0),
            "goals": match.get("goals", 0),
            "assists": match.get("assists", 0),
            "minutes": match.get("minutes_played", 0),
        }
        
    return {**state, "match_intelligence": intel, "is_post_game": is_post}

# --- Node 2: Art Director Strategist ---
def art_director_node(state: AgentState) -> AgentState:
    """Selects Trend, Archetype and builds the Master Prompt for Nano Banana."""
    p = {"phase": "Definiendo estrategia visual...", "pct": 30}
    state["progress"] = p
    if state.get("on_progress"): state["on_progress"](p)

    intel = state["match_intelligence"]
    is_post = state["is_post_game"]
    fmt = state.get("format", "9:16")
    
    # 1. Select Trend based on context
    trend_path = Path("assets/design_trends/urban_gritty.json") # Default
    if intel["competition"] in ["AFC", "Cup"]:
        trend_path = Path("assets/design_trends/minimal_luxury.json")
    
    try:
        with open(trend_path, "r") as f:
            trend = json.load(f)
    except:
        trend = {"name": "Elite Sports", "nanobana_prompt_injection": "Professional sports graphic."}

    # 2. Select Archetype from Teardown Rules
    # Archetype A (God Mode) for Pre-game Hype
    # Archetype B (Editorial) for Post-game Stats
    archetype = "Archetype B: Editorial Split" if is_post else "Archetype A: God Mode (Centered Action)"
    
    # 3. Build Prompt
    prompt = f"""
    Create an ELITE professional matchday poster for Instagram ({fmt} format).
    STYLE: {trend['name']}. {trend.get('nanobana_prompt_injection', '')}
    COMPOSITION: Use {archetype} rules from the elite design manual.
    
    CONTEXT:
    - Match: {intel['home']['name']} vs {intel['away']['name']}
    - Venue: {intel['venue']}
    - Date: {intel['date']} (MANDATORY: Show this date clearly in the design)
    """
    
    if is_post:
        s = intel['stats']
        prompt += f"\nPOST-GAME HIGHLIGHTS: Result {s['score']}, Player Rating {s['rating']}, Goals {s['goals']}, Assists {s['assists']}."
        prompt += "\nINTEGRATION: Integrate these stats as bold, cinematic graphic elements in the composition."
    else:
        prompt += "\nPRE-GAME HYPE: Focus on the 'MATCHDAY' typography and the stadium atmosphere."

    prompt += "\nULTRA-FIDELITY RULES: 100% integrated design. The player photo MUST be the hero, illuminated by the stadium lights. Badges and Text MUST be part of the scene, not floating stickers."

    return {**state, "design_strategy": {"prompt": prompt, "trend": trend["name"]}}

# --- Node 3: Design Studio (Nano Banana One-Shot) ---
def design_studio_node(state: AgentState) -> AgentState:
    """The core engine. Sends all visual materials to Gemini for a 100% integrated result."""
    p = {"phase": "Nano Banana está diseñando tu obra maestra...", "pct": 60}
    state["progress"] = p
    if state.get("on_progress"): state["on_progress"](p)

    t0 = time.time()
    
    match = state["match_payload"]
    player_id = match.get("player_id", "unknown")
    match_id = str(match.get("fixture_id") or match.get("milestone_id") or "match")
    
    # 1. Prepare Vision Parts
    parts = []
    
    # A. Player Photo (The most important)
    photos = get_player_album(player_id)
    photo_path = None
    selected_idx = match.get("selected_photo_idx") # Passed from callback
    
    if photos:
        entry = None
        if selected_idx is not None:
            entry = next((p for p in photos if p["idx"] == selected_idx), photos[0])
        else:
            entry = photos[0]
            
        photo_path = entry.get("original") # Let IA handle the integration better from original
        if photo_path and os.path.exists(photo_path):
            with open(photo_path, "rb") as f:
                parts.append(types.Part.from_bytes(data=f.read(), mime_type="image/jpeg"))
    
    # B. Team Badges
    for team_key in ["home_team", "away_team"]:
        team_name = match.get(team_key)
        assets = get_team_assets(team_name)
        logo_path = assets.get("logo_png")
        if logo_path and os.path.exists(logo_path):
            with open(logo_path, "rb") as f:
                parts.append(types.Part.from_bytes(data=f.read(), mime_type="image/png"))

    # C. Design Reference (Visual Guide - Variety)
    ref_dir = Path("assets/design_references")
    refs = list(ref_dir.glob("*.jpg"))
    if refs:
        chosen_ref = random.choice(refs)
        with open(chosen_ref, "rb") as f:
            parts.append(types.Part.from_bytes(data=f.read(), mime_type="image/jpeg"))

    # D. Instructions
    parts.append(state["design_strategy"]["prompt"])

    # 2. Call Nano Banana
    try:
        from utils.nanobana_service import generate_nanobana_image
        image_bytes = generate_nanobana_image(parts)
        
        output_dir = Path("data/player_cards") / str(player_id) / str(match_id)
        output_dir.mkdir(parents=True, exist_ok=True)
        final_path = output_dir / f"card_{int(time.time())}.png"
        
        with open(final_path, "wb") as f:
            f.write(image_bytes)
            
        return {**state, "generated_card_path": str(final_path), "agency_status": "Success: Integrated card generated."}
    except Exception as e:
        logger.error(f"Nano Banana failed: {e}")
        return {**state, "error": str(e), "agency_status": "Failed: Nano Banana error."}

# --- Node 4: Validator & Fallback ---
def validator_node(state: AgentState) -> AgentState:
    """Saves the result and executes Pillow fallback if IA failed."""
    if state.get("generated_card_path") and not state.get("error"):
        p = {"phase": "¡Diseño de élite completado!", "pct": 100}
        state["progress"] = p
        if state.get("on_progress"): state["on_progress"](p)
        return state

    # --- FALLBACK: Use Pillow Compositor ---
    p = {"phase": "IA falló. Generando diseño de emergencia (Pillow)...", "pct": 80}
    state["progress"] = p
    if state.get("on_progress"): state["on_progress"](p)
    try:
        from utils.card_compositor import compose_precision_card
        match = state["match_payload"]
        player_id = match.get("player_id", "unknown")
        match_id = str(match.get("fixture_id") or match.get("milestone_id") or "match")
        output_dir = str(Path("data/player_cards") / str(player_id) / str(match_id))
        
        card_path = compose_precision_card(
            background_image_path=None, # Will use gradient
            player_photo_path=state.get("player_photo_path"),
            match_payload=match,
            player_name=state.get("player_profile", {}).get("name", "PLAYER"),
            output_dir=output_dir,
            card_format="9:16",
        )
        return {**state, "generated_card_path": str(card_path), "agency_status": "Fallback: Pillow card generated."}
    except Exception as e:
        return {**state, "error": f"Total failure: {e}", "agency_status": "Critical: Fallback failed."}

# --- Graph Construction ---
def run_card_design_agent(match_payload: Dict, player_profile: Dict, card_format: str = "9:16", on_progress: Optional[Callable] = None) -> Dict:
    """Entry point for the One-Shot Agency."""
    builder = StateGraph(AgentState)
    
    builder.add_node("intelligence", match_intelligence_node)
    builder.add_node("strategy", art_director_node)
    builder.add_node("studio", design_studio_node)
    builder.add_node("validator", validator_node)
    
    builder.set_entry_point("intelligence")
    builder.add_edge("intelligence", "strategy")
    builder.add_edge("strategy", "studio")
    builder.add_edge("studio", "validator")
    builder.add_edge("validator", END)
    
    graph = builder.compile()
    
    initial_state = {
        "match_payload": match_payload,
        "player_profile": player_profile,
        "is_post_game": False,
        "format": card_format,
        "generated_card_path": None,
        "agency_status": "Starting...",
        "progress": {"phase": "Iniciando Agencia Elite...", "pct": 0},
        "on_progress": on_progress,
        "error": None
    }
    
    final_state = graph.invoke(initial_state)
    return final_state
