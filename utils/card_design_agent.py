# ABOUTME: Elite One-Shot Design Agency Agent — V5 with editorial selection for post-match cards.
# ABOUTME: Flow: Match Intelligence → Performance Editor → Art Director → Design Studio → Validator.
# ABOUTME: Nano Banana generates 100% of the card (integrated subject, badges, and text).

import io
import json
import logging
import os
import time
import random
from pathlib import Path
from datetime import datetime
from typing import TypedDict, List, Optional, Dict, Any, Callable

# Third-party
from langgraph.graph import StateGraph, END
from google.genai import types
from PIL import Image as PILImage

# Project
from data.team_branding_registry import canonicalize_team_name, get_team_colors
from data.competition_registry import get_competition_display_name
from utils.image_processing import get_player_album, get_team_assets
from utils.runtime_storage import ensure_player_cards_dir

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
    editorial_decision: Dict[str, Any]
    design_strategy: Dict[str, Any]
    forced_stats: Optional[List[Dict[str, Any]]] # Added for manual selection
    exclude_trends: List[str] # Trends to skip in randomness
    
    # Artifacts
    player_photo_path: Optional[str]
    generated_card_path: Optional[str]
    caption: Optional[str]
    agency_status: str
    progress: Dict[str, Any]
    on_progress: Optional[Callable[[Dict[str, Any]], None]]
    error: Optional[str]


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _format_stat_value(value: Any, kind: str = "number") -> str:
    if value is None or value == "":
        return "0"
    if kind == "percent":
        return f"{_safe_float(value):.0f}%"
    if kind == "minutes":
        return f"{_safe_int(value)}'"
    if isinstance(value, float):
        if abs(value - round(value)) < 0.05:
            return str(int(round(value)))
        return f"{value:.1f}"
    return str(value)


def _normalize_selected_stats(raw_stats: Any) -> List[Dict[str, Any]]:
    if not isinstance(raw_stats, list):
        return []
    normalized: List[Dict[str, Any]] = []
    for idx, item in enumerate(raw_stats, start=1):
        if not isinstance(item, dict):
            continue
        label = str(item.get("label") or "").strip()
        value = str(item.get("value") or "").strip()
        if not label or not value:
            continue
        normalized.append({
            "label": label,
            "value": value,
            "priority": _safe_int(item.get("priority"), idx),
        })
    return normalized[:5]


def _build_editorial_decision(
    headline: str,
    subheadline: str,
    story_angle: str,
    selected_stats: List[Dict[str, Any]],
    supporting_visual: Dict[str, Any],
    confidence: float = 0.7,
) -> Dict[str, Any]:
    return {
        "story_angle": story_angle,
        "headline": str(headline or "").strip(),
        "subheadline": str(subheadline or "").strip(),
        "selected_stats": _normalize_selected_stats(selected_stats),
        "supporting_visual": {
            "type": str((supporting_visual or {}).get("type") or "none"),
            "reason": str((supporting_visual or {}).get("reason") or "").strip(),
        },
        "confidence": max(0.0, min(1.0, _safe_float(confidence, 0.7))),
    }


def _default_editorial_decision(match_payload: Dict[str, Any], player_profile: Dict[str, Any]) -> Dict[str, Any]:
    player_name = str((player_profile or {}).get("name") or "Player")
    stats = [
        {"label": "Minutes", "value": _format_stat_value(match_payload.get("minutes_played"), "minutes"), "priority": 1},
        {"label": "Rating", "value": _format_stat_value(match_payload.get("rating", "—")), "priority": 2},
        {"label": "Goals", "value": _format_stat_value(match_payload.get("goals", 0)), "priority": 3},
        {"label": "Assists", "value": _format_stat_value(match_payload.get("assists", 0)), "priority": 4},
    ]
    return _build_editorial_decision(
        headline=f"{player_name} performance",
        subheadline=str(match_payload.get("score") or "").strip(),
        story_angle="consistent_performer",
        selected_stats=stats,
        supporting_visual={"type": "none", "reason": "Fallback summary without additional visual."},
        confidence=0.45,
    )


