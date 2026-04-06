# ABOUTME: Elite Design Agency Agent (LangGraph) — V2 (archetype layouts) + V3 (Master Image pipeline).
# ABOUTME: V3 adds Deconstructor + Surgeon nodes; activated via CARD_AGENCY_V3=true env var.
# ABOUTME: V3 flow: Strategist → Art Director → Nano Banana → Deconstructor → Surgeon → Compositor.

import json
import logging
import os
import re
import base64
import time
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

# --- Model Lists (resolved from ai_config with runtime fallback) ---
from utils.ai_config import AI_DEFAULTS as _AI_DEFAULTS
_PRO_MODELS = [
    _AI_DEFAULTS["orchestrator"]["primary"],   # gemini-3-pro-preview
    _AI_DEFAULTS["orchestrator"]["fallback"],  # gemini-2.5-pro
]
_FLASH_MODELS = [
    _AI_DEFAULTS["worker"]["primary"],         # gemini-3-flash-preview
    _AI_DEFAULTS["worker"]["fallback_1"],      # gemini-2.5-flash
    _AI_DEFAULTS["worker"]["fallback_2"],      # gemini-2.0-flash
]
# Aliases kept for V2 code that uses the bare constant
_STRATEGIST_MODEL = _FLASH_MODELS[0]
_ART_DIRECTOR_MODEL = _PRO_MODELS[0]
_LAYOUT_MODEL = _FLASH_MODELS[0]
_CRITIC_MODEL = _PRO_MODELS[0]


# Session-level quota tracker: model_name → expiry timestamp (float)
_EXHAUSTED_MODELS: dict[str, float] = {}

# Exponential backoff delays between model-switch attempts (seconds)
_SWITCH_BACKOFF = [0, 1, 2]  # no wait on first switch, then 1s, 2s


def _parse_retry_after(exc: Exception) -> float:
    """Extract Retry-After seconds from a Google API 429 exception, if present.
    Falls back to 60 s if the header is missing or unparseable.
    """
    try:
        # google-genai wraps the httpx response; try to find 'retryDelay' in the error detail
        err_str = str(exc)
        import re as _re
        match = _re.search(r"[Rr]etry[_-]?[Aa]fter[\"']?\s*[=:]\s*[\"']?(\d+)", err_str)
        if match:
            return float(match.group(1))
        # Also check for retryDelay in JSON body (Google API format: "retryDelay":"30s")
        match = _re.search(r'"retryDelay"\s*:\s*"(\d+)', err_str)
        if match:
            return float(match.group(1))
    except Exception:
        pass
    return 60.0  # conservative default — 1 minute


def _is_model_exhausted(model_name: str) -> bool:
    expiry = _EXHAUSTED_MODELS.get(model_name)
    if expiry is None:
        return False
    if time.time() < expiry:
        return True
    del _EXHAUSTED_MODELS[model_name]
    return False


def _generate_with_fallback(client, model_list: list, contents, config):
    """Try models in order with exponential backoff and Retry-After awareness.

    - Skips models whose quota window hasn't expired yet.
    - On 429: parses Retry-After header to set a precise expiry, then tries the next model.
    - Raises immediately when all models in the list are exhausted (no reset loop).
    """
    available = [m for m in model_list if not _is_model_exhausted(m)]
    if not available:
        mins_left = max(
            ((exp - time.time()) / 60 for exp in _EXHAUSTED_MODELS.values() if exp > time.time()),
            default=0,
        )
        raise RuntimeError(
            f"All text models exhausted (resets in ~{int(mins_left)}m): {model_list}."
        )

    last_err = None
    for attempt, model_name in enumerate(available):
        # Exponential backoff between model switches (not on the first attempt)
        if attempt > 0:
            wait = _SWITCH_BACKOFF[min(attempt, len(_SWITCH_BACKOFF) - 1)]
            if wait:
                logger.debug(f"Backoff {wait}s before trying {model_name}")
                time.sleep(wait)

        try:
            return client.models.generate_content(model=model_name, contents=contents, config=config)
        except Exception as e:
            err_str = str(e)
            if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str or "spending cap" in err_str.lower():
                retry_after = _parse_retry_after(e)
                _EXHAUSTED_MODELS[model_name] = time.time() + retry_after
                logger.warning(
                    f"Model {model_name} quota exhausted — retry in {int(retry_after)}s."
                )
                last_err = e
                continue
            raise
    raise last_err

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
    # V3 state fields
    master_image_path: Optional[str]
    master_layout: Optional[dict]
    bg_inpainted_path: Optional[str]
    atmosphere_overlays: Optional[List[str]]
    progress: Optional[dict]
    v3_result: Optional[dict]

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
        res = _generate_with_fallback(client, _FLASH_MODELS, prompt, types.GenerateContentConfig(response_mime_type="application/json"))
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
        res = _generate_with_fallback(client, _PRO_MODELS, contents, types.GenerateContentConfig(response_mime_type="application/json"))
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

