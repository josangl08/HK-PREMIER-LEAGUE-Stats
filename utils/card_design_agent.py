# ABOUTME: Elite Design Agency Agent (LangGraph) with Strict Layout Archetypes.
# ABOUTME: Implements the "Tear-down" rules: God Mode, Editorial Split, and Tactical Dual.
# ABOUTME: Enforces architectural typography and multi-pass compositor logic.

import json
import logging
import os
import re
import base64
from pathlib import Path
from datetime import datetime, timezone
from typing import TypedDict, List, Optional, Dict, Any, Union

# Third-party
from langgraph.graph import StateGraph, END
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

# --- Configuration & Logging ---
TRACE_FILE = Path("cache/design_agency_trace.json")

def _log_agency_step(node_name: str, input_summary: Any, output_data: Any):
    try:
        TRACE_FILE.parent.mkdir(parents=True, exist_ok=True)
        trace = []
        if TRACE_FILE.exists():
            try:
                with open(TRACE_FILE, "r") as f: trace = json.load(f)
            except: trace = []
        trace.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "node": node_name,
            "input": str(input_summary)[:1000],
            "output": output_data
        })
        with open(TRACE_FILE, "w") as f: json.dump(trace[-50:], f, indent=2)
    except Exception as e: logger.error(f"Failed to log: {e}")

# --- Model Constants ---
_STRATEGIST_MODEL = "gemini-3-flash-preview" 
_ART_DIRECTOR_MODEL = "gemini-3-pro-preview" 
_LAYOUT_MODEL = "gemini-3-flash-preview"
_CRITIC_MODEL = "gemini-3-pro-preview"

# --- State Schemas ---

class DesignBrief(TypedDict):
    narrative: dict
    design: dict
    layout_modifiers: dict
    nanobana_background_prompt: str
    selected_photo_idx: Optional[int]
    agency_status: Optional[str]

class AgentState(TypedDict):
    match_payload: dict
    player_profile: dict
    team_colors: dict
    player_history: list
    has_player_photo: bool
    card_type: str
    player_preferences: dict
    tone: str
    context: dict
    narrative_results: dict
    style_concepts: List[dict]
    proposals: List[dict]
    agency_status: str
    error: Optional[str]

# --- Client Factory ---

def _get_client():
    api_key = os.environ.get("GOOGLE_API_KEY")
    return genai.Client(api_key=api_key, http_options=types.HttpOptions(api_version="v1beta"))

# --- Normalization Helpers ---

def _ensure_dict(val: Any, fallback: dict = None) -> dict:
    if isinstance(val, dict): return val
    if isinstance(val, list) and len(val) > 0: return _ensure_dict(val[0], fallback)
    return fallback if fallback is not None else {}

def _process_colors(color_val: Any) -> Any:
    if isinstance(color_val, list): return [str(c) for c in color_val if str(c).startswith("#")]
    if isinstance(color_val, str) and color_val.startswith("#"): return color_val
    return "#050505"

def _get_design_references() -> List[Dict[str, Any]]:
    refs = []
    ref_dir = Path("assets/design_references")
    if not ref_dir.exists(): return []
    for img_path in sorted(ref_dir.glob("*")):
        if img_path.suffix.lower() in [".png", ".jpg", ".jpeg", ".webp"]:
            try:
                with open(img_path, "rb") as f: data = f.read()
                ext = img_path.suffix[1:].replace('jpg', 'jpeg')
                refs.append({"name": img_path.name, "data": base64.b64encode(data).decode("utf-8"), "mime": f"image/{ext}"})
            except: continue
    return refs

# --- Nodes ---

def strategist_node(state: AgentState) -> AgentState:
    client = _get_client()
    match = state["match_payload"]
    player = state["player_profile"]
    
    prompt = f"""Act as a Professional Football Analyst and Social Media Manager.
    Analyze this match data and player profile to create:
    1. A technical match report (2-3 paragraphs) highlighting key moments and the player's performance.
    2. An engaging Instagram caption with relevant emojis.
    3. A list of 5-8 trending hashtags (including #HKPL, #HongKongFootball, and team/player specific tags).

    MATCH DATA: {json.dumps(match)}
    PLAYER PROFILE: {json.dumps(player)}
    
    Return JSON: {{"report": "...", "instagram_caption": "...", "hashtags": ["#tag1", "#tag2"]}}
    """
    
    try:
        res = client.models.generate_content(model=_STRATEGIST_MODEL, contents=prompt, config=types.GenerateContentConfig(response_mime_type="application/json"))
        raw = _ensure_dict(json.loads(res.text))
        final = {
            "report": raw.get("report", "Analysis pending..."),
            "instagram_caption": raw.get("instagram_caption", "Matchday vibes!"),
            "hashtags": raw.get("hashtags", ["#HKPL", "#Matchday"]),
            "headline": "MATCHDAY",
            "subtitle": "READY"
        }
        return {**state, "narrative_results": final, "agency_status": "Strategist: Match report and caption generated."}
    except Exception as e:
        logger.error(f"Strategist error: {e}")
        return {**state, "narrative_results": {"headline": "MATCHDAY", "subtitle": "READY", "report": "Error generating report.", "instagram_caption": "", "hashtags": []}, "agency_status": "Strategist: Fallback used."}