def _normalize_editorial_decision(decision: Any, match_payload: Optional[Dict[str, Any]] = None, player_profile: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    if not isinstance(decision, dict):
        return _default_editorial_decision(match_payload or {}, player_profile or {})
    normalized = _build_editorial_decision(
        headline=str(decision.get("headline") or ""),
        subheadline=str(decision.get("subheadline") or ""),
        story_angle=str(decision.get("story_angle") or "consistent_performer"),
        selected_stats=decision.get("selected_stats") or [],
        supporting_visual=decision.get("supporting_visual") or {},
        confidence=_safe_float(decision.get("confidence"), 0.7),
    )
    if not normalized["headline"]:
        fallback = _default_editorial_decision(match_payload or {}, player_profile or {})
        normalized["headline"] = fallback["headline"]
    return normalized


def _build_editorial_brief(editorial_decision: Dict[str, Any]) -> str:
    stats_text = ", ".join(
        f"{item['label']}: {item['value']}" for item in editorial_decision.get("selected_stats", [])
    ) or "No supporting stats selected."
    visual = editorial_decision.get("supporting_visual") or {}
    visual_type = str(visual.get("type") or "none")
    visual_reason = str(visual.get("reason") or "No supporting visual.")
    return (
        "EDITORIAL BRIEF:\n"
        f"- STORY ANGLE: {editorial_decision.get('story_angle', 'consistent_performer')}\n"
        f"- HEADLINE: {editorial_decision.get('headline', '')}\n"
        f"- SUBHEADLINE: {editorial_decision.get('subheadline', '')}\n"
        f"- PRIORITY STATS: {stats_text}\n"
        f"- SUPPORTING VISUAL: {visual_type} ({visual_reason})\n"
    )

# --- Node 1: Match Intelligence Collector ---
def match_intelligence_node(state: AgentState) -> AgentState:
    """Gathers all game/player context (teams, venue, time, colors, and post-game stats)."""
    p = {
        "phase": "ANALYZING MATCH INTELLIGENCE...",
        "pct": 10,
        "icon": "bi bi-radar",
        "bg": "linear-gradient(135deg, rgba(10, 10, 15, 0.95) 0%, rgba(0, 100, 255, 0.3) 100%)"
    }
    state["progress"] = p
    if state.get("on_progress"):
        state["on_progress"](p)
    
    # Delay to allow user to read the phase
    time.sleep(5)

    match = state["match_payload"]
    # 1. Determine if it's pre or post game
    # Prefer explicit card_type from the editor; fall back to heuristic (minutes_played present)
    card_type = match.get("card_type", "pre-match")
    is_post = (card_type == "post-match") or (match.get("minutes_played") is not None)
    
    # 2. Extract Date (try multiple sources)
    date_str = match.get("kickoff_display") or match.get("date_utc") or match.get("date") or "MATCHDAY"
    if isinstance(date_str, str) and "T" in date_str and "202" in date_str: # ISO format cleanup
        try:
            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            date_str = dt.strftime("%d %b %Y")
        except: pass

    home_raw = match.get("home_team", "Home Team")
    away_raw = match.get("away_team", "Away Team")
    
    home_norm = canonicalize_team_name(home_raw)
    away_norm = canonicalize_team_name(away_raw)
    normalized_score = match.get("score")
    basic_info = (match.get("player_stats") or {}).get("basic_info") or {}
    match_stats = match.get("match_stats") or {}
    heatmap = match.get("heatmap") or []
    recent_ratings = match.get("recent_ratings") or []
    status = match.get("status")
    
    intel = {
        "is_post_game": is_post,
        "home": {"name": home_raw, "colors": get_team_colors(home_norm)},
        "away": {"name": away_raw, "colors": get_team_colors(away_norm)},
        "venue": match.get("venue") or match.get("stadium") or "Stadium",
        "date": date_str,
        "competition": get_competition_display_name(match.get("competition", "HK Premier League")),
        "result": match.get("result"),
        "status": status,
        "position": match.get("position") or basic_info.get("position_primary") or state.get("player_profile", {}).get("position"),
        "intelligence_meta": match.get("intelligence_meta") or {},
        "player_stats": match.get("player_stats") or {},
    }
    
    # 4. Add Performance Stats for Post-Game
    if is_post:
        intel["stats"] = {
            "score": normalized_score,
            "rating": match.get("rating", 0.0),
            "goals": match.get("goals", 0),
            "assists": match.get("assists", 0),
            "minutes": match.get("minutes_played", 0),
            "started": match.get("started"),
            "yellow_cards": match.get("yellow_cards", 0),
            "red_cards": match.get("red_cards", 0),
            "match_stats": match_stats,
            "heatmap": heatmap,
            "recent_ratings": recent_ratings,
        }
        
    return {**state, "match_intelligence": intel, "is_post_game": is_post}


def performance_editor_node(state: AgentState) -> AgentState:
    """Selects the promotional angle, the 4-5 key stats, and the optional supporting visual."""
    p = {
        "phase": "CRAFTING MATCH NARRATIVE...",
        "pct": 22,
        "icon": "bi bi-vector-pen",
        "bg": "linear-gradient(135deg, rgba(10, 10, 15, 0.95) 0%, rgba(200, 0, 255, 0.3) 100%)"
    }
    state["progress"] = p
    if state.get("on_progress"):
        state["on_progress"](p)
    
    # Delay to allow user to read the phase
    time.sleep(5)

    intel = state.get("match_intelligence") or {}

    if not state.get("is_post_game"):
        decision = _build_editorial_decision(
            headline="MATCHDAY",
            subheadline=str(intel.get("competition") or "").strip(),
            story_angle="consistent_performer",
            selected_stats=[],
            supporting_visual={"type": "none", "reason": "Pre-match cards do not use performance visuals."},
            confidence=0.9,
        )
        return {**state, "editorial_decision": decision}

    stats = intel.get("stats") or {}
    minutes = _safe_int(stats.get("minutes"))

    # Post-match: player did not participate — result is the protagonist
    if not minutes:
        result_score = str(stats.get("score") or intel.get("result") or "").strip()
        decision = _build_editorial_decision(
            headline=result_score or "FULL TIME",
            subheadline=str(intel.get("competition") or "").strip(),
            story_angle="match_result",
            selected_stats=[],
            supporting_visual={"type": "none", "reason": "Player did not participate in this match."},
            confidence=0.85,
        )
        return {**state, "editorial_decision": decision}

    # Post-match: user manually selected stats (2nd design attempt override)
    forced = state.get("forced_stats")
    if forced and len(forced) >= 4:
        result_score = str(stats.get("score") or intel.get("result") or "").strip()
        decision = _build_editorial_decision(
            headline=result_score or "FULL TIME",
            subheadline=str(intel.get("competition") or "").strip(),
            story_angle="user_selected",
            selected_stats=forced,
            supporting_visual={"type": "none", "reason": "User-selected stats override."},
            confidence=1.0,
        )
        return {**state, "editorial_decision": decision}

    match_stats = stats.get("match_stats") or {}
    player_name = str((state.get("player_profile") or {}).get("name") or "Player")

    goals = _safe_int(stats.get("goals"))
    assists = _safe_int(stats.get("assists"))
    rating = _safe_float(stats.get("rating"))
    saves = _safe_int(match_stats.get("saves"))
    pass_pct = 0.0
    total_pass = _safe_float(match_stats.get("totalPass"))
    accurate_passes = _safe_float(match_stats.get("accuratePasses"))
    if total_pass > 0:
        pass_pct = (accurate_passes / total_pass) * 100.0
    duel_total = _safe_float(match_stats.get("duelTotal"))
    duel_won = _safe_float(match_stats.get("duelWon"))
    duel_pct = (duel_won / duel_total) * 100.0 if duel_total > 0 else 0.0
    dribbles_total = _safe_float(match_stats.get("totalDribbles"))
    dribbles_success = _safe_float(match_stats.get("successfulDribbles"))
    tackles = _safe_int(match_stats.get("tackles"))
    interceptions = _safe_int(match_stats.get("interceptions"))
    recent_ratings = stats.get("recent_ratings") or []
    score = str(stats.get("score") or "").strip()
    position = str(intel.get("position") or "").lower()

    if saves >= 5:
        story_angle = "goalkeeper_hero"
        headline = "Shot-stopping performance"
    elif goals + assists >= 2 or goals >= 2:
        story_angle = "match_winner"
        headline = "Decisive in the final third"
    elif assists >= 1 or _safe_int(match_stats.get("keyPasses")) >= 3:
        story_angle = "creative_engine"
        headline = "Creative engine on the day"
    elif tackles + interceptions >= 5 or duel_pct >= 65:
        story_angle = "defensive_wall"
        headline = "Defensive control all match"
    elif pass_pct >= 88 and minutes >= 75:
        story_angle = "midfield_control"
        headline = "Controlled the rhythm"
    else:
        story_angle = "consistent_performer"
        headline = "Strong all-round performance"

    subheadline_parts = []
    if score:
        subheadline_parts.append(score)
    result = str(intel.get("result") or "").strip()
    if result:
        subheadline_parts.append(result)
    if minutes:
        subheadline_parts.append(f"{minutes}'")
    subheadline = " · ".join(subheadline_parts[:3])

    candidates: List[Dict[str, Any]] = []
    def add_stat(label: str, value: str, score_weight: float):
        if value in {"0", "0%", "0.0", "0.0%", "—", ""}:
            return
        candidates.append({"label": label, "value": value, "score": score_weight})

    add_stat("Goals", _format_stat_value(goals), 120 + goals * 10)
    add_stat("Assists", _format_stat_value(assists), 110 + assists * 8)
    add_stat("Rating", _format_stat_value(rating), 95 + rating)
    add_stat("Minutes", _format_stat_value(minutes, "minutes"), 70 + min(minutes, 90) / 2)
    add_stat("Pass %", _format_stat_value(pass_pct, "percent"), 84 if pass_pct >= 70 else 0)
    add_stat("Duels Won %", _format_stat_value(duel_pct, "percent"), 82 if duel_pct >= 55 else 0)
    add_stat("Dribbles", _format_stat_value(dribbles_success), 78 if dribbles_success >= 2 else 0)
    add_stat("Tackles", _format_stat_value(tackles), 77 if tackles >= 2 else 0)
    add_stat("Interceptions", _format_stat_value(interceptions), 76 if interceptions >= 2 else 0)
    add_stat("Saves", _format_stat_value(saves), 105 if saves >= 3 else 0)
    add_stat("Yellow Cards", _format_stat_value(stats.get("yellow_cards")), 10)
    add_stat("Red Cards", _format_stat_value(stats.get("red_cards")), 1)

    candidates.sort(key=lambda item: item["score"], reverse=True)
    selected_stats: List[Dict[str, Any]] = []
    seen_labels = set()
    for idx, item in enumerate(candidates, start=1):
        if item["label"] in seen_labels or item["score"] <= 0:
            continue
        selected_stats.append({
            "label": item["label"],
            "value": item["value"],
            "priority": idx,
        })
        seen_labels.add(item["label"])
        if len(selected_stats) >= 5:
            break
    if len(selected_stats) < 4:
        for label, value in [("Minutes", _format_stat_value(minutes, "minutes")), ("Rating", _format_stat_value(rating))]:
            if label not in seen_labels:
                selected_stats.append({"label": label, "value": value, "priority": len(selected_stats) + 1})
                seen_labels.add(label)
            if len(selected_stats) >= 4:
                break

    visual_type = "none"
    visual_reason = "The layout should stay focused on the headline and selected stats."
    heatmap = stats.get("heatmap") or []
    if heatmap and story_angle in {"creative_engine", "midfield_control", "consistent_performer"}:
        visual_type = "heatmap"
        visual_reason = "Heatmap reinforces territorial dominance and activity zones."
    elif match_stats and story_angle in {"defensive_wall", "goalkeeper_hero", "consistent_performer"}:
        visual_type = "radar"
        visual_reason = "A compact radar can summarize the all-round contribution."
    elif len(recent_ratings) >= 3 and story_angle == "consistent_performer":
        visual_type = "sparkline"
        visual_reason = "Recent ratings support the consistency angle."

    if "goalkeeper" in position and visual_type == "heatmap":
        visual_type = "radar"
        visual_reason = "Goalkeeper cards read better with a compact performance summary."

    decision = _build_editorial_decision(
        headline=headline,
        subheadline=subheadline,
        story_angle=story_angle,
        selected_stats=selected_stats,
        supporting_visual={"type": visual_type, "reason": visual_reason},
        confidence=0.82 if selected_stats else 0.55,
    )
    if story_angle == "match_winner" and goals:
        decision["headline"] = "Match-winning impact" if goals >= 2 else "Decisive attacking display"
    if story_angle == "goalkeeper_hero":
        decision["headline"] = "Big saves, big presence"
    if decision["headline"].lower().startswith(player_name.lower()):
        decision["headline"] = decision["headline"].replace(player_name, "").strip() or decision["headline"]
    return {**state, "editorial_decision": decision}

# --- Node 2: Art Director Strategist ---
def art_director_node(state: AgentState) -> AgentState:
    """Selects Trend, Archetype and builds the Master Prompt for Nano Banana."""
    p = {
        "phase": "DEFINING VISUAL STRATEGY...",
        "pct": 30,
        "icon": "bi bi-palette",
        "bg": "linear-gradient(135deg, rgba(10, 10, 15, 0.95) 0%, rgba(0, 255, 128, 0.3) 100%)"
    }
    state["progress"] = p
    if state.get("on_progress"):
        state["on_progress"](p)

    intel = state["match_intelligence"]
    is_post = state["is_post_game"]
    fmt = state.get("format", "9:16")
    editorial_decision = _normalize_editorial_decision(
        state.get("editorial_decision"),
        state.get("match_payload"),
        state.get("player_profile"),
    )
    
    # 1. Select Trend
    trend_dir = Path("assets/design_trends")
    available_trends = list(trend_dir.glob("*.json"))
    
    exclude = state.get("exclude_trends") or []
    # Filter out excluded trends by filename stem
    filtered_trends = [t for t in available_trends if t.stem not in exclude]
    # If we excluded everything, fall back to all available to avoid crash
    if not filtered_trends:
        filtered_trends = available_trends

    # Competition-based priority
    if intel["competition"] in ["AFC", "Cup"]:
        trend_path = trend_dir / "minimal_luxury.json"
        # If minimal_luxury was excluded but we forced it, it's okay for high-tier comps,
        # but we could also try to find an alternative filtered if it was excluded.
    else:
        trend_path = random.choice(filtered_trends) if filtered_trends else trend_dir / "urban_gritty.json"
    
    try:
        with open(trend_path, "r") as f:
            trend = json.load(f)
    except:
        trend = {"name": "Elite Sports"}

    # 2. Extract specific visual identity rules
    vi = trend.get("visual_identity", {})
    typo = vi.get("typography", {})
    colors = vi.get("color_palette", {})
    elements = vi.get("elements", {})
    
    # 3. Select Archetype
    archetype = "Archetype B: Editorial Split" if is_post else "Archetype A: God Mode (Centered Action)"
    
    # 4. Build Structured Prompt (Inverse Deconstruction Strategy)
    # Determine post-match score for mandatory data
    _post_score = ""
    if is_post:
        _s = intel.get("stats") or {}
        _post_score = str(_s.get("score") or intel.get("result") or "").strip()

    prompt = f"""
    Create a professional matchday graphic for Instagram ({fmt} format).
    STYLE TARGET: {trend['name']}

    CRITICAL STYLE DECONSTRUCTION:
    - BACKGROUND SOURCE: You have been provided a VISUAL STYLE REFERENCE IMAGE. REPLICATE its background style, textures, and atmosphere exactly. DO NOT invent your own background (no galaxies, no abstract gradients, no space imagery). Stay faithful to the reference.
    - THEMATIC GUIDE (JSON): Use the provided visual identity rules for colors, textures, and typography style.
    - STRUCTURAL GUIDE (REFERENCE IMAGE): Use the provided VISUAL STYLE REFERENCE IMAGE strictly as a blueprint for composition, element scaling, and spatial hierarchy.
    - ATMOSPHERE: {elements.get('background', 'Professional sports stadium.')}. Focus on high-end realism.
    - TYPOGRAPHY: Use {typo.get('primary', 'Impact')}-style fonts.
    - COLOR RULES: Base is {colors.get('base', 'Dark')}. Internal palette HEX CODES: {', '.join(colors.get('accents', []))}. Use for lighting and highlights ONLY. DO NOT render hex strings as visible text.
    """

    prompt += f"""
    MANDATORY DATA TO RENDER:
    - TEAM A: {intel['home']['name']} (Home)
    - TEAM B: {intel['away']['name']} (Away)
    - DATE: {intel['date']}
    - VENUE: {intel['venue']}
    {f"- MATCH RESULT: {_post_score}" if _post_score else ""}

    HIERARCHY & SCALE RULES (CRITICAL):
    1. ANALYZE the VISUAL STYLE REFERENCE IMAGE for the correct layout, element sizes, and visual hierarchy.
    2. PLAYER PHOTO: Primary focus. Scale and weight as seen in the reference.
    3. SECONDARY ELEMENTS: Date, Venue, and Team Badges must be small, tasteful metadata — proportioned as in the reference.
    4. NO BRACKETS/PARENTHESES around team roles. Use clean bold typography only.
    5. NO DATA LEAK: Never render internal labels like "(Role: Home Team)" literally.
    """

    if is_post:
        s = intel.get('stats') or {}
        story_angle = editorial_decision.get("story_angle", "")
        if story_angle == "match_result":
            # Player did not participate — result is the sole protagonist
            prompt += f"\nCARD TYPE: POST-MATCH RESULT CARD. Focus on the team result, not individual stats."
            if _post_score:
                prompt += f"\nSCORE (DOMINANT ELEMENT): Display '{_post_score}' as the largest, most prominent text on the card."
            prompt += "\nPLAYER CONTEXT: Player was not in the squad for this match."
        else:
            prompt += f"\nCARD TYPE: POST-MATCH PERFORMANCE CARD."
            if _post_score:
                prompt += f"\nFINAL SCORE: {_post_score} — render this prominently below the headline."
            if s.get("started") is True:
                prompt += "\nPLAYER STARTED the match."
            elif s.get("started") is False:
                prompt += "\nPLAYER CAME ON AS SUBSTITUTE."
            prompt += "\n" + _build_editorial_brief(editorial_decision)
            prompt += (
                "\nSTATS PANEL RULES (MANDATORY):"
                "\n- Render ONLY the stats listed in PRIORITY STATS above."
                "\n- Each stat MUST show its LABEL and VALUE together (e.g. 'Goals  1', 'Rating  7.5', 'Minutes  80'')."
                "\n- DO NOT show numbers without labels. DO NOT invent stats not listed above."
                "\n- Keep the stats panel secondary to the player photo and headline."
                "\n- If supporting visual is 'none', do not add charts or graphs."
            )
    else:
        prompt += "\nCARD TYPE: PRE-MATCH. Hero text: 'MATCHDAY'."

    prompt += f"""
    ULTRA-STRICT FIDELITY RULES:
    1. PLAYER PHOTO: The provided image is a clean cutout. PRESERVE the player's face, body, and colors exactly. DO NOT regenerate or distort him.
    2. TEAM BADGES: USE THE EXACT images provided as HOME TEAM BADGE and AWAY TEAM BADGE. Do not replace with generic logos.
    3. BACKGROUND: Follow the VISUAL STYLE REFERENCE IMAGE. No space imagery, no galaxies, no abstract sci-fi effects.
    4. REALISM: Elite professional football marketing aesthetic only.
    """

    # Generate Social Media Caption
    from ai_models.agent_tools import generate_caption
    player_name = str((state.get("player_profile") or {}).get("name") or "Player")
    brief = _build_editorial_brief(editorial_decision)
    caption = generate_caption.invoke({"player_name": player_name, "context": brief})

    return {
        **state,
        "caption": caption,
        "editorial_decision": editorial_decision,
        "design_strategy": {
            "prompt": prompt,
            "trend": trend["name"],
            "trend_id": trend_path.stem,
            "archetype": archetype,
            "editorial_brief": editorial_decision,
        },
    }

# --- Node 3: Design Studio (Nano Banana One-Shot) ---
def design_studio_node(state: AgentState) -> AgentState:
    """The core engine. Sends all visual materials to Gemini for a 100% integrated result."""
    p = {
        "phase": "DESIGNERS ARE RENDERING YOUR MASTERPIECE...",
        "pct": 60,
        "icon": "bi bi-stars",
        "bg": "linear-gradient(135deg, rgba(10, 10, 15, 0.95) 0%, rgba(255, 150, 0, 0.3) 100%)"
    }
    state["progress"] = p
    if state.get("on_progress"):
        state["on_progress"](p)

    t0 = time.time()
    match = state["match_payload"]
    player_id = match.get("player_id", "unknown")
    match_id = str(match.get("fixture_id") or match.get("milestone_id") or "match")
    trend_id = state.get("design_strategy", {}).get("trend_id", "unknown")
    
    # 1. Prepare Vision Parts with Explicit Labeling (Deconstruction)
    parts = []
    
    # A. Player Photo (CUTOUT)
    photos = get_player_album(player_id)
    selected_idx = match.get("selected_photo_idx")
    if photos:
        entry = next((p for p in photos if p["idx"] == selected_idx), photos[0])
        photo_path = entry.get("bg_removed") or entry.get("original")
        if photo_path and os.path.exists(photo_path):
            mime = "image/png" if ".png" in str(photo_path).lower() else "image/jpeg"
            parts.append("--- SOURCE PLAYER PHOTO (PRE-CUTOUT) ---")
            with open(photo_path, "rb") as f:
                parts.append(types.Part.from_bytes(data=f.read(), mime_type=mime))
    
    # B. Team Badges
    for team_key, label in [("home_team", "HOME TEAM BADGE"), ("away_team", "AWAY TEAM BADGE")]:
        team_name = match.get(team_key)
        assets = get_team_assets(team_name)
        logo_path = assets.get("logo_png")
        
        if logo_path and os.path.exists(logo_path):
            parts.append(f"--- {label}: {team_name} ---")
            with open(logo_path, "rb") as f:
                parts.append(types.Part.from_bytes(data=f.read(), mime_type="image/png"))
    
    # C. Design Reference (Try to find a matching reference image for the trend)
    ref_dir = Path("assets/design_references")
    # Priority: image matching the trend stem (e.g. urban_gritty.jpg)
    trend_ref = next(ref_dir.glob(f"{trend_id}.*"), None)
    
    if trend_ref:
        chosen_ref = trend_ref
    else:
        # Fallback to general references if no specific match
        refs = list(ref_dir.glob("*.jpg")) + list(ref_dir.glob("*.jpeg")) + list(ref_dir.glob("*.webp"))
        chosen_ref = random.choice(refs) if refs else None
        
    if chosen_ref:
        parts.append("--- VISUAL STYLE REFERENCE IMAGE (BLUEPRINT FOR COMPOSITION) ---")
        mime = "image/jpeg" if ".jp" in str(chosen_ref).lower() else "image/png"
        if ".webp" in str(chosen_ref).lower(): mime = "image/webp"
        with open(chosen_ref, "rb") as f:
            parts.append(types.Part.from_bytes(data=f.read(), mime_type=mime))

    # D. Instructions
    parts.append("--- FINAL DESIGN INSTRUCTIONS ---")
    parts.append(state["design_strategy"]["prompt"])

    # 2. Call Nano Banana
    try:
        from utils.nanobana_service import generate_nanobana_image
        image_bytes = generate_nanobana_image(parts)
        
        if not image_bytes:
            return {**state, "error": "Nano Banana returned no image data (likely quota exhausted).", "agency_status": "Failed: Quota exhausted."}

        output_dir = ensure_player_cards_dir(str(player_id), str(match_id))
        designs_dir = output_dir / "designs"
        designs_dir.mkdir(parents=True, exist_ok=True)
        final_path = designs_dir / f"card_{int(time.time())}.jpg"
        
        img = PILImage.open(io.BytesIO(image_bytes))
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        img.save(final_path, "JPEG", quality=95)
            
        return {**state, "generated_card_path": str(final_path), "agency_status": "Success: Integrated card generated."}
    except Exception as e:
        logger.error(f"Nano Banana failed: {e}")
        return {**state, "error": str(e), "agency_status": "Failed: Nano Banana error."}

# --- Node 4: Validator & Fallback ---
def validator_node(state: AgentState) -> AgentState:
    """Saves the result and executes Pillow fallback if IA failed."""
    if state.get("generated_card_path") and not state.get("error"):
        p = {
            "phase": "ELITE DESIGN COMPLETED!",
            "pct": 100,
            "icon": "bi bi-check-circle-fill",
            "bg": "linear-gradient(135deg, rgba(10, 10, 15, 0.95) 0%, rgba(0, 255, 0, 0.3) 100%)"
        }
        state["progress"] = p
        if state.get("on_progress"):
            state["on_progress"](p)
        
        # Delay to allow user to see the success state
        time.sleep(5)
        return state

    # --- FALLBACK: Use Pillow Compositor ---
    p = {
        "phase": "AI FAILED. GENERATING EMERGENCY FALLBACK...",
        "pct": 80,
        "icon": "bi bi-exclamation-triangle-fill",
        "bg": "linear-gradient(135deg, rgba(10, 10, 15, 0.95) 0%, rgba(255, 0, 0, 0.4) 100%)"
    }
    state["progress"] = p
    if state.get("on_progress"):
        state["on_progress"](p)
    try:
        from utils.card_compositor import compose_precision_card
        match = state["match_payload"]
        player_id = match.get("player_id", "unknown")
        match_id = str(match.get("fixture_id") or match.get("milestone_id") or "match")
        output_dir = str(ensure_player_cards_dir(str(player_id), str(match_id)))
        
        card_path = compose_precision_card(
            background_image_path=None,
            player_photo_path=state.get("player_photo_path"),
            match_payload=match,
            player_name=state.get("player_profile", {}).get("name", "PLAYER"),
            output_dir=output_dir,
            card_format=state.get("format", "9:16"),
            narrative=state.get("editorial_decision"),
        )
        return {**state, "generated_card_path": str(card_path), "agency_status": "Fallback: Pillow card generated."}
    except Exception as e:
        return {**state, "error": f"Total failure: {e}", "agency_status": "Critical: Fallback failed."}

# --- Graph Construction ---
def run_card_design_agent(match_payload: Dict, player_profile: Dict, card_format: str = "9:16",
                          forced_stats: Optional[List[Dict]] = None, 
                          exclude_trends: Optional[List[str]] = None,
                          on_progress: Optional[Callable] = None) -> Dict:
    """Entry point for the One-Shot Agency."""
    builder = StateGraph(AgentState)

    builder.add_node("intelligence", match_intelligence_node)
    builder.add_node("editorial", performance_editor_node)
    builder.add_node("strategy", art_director_node)
    builder.add_node("studio", design_studio_node)
    builder.add_node("validator", validator_node)

    builder.set_entry_point("intelligence")
    builder.add_edge("intelligence", "editorial")
    builder.add_edge("editorial", "strategy")
    builder.add_edge("strategy", "studio")
    builder.add_edge("studio", "validator")
    builder.add_edge("validator", END)

    graph = builder.compile()

    initial_state = {
        "match_payload": match_payload,
        "player_profile": player_profile,
        "is_post_game": False,
        "format": card_format,
        "forced_stats": forced_stats,
        "exclude_trends": exclude_trends or [],
        "editorial_decision": _default_editorial_decision(match_payload, player_profile),
        "generated_card_path": None,
        "caption": None,
        "agency_status": "Starting...",
        "progress": {
            "phase": "INITIALIZING ELITE AGENCY...",
            "pct": 0,
            "icon": "bi bi-cpu",
            "bg": "rgba(10, 10, 15, 0.95)"
        },
        "on_progress": on_progress,
        "error": None
    }
    
    final_state = graph.invoke(initial_state)
    return final_state