# ---------------------------------------------------------------------------
# V3 Nodes
# ---------------------------------------------------------------------------

def strategist_v3_node(state: AgentState) -> AgentState:
    """V3 Strategist — same logic as V2 but emits progress event."""
    state = {**state, "progress": {"phase": "Analizando el ADN del partido...", "pct": 0}}
    return strategist_node(state)


def art_director_v3_node(state: AgentState) -> AgentState:
    """V3 Art Director — produces a Master Design Prompt for Nano Banana."""
    state = {**state, "progress": {"phase": "Diseñando la visión artística...", "pct": 20}}
    client = _get_client()

    match = state["match_payload"]
    player = state["player_profile"]
    narrative = state.get("narrative_results", {})
    team_colors = state.get("team_colors", {})

    # Determine archetype from match type
    is_derby = match.get("is_derby", False)
    is_cup = "cup" in str(match.get("competition", "")).lower()
    archetype = "derby" if is_derby else ("cup_final" if is_cup else "league")

    prompt = f"""You are an Elite Art Director for a global sports card agency.
Generate a "Master Design Prompt" for Nano Banana (an AI image generator) to create a COMPLETE football matchday card.

The card MUST contain:
1. A photorealistic sports background scene (stadium, pitch, dramatic lighting)
2. Team colour palette applied: {json.dumps(team_colors)}
3. Atmosphere effects (choose one: volumetric smoke, light particles, lens flares)
4. Two logo placement zones: bottom-left and bottom-right corners (leave space ~15% of card)
5. Text safe area: lower 20% of card for player name, upper 10% for match info
6. A NEUTRAL HUMAN SILHOUETTE placeholder in centre-column (NO face, NO jersey details, neutral stance, inpaintable region)

Match context: {json.dumps({"player": player.get("name",""), "match": match.get("fixture",""), "archetype": archetype})}
Narrative: {narrative.get("report", "")[:200]}

Return JSON:
{{
  "master_design_prompt": "<detailed image generation prompt in English, 100-200 words>",
  "archetype": "{archetype}",
  "atmosphere_type": "<smoke|particles|lens_flares|fog>"
}}
"""
    try:
        res = _generate_with_fallback(
            client, _PRO_MODELS,
            [prompt],
            types.GenerateContentConfig(response_mime_type="application/json"),
        )
        raw = json.loads(res.text)
        master_prompt = raw.get("master_design_prompt", "Cinematic sports card background with neutral player silhouette.")
        _log_agency_step("art_director_v3", "Master Prompt", raw)
        return {**state, "style_concepts": [raw], "agency_status": "Art Director V3: Master Design Prompt ready."}
    except Exception as e:
        logger.error(f"Art Director V3 error: {e}")
        fallback_prompt = "Ultra-cinematic football stadium at night, dramatic rim lighting, volumetric fog, team colours, neutral human silhouette centre-frame, two logo zones bottom corners, text space lower 20%."
        return {**state, "style_concepts": [{"master_design_prompt": fallback_prompt, "archetype": archetype, "atmosphere_type": "fog"}], "agency_status": "Art Director V3: Fallback used."}