def art_director_node(state: AgentState) -> AgentState:
    client = _get_client()
    
    # 1. LOAD ELITE PROMPT FROM FILE
    prompt_path = Path("ai_models/prompts/card_designer.txt")
    if prompt_path.exists():
        with open(prompt_path, "r") as f: base_prompt = f.read()
    else:
        base_prompt = "Act as an Elite Art Director for sports designs. Create 3 concepts."

    context_payload = {
        "match": state["match_payload"],
        "player": state["player_profile"],
        "has_photos": state["has_player_photo"],
        "narrative": state.get("narrative_results", {})
    }
    
    formatted_prompt = base_prompt.replace("{context_json}", json.dumps(context_payload))
    formatted_prompt = formatted_prompt.replace("{team_colors}", json.dumps(state["team_colors"]))
    
    contents = [formatted_prompt]
    
    # Visual analysis of the player photo if available
    photos = state.get("context", {}).get("available_photos", [])
    if photos:
        best_photo = photos[0].get("bg_removed") or photos[0].get("original")
        if best_photo and Path(best_photo).exists():
            with open(best_photo, "rb") as f: photo_bytes = f.read()
            contents.append("Player Pose Analysis (integrate player into the composition based on this pose):")
            contents.append(types.Part.from_bytes(data=photo_bytes, mime_type=f"image/{Path(best_photo).suffix[1:].replace('jpg','jpeg')}"))

    try:
        res = client.models.generate_content(model=_ART_DIRECTOR_MODEL, contents=contents, config=types.GenerateContentConfig(response_mime_type="application/json"))
        raw = json.loads(res.text)
        concepts = raw.get("concepts", []) if isinstance(raw, dict) else raw
        if not isinstance(concepts, list): concepts = [concepts]
        _log_agency_step("art_director", "Elite Vision", concepts)
        return {**state, "style_concepts": concepts, "agency_status": "Art Director: 3 elite concepts designed."}
    except Exception as e:
        logger.error(f"Art Director error: {e}")
        return {**state, "style_concepts": [{"archetype": "god_mode", "headline_depth": "behind", "use_stadium": True, "fx_type": "fog", "color_palette": {"base": "#050505", "glow": "#ffffff"}}], "agency_status": "Art Director: Fallback used."}