def _generate_gradient_fallback(state: AgentState) -> bytes:
    """Generates a team-coloured gradient PNG locally (PIL-only, no API calls)."""
    from PIL import Image, ImageDraw
    from io import BytesIO

    team_colors = state.get("team_colors", {})
    raw_colors = team_colors.get("home") or team_colors.get("primary") or ["#0a0a1a", "#1a1a3e"]
    if isinstance(raw_colors, str):
        raw_colors = [raw_colors, "#0a0a1a"]
    c1_hex = (raw_colors[0] if len(raw_colors) > 0 else "#0a0a1a").lstrip("#")
    c2_hex = (raw_colors[1] if len(raw_colors) > 1 else "#0a0a1a").lstrip("#")

    def hex_to_rgb(h: str):
        try:
            return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        except Exception:
            return 10, 10, 26

    c1, c2 = hex_to_rgb(c1_hex), hex_to_rgb(c2_hex)
    W, H = 1080, 1920
    img = Image.new("RGB", (W, H))
    draw = ImageDraw.Draw(img)
    for y in range(H):
        t = y / H
        r = int(c1[0] * (1 - t) + c2[0] * t)
        g = int(c1[1] * (1 - t) + c2[1] * t)
        b = int(c1[2] * (1 - t) + c2[2] * t)
        draw.line([(0, y), (W, y)], fill=(r, g, b))

    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def nano_banana_node(state: AgentState) -> AgentState:
    """V3 Nano Banana — generates the full Master Image from the Art Director's prompt."""
    state = {**state, "progress": {"phase": "Diseñando la visión artística...", "pct": 30}}

    concept = state.get("style_concepts", [{}])[0] if state.get("style_concepts") else {}
    master_prompt = concept.get("master_design_prompt", "Cinematic football card background with player silhouette.")

    match = state["match_payload"]
    player_id = match.get("player_id", "unknown")
    match_id = str(match.get("fixture_id") or match.get("milestone_id") or "match")

    from utils.nanobana_service import generate_nanobana_background

    try:
        image_bytes = generate_nanobana_background(master_prompt)
    except Exception as e:
        logger.error(f"Nano Banana V3 error: {e}")
        image_bytes = None

    if not image_bytes:
        logger.warning("Nano Banana V3: API unavailable — using local gradient fallback.")
        image_bytes = _generate_gradient_fallback(state)

    from pathlib import Path as _Path
    card_dir = _Path("data/player_cards") / str(player_id) / str(match_id)
    card_dir.mkdir(parents=True, exist_ok=True)
    master_path = card_dir / "master.png"
    with open(master_path, "wb") as f:
        f.write(image_bytes)
    return {**state, "master_image_path": str(master_path), "agency_status": "Nano Banana V3: Master Image ready (gradient fallback)."}


def deconstructor_node(state: AgentState) -> AgentState:
    """V3 Deconstructor — extracts MasterLayout bounding boxes from the Master Image."""
    state = {**state, "progress": {"phase": "Deconstruyendo la obra maestra...", "pct": 40}}

    master_image_path = state.get("master_image_path")
    if not master_image_path:
        return {**state, "agency_status": "Deconstructor: No master image to analyse.", "error": "master_image_path missing"}

    from utils.deconstructor_service import deconstruct_master_image, DeconstructorValidationError
    try:
        master_layout = deconstruct_master_image(master_image_path=master_image_path)
        _log_agency_step("deconstructor", master_image_path, master_layout)
        return {**state, "master_layout": master_layout, "agency_status": "Deconstructor: MasterLayout extracted."}
    except DeconstructorValidationError as e:
        logger.error(f"DeconstructorValidationError: {e}")
        return {**state, "master_layout": None, "phase": "deconstruction_failed", "agency_status": f"Deconstructor: Validation failed — {e}", "error": str(e)}
    except Exception as e:
        logger.error(f"Deconstructor error: {e}")
        return {**state, "master_layout": None, "phase": "deconstruction_failed", "agency_status": f"Deconstructor: Error — {e}", "error": str(e)}


def surgeon_node(state: AgentState) -> AgentState:
    """V3 Surgeon — inpaints the player zone and extracts atmosphere overlays."""
    state = {**state, "progress": {"phase": "Preparando el escenario infinito...", "pct": 60}}

    master_image_path = state.get("master_image_path")
    master_layout = state.get("master_layout")

    if not master_image_path or not master_layout:
        return {**state, "bg_inpainted_path": master_image_path, "atmosphere_overlays": [], "agency_status": "Surgeon: Skipped — missing inputs."}

    from utils.surgeon_service import inpaint_background, extract_atmosphere_overlays

    player_bbox = master_layout.get("player_bbox", {"x": 270, "y": 200, "w": 540, "h": 700})
    atmosphere_regions = master_layout.get("atmosphere_mask_regions", [])

    bg_path = inpaint_background(master_image_path, player_bbox, fallback=True)
    overlay_paths = extract_atmosphere_overlays(master_image_path, atmosphere_regions)

    return {
        **state,
        "bg_inpainted_path": str(bg_path),
        "atmosphere_overlays": [str(p) for p in overlay_paths],
        "agency_status": "Surgeon: Infinite Background and overlays ready.",
    }