def layout_designer_node(state: AgentState) -> AgentState:
    concepts = state.get("style_concepts", [])
    narrative = state.get("narrative_results", {"headline": "MATCHDAY"})
    
    final_proposals = []
    templates = ["A", "B", "C"]
    
    for i in range(3):
        concept = _ensure_dict(concepts[i % len(concepts)])
        archetype = concept.get("archetype", "god_mode")
        
        # --- ELITE ARCHETYPE ENGINE ---
        if archetype == "editorial":
            mods = {
                "player_photo": {"x": 75, "y": 95, "scale": 135, "visible": True},
                "headline": {"x": 25, "y": 30, "scale": 150, "visible": True},
                "player_name": {"x": 25, "y": 45, "scale": 95, "visible": True},
                "home_logo": {"x": 10, "y": 85, "scale": 85, "visible": True},
                "away_logo": {"x": 25, "y": 85, "scale": 85, "visible": True},
                "stadium": {"x": 50, "y": 50, "scale": 100, "visible": False}
            }
        elif archetype == "minimalist":
            mods = {
                "player_photo": {"x": 50, "y": 95, "scale": 115, "visible": True},
                "headline": {"x": 50, "y": 50, "scale": 280, "visible": True},
                "player_name": {"x": 50, "y": 15, "scale": 125, "visible": True},
                "home_logo": {"x": 50, "y": 80, "scale": 160, "visible": False},
                "away_logo": {"x": 50, "y": 80, "scale": 160, "visible": False},
                "stadium": {"x": 50, "y": 50, "scale": 100, "visible": False}
            }
        elif archetype == "tactical":
            mods = {
                "player_photo": {"x": 50, "y": 95, "scale": 120, "visible": True},
                "headline": {"x": 50, "y": 20, "scale": 130, "visible": True},
                "home_logo": {"x": 25, "y": 15, "scale": 110, "visible": True},
                "away_logo": {"x": 75, "y": 15, "scale": 110, "visible": True},
                "player_name": {"x": 50, "y": 82, "scale": 105, "visible": True},
                "stadium": {"x": 50, "y": 50, "scale": 100, "visible": True}
            }
        else: # GOD MODE
            mods = {
                "player_photo": {"x": 50, "y": 95, "scale": 145, "visible": True},
                "headline": {"x": 50, "y": 35, "scale": 220, "visible": True},
                "player_name": {"x": 50, "y": 85, "scale": 115, "visible": True},
                "home_logo": {"x": 12, "y": 12, "scale": 100, "visible": True},
                "away_logo": {"x": 88, "y": 12, "scale": 100, "visible": True},
                "stadium": {"x": 50, "y": 50, "scale": 100, "visible": concept.get("use_stadium", True)}
            }

        for k in ["comp_badge", "subtitle", "stream_logo", "match_info"]:
            if k not in mods: mods[k] = {"x": 50, "y": 10, "scale": 60, "visible": True}

        proposal = {
            "template": templates[i],
            "narrative": narrative,
            "nanobana_background_prompt": str(concept.get("nanobana_prompt") or "Cinematic sports background."),
            "layout_modifiers": mods,
            "selected_photo_idx": 0, 
            "fx_type": concept.get("fx_type", "fog"),
            "use_stadium": concept.get("use_stadium", True),
            "headline_depth": concept.get("headline_depth", "behind"),
            "design": {
                "template": templates[i],
                "layers": {
                    "base_color": _process_colors(concept.get("color_palette", {}).get("base")),
                    "glow_color": _process_colors(concept.get("color_palette", {}).get("glow"))
                }
            }
        }
        final_proposals.append(proposal)
        
    return {**state, "proposals": final_proposals, "agency_status": "Layout Designer: Elite coordinates finalized."}

def retrieve_context(state: AgentState) -> AgentState:
    match = state["match_payload"]
    player_id = match.get("player_id", "unknown")
    from utils.image_processing import get_player_album
    return {**state, "context": {"player_id": player_id, "available_photos": get_player_album(player_id)}, "agency_status": "Agency: Match context retrieved."}

def _build_graph():
    builder = StateGraph(AgentState)
    builder.add_node("retrieve_context", retrieve_context)
    builder.add_node("strategist", strategist_node)
    builder.add_node("art_director", art_director_node)
    builder.add_node("layout_designer", layout_designer_node)
    builder.set_entry_point("retrieve_context")
    builder.add_edge("retrieve_context", "strategist")
    builder.add_edge("strategist", "art_director")
    builder.add_edge("art_director", "layout_designer")
    builder.add_edge("layout_designer", END)
    return builder.compile()

_graph = None
def _get_graph():
    global _graph
    if _graph is None: _graph = _build_graph()
    return _graph

def run_card_design_agent(match_payload: dict, player_profile: dict, team_colors: dict, player_history: list, has_player_photo: bool, card_type: str = "post-match", player_preferences: dict | None = None, tone: str = "pro") -> list:
    # FORCE LANGSMITH EUROPE SYNC
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_ENDPOINT"] = "https://eu.api.smith.langchain.com"
    os.environ["LANGCHAIN_API_KEY"] = "os.environ.get("LANGCHAIN_API_KEY", "")"
    os.environ["LANGCHAIN_PROJECT"] = "HKPL-Design-Agency"

    try:
        initial_state: AgentState = {
            "match_payload": match_payload, "player_profile": player_profile, "team_colors": team_colors,
            "player_history": player_history, "has_player_photo": has_player_photo, "card_type": card_type,
            "player_preferences": player_preferences or {}, "tone": tone, "context": {}, 
            "style_concepts": [], "proposals": [], "agency_status": "Agency: Starting session...", "error": None
        }
        graph = _get_graph()
        result = graph.invoke(initial_state)
        return result.get("proposals") or []
    except Exception as exc:
        logger.error(f"run_card_design_agent error: {exc}")
        return []