def compositor_v3_node(state: AgentState) -> AgentState:
    """V3 Compositor — assembles the final card using compose_from_master."""
    state = {**state, "progress": {"phase": "Fusionando al protagonista...", "pct": 80}}

    context = state.get("context", {})
    photos = context.get("available_photos", [])
    player_photo_path = None
    if photos:
        idx = state.get("selected_photo_idx", 0) or 0
        photo_entry = photos[idx] if idx < len(photos) else photos[0]
        player_photo_path = photo_entry.get("bg_removed") or photo_entry.get("original")

    master_layout = state.get("master_layout") or {}
    bg_inpainted_path = state.get("bg_inpainted_path") or state.get("master_image_path", "")
    atmosphere_overlays = state.get("atmosphere_overlays") or []

    match = state["match_payload"]
    player_id = match.get("player_id", "unknown")
    match_id = str(match.get("fixture_id") or match.get("milestone_id") or "match")
    narrative = state.get("narrative_results", {})
    player_name = state.get("player_profile", {}).get("name", "PLAYER")

    ui_brief = {
        "player_name": player_name,
        "match_payload": match,
        "narrative": narrative,
    }

    from pathlib import Path as _Path
    output_dir = str(_Path("data/player_cards") / str(player_id) / str(match_id))

    from utils.card_renderer import compose_from_master
    try:
        card_path = compose_from_master(
            master_layout=master_layout,
            bg_inpainted_path=bg_inpainted_path,
            player_photo_path=player_photo_path or "",
            atmosphere_overlays=atmosphere_overlays,
            ui_brief=ui_brief,
            output_dir=output_dir,
            format="9:16",
        )
        v3_result = {
            "card_v3_path": str(card_path),
            "master_layout": master_layout,
            "narrative": narrative,
            "template": "V3",
            "layout_modifiers": {},
            "design": {"template": "V3"},
            "nanobana_background_path": bg_inpainted_path,
        }
        return {**state, "v3_result": v3_result, "agency_status": "Compositor V3: Card rendered.", "progress": {"phase": "Fusionando al protagonista...", "pct": 100}}
    except Exception as e:
        logger.error(f"Compositor V3 error: {e}")
        return {**state, "v3_result": None, "agency_status": f"Compositor V3: Error — {e}", "error": str(e)}


# ---------------------------------------------------------------------------
# Graph Builders
# ---------------------------------------------------------------------------

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


def _build_graph_v3():
    builder = StateGraph(AgentState)
    builder.add_node("retrieve_context", retrieve_context)
    builder.add_node("strategist", strategist_v3_node)
    builder.add_node("art_director", art_director_v3_node)
    builder.add_node("nano_banana", nano_banana_node)
    builder.add_node("deconstructor", deconstructor_node)
    builder.add_node("surgeon", surgeon_node)
    builder.add_node("compositor", compositor_v3_node)
    builder.set_entry_point("retrieve_context")
    builder.add_edge("retrieve_context", "strategist")
    builder.add_edge("strategist", "art_director")
    builder.add_edge("art_director", "nano_banana")
    builder.add_edge("nano_banana", "deconstructor")
    builder.add_edge("deconstructor", "surgeon")
    builder.add_edge("surgeon", "compositor")
    builder.add_edge("compositor", END)
    return builder.compile()


_graph_v2 = None
_graph_v3 = None

def _get_graph():
    global _graph_v2, _graph_v3
    if os.getenv("CARD_AGENCY_V3") == "true":
        if _graph_v3 is None:
            _graph_v3 = _build_graph_v3()
        return _graph_v3
    else:
        if _graph_v2 is None:
            _graph_v2 = _build_graph()
        return _graph_v2

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
            "style_concepts": [], "proposals": [], "agency_status": "Agency: Starting session...", "error": None,
            # V3 fields (None for V2 runs)
            "master_image_path": None, "master_layout": None, "bg_inpainted_path": None,
            "atmosphere_overlays": None, "progress": None, "v3_result": None,
        }
        graph = _get_graph()
        result = graph.invoke(initial_state)
        if os.getenv("CARD_AGENCY_V3") == "true":
            v3_result = result.get("v3_result")
            return [v3_result] if v3_result else []
        return result.get("proposals") or []
    except Exception as exc:
        logger.error(f"run_card_design_agent error: {exc}")
        return []
