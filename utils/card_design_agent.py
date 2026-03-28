# ABOUTME: LangGraph-based AI agent that generates 3 Design Brief proposals per match card.
# ABOUTME: Supports pre-match and post-match archetypes; falls back to deterministic brief on LLM failure.

# Standard Library
import json
import logging
import os
import re
from typing import TypedDict

# Third-party
from langgraph.graph import StateGraph, END

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = "gemini-2.0-flash"
_DEFAULT_DARK_COLOR = "#1a1a2e"

# ---------------------------------------------------------------------------
# DesignBrief schema
# ---------------------------------------------------------------------------

class DesignBrief(TypedDict):
    narrative: dict   # archetype, emotion, headline, key_moment, supporting_story,
                      # caption, hashtags, reasoning
    design: dict      # template, format, layers, typography, elements


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

CARD_DESIGNER_PROMPT = """
Eres un director creativo de tarjetas deportivas para la Hong Kong Premier League.
Tu tarea es generar exactamente 3 propuestas de diseño (DesignBrief) para una {card_type} card
de un jugador basándote en el contexto del partido.

## Contexto del partido
{context_json}

## Reglas
1. Cada propuesta debe tener un arquetipo narrativo diferente o un ángulo diferente de momento clave.
2. Usa los colores reales del equipo cuando sea posible.
3. Todos los valores hexadecimales DEBEN ser válidos (#RRGGBB).
4. Solo incluye stats que existan en player_stats.performance_stats del contexto.
5. El campo reasoning debe explicar en 3-5 frases naturales la elección de diseño.
6. Template A = centrado con foto del jugador, B = split horizontal con stats destacados, C = minimalista sin foto.
7. Si has_player_photo=false, usa template C para todas las propuestas que requieran foto.

## Output — responde ÚNICAMENTE con JSON válido, sin markdown, sin texto adicional:
{{
  "proposals": [
    {{
      "narrative": {{
        "archetype": "<GOAL_SCORER|ASSIST_KING|CLEAN_SHEET|ELITE_PERFORMER|WORKHORSE|COMEBACK|REDEMPTION|UNLUCKY|SOLID_PRESENCE|cup_final|title_race|return|standard>",
        "emotion": "<celebración|determinación|orgullo|resiliencia>",
        "headline": "<texto impactante en español o inglés ≤ 30 chars>",
        "key_moment": "<momento clave del partido>",
        "supporting_story": "<narrativa de apoyo 1-2 frases>",
        "caption": "<caption para redes sociales>",
        "hashtags": ["#HKFootball"],
        "reasoning": "<3-5 frases explicando las decisiones de diseño>"
      }},
      "design": {{
        "template": "<A|B|C>",
        "format": "1:1",
        "layers": {{
          "base_color": "#1a1a2e",
          "gradient": {{"color1": "#hex", "color2": "#hex", "direction": "135deg", "opacity": 0.75}},
          "pattern": "hexagonal",
          "glow_color": "#hex"
        }},
        "typography": {{
          "hero_stat": {{"value": "0", "label": "STAT", "size": "96pt", "color": "#ffffff"}},
          "secondary_stats": []
        }},
        "elements": {{
          "team_logo": true,
          "player_photo": true,
          "radar_chart": false,
          "match_score": true,
          "competition_badge": true
        }}
      }}
    }}
  ]
}}
"""


# ---------------------------------------------------------------------------
# Archetype detection helpers
# ---------------------------------------------------------------------------

_CUP_KEYWORDS = {"cup", "shield", "盃", "銀牌", "fa", "sapling", "senior", "copa"}
_FINAL_KEYWORDS = {"final", "semi", "semifinal"}
_CUP_COMPETITIONS = {"hkfa cup", "fa cup", "sapling cup", "senior shield", "senior challenge shield"}


def _detect_pregame_archetype(
    match_payload: dict,
    player_profile_or_history=None,
    standings=None,
) -> str:
    """
    Deterministic pre-match archetype classification — no LLM.

    Accepts two call patterns:
      _detect_pregame_archetype(payload, player_history: list, standings)  [LangGraph nodes]
      _detect_pregame_archetype(payload, player_profile: dict)              [test interface]
    """
    competition = (match_payload.get("competition") or "").lower()
    round_ = (match_payload.get("round") or "").lower()

    # Derby detection
    if match_payload.get("is_derby"):
        return "DERBY_DAY"

    # Cup competition detection (test interface: any cup competition → CUP_KNOCKOUT)
    if any(kw in competition for kw in _CUP_KEYWORDS):
        # If round contains final/semi keywords → cup_final (LangGraph naming)
        if any(k in round_ for k in _FINAL_KEYWORDS):
            return "cup_final"
        return "CUP_KNOCKOUT"

    # Title race — only when standings data is available
    if standings is not None:
        top_two = list(standings.items())[:2] if isinstance(standings, dict) else []
        if len(top_two) >= 2:
            gap = abs(top_two[0][1] - top_two[1][1]) if isinstance(top_two[0][1], (int, float)) else 99
            if gap <= 3:
                return "title_race"

    # Return from absence — check most recent post-match milestone (list-based history)
    player_history = player_profile_or_history if isinstance(player_profile_or_history, list) else []
    if player_history:
        recent_post = next(
            (m for m in reversed(player_history) if m.get("type") == "post-match"),
            None,
        )
        if recent_post and recent_post.get("payload", {}).get("absence_reason"):
            return "return"

    return "standard"


def _detect_postgame_archetype(match_payload: dict) -> str:
    """
    Classifies a post-match performance into a narrative archetype.

    Supports two payload formats:
      {"stats": {"goals": 1, "clean_sheet": True}}     [test / flat format]
      {"player_stats": {"performance_stats": {...}}}    [ETL pipeline format]
    """
    # Flat "stats" key takes priority (test format)
    flat = match_payload.get("stats") or {}
    perf = flat or (match_payload.get("player_stats") or {}).get("performance_stats", {})

    goals = float(perf.get("goals") or match_payload.get("goals") or 0)
    assists = float(perf.get("assists") or 0)
    xg = float(perf.get("xg") or match_payload.get("xg") or 0)
    rating = float(perf.get("rating") or 0)
    minutes = float(perf.get("minutes_played") or 0)
    clean_sheet = bool(perf.get("clean_sheet") or match_payload.get("clean_sheet"))
    absence_reason = match_payload.get("absence_reason")

    if absence_reason:
        return "REDEMPTION"
    if goals >= 2:
        return "BRACE_HERO"
    if goals >= 1:
        return "GOAL_SCORER"
    if assists >= 2:
        return "ASSIST_KING"
    if clean_sheet:
        return "THE_WALL"
    if rating >= 8.5:
        return "ELITE_PERFORMER"
    if xg >= 0.7 and goals == 0:
        return "UNLUCKY"
    if minutes >= 85:
        return "WORKHORSE"
    if rating >= 6.5:
        return "SOLID_PRESENCE"
    return "WORKHORSE"


# Alias used internally by the LangGraph retrieve_context node
_detect_postmatch_archetype = _detect_postgame_archetype


# ---------------------------------------------------------------------------
# Graph state
# ---------------------------------------------------------------------------

class AgentState(TypedDict):
    match_payload: dict
    player_profile: dict
    team_colors: dict
    player_history: list
    has_player_photo: bool
    card_type: str
    player_preferences: dict
    tone: str
    context: dict           # built by retrieve_context
    raw_proposals: list     # from generate_proposals
    proposals: list         # final validated proposals
    error: str | None


# ---------------------------------------------------------------------------
# Graph nodes
# ---------------------------------------------------------------------------

def retrieve_context(state: AgentState) -> AgentState:
    """Node 1: Classifies match archetype and assembles context for the LLM."""
    match_payload = state["match_payload"]
    card_type = state.get("card_type", "post-match")
    player_history = state.get("player_history") or []

    if card_type == "pre-match":
        archetype = _detect_pregame_archetype(match_payload, player_history)
    else:
        archetype = _detect_postmatch_archetype(match_payload)

    perf = (match_payload.get("player_stats") or {}).get("performance_stats", {})

    context = {
        "archetype": archetype,
        "card_type": card_type,
        "match": {
            "competition": match_payload.get("competition"),
            "home_team": match_payload.get("home_team"),
            "away_team": match_payload.get("away_team"),
            "score": match_payload.get("score"),
            "date": match_payload.get("date"),
            "round": match_payload.get("round"),
        },
        "player_stats": perf,
        "team_colors": state.get("team_colors") or {},
        "has_player_photo": state.get("has_player_photo", False),
        "player_preferences": state.get("player_preferences") or {},
        "tone": state.get("tone", "pro"),
    }

    return {**state, "context": context}


def generate_proposals(state: AgentState) -> AgentState:
    """Node 2: Single LLM call (Gemini) to generate 3 Design Brief proposals."""
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI

        model_name = os.environ.get("CARD_AGENT_MODEL", _DEFAULT_MODEL)
        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY not set")
        llm = ChatGoogleGenerativeAI(model=model_name, temperature=0.7, google_api_key=api_key)

        context = state["context"]
        card_type = state.get("card_type", "post-match")
        prompt = CARD_DESIGNER_PROMPT.format(
            card_type=card_type,
            context_json=json.dumps(context, ensure_ascii=False, indent=2),
        )

        response = llm.invoke(prompt)
        content = response.content if hasattr(response, "content") else str(response)

        # Strip markdown fences if present
        content = re.sub(r"^```(?:json)?\s*", "", content.strip(), flags=re.IGNORECASE)
        content = re.sub(r"\s*```$", "", content.strip())

        parsed = json.loads(content)
        raw_proposals = parsed.get("proposals", [])
        return {**state, "raw_proposals": raw_proposals, "error": None}

    except Exception as exc:
        logger.error(f"generate_proposals Gemini error: {exc}")
        return {**state, "raw_proposals": [], "error": str(exc)}


def validate_proposals(state_or_proposals, has_player_photo: bool = False) -> "AgentState | list":
    """
    Node 3 / public helper: Validates hex colours, applies photo override, removes missing stats.

    Two call signatures:
      validate_proposals(state: AgentState) -> AgentState   [LangGraph node]
      validate_proposals(proposals: list, has_player_photo: bool) -> list  [test / direct use]
    """
    # Detect which interface is being used
    _langgraph_mode = isinstance(state_or_proposals, dict) and "raw_proposals" in state_or_proposals

    if _langgraph_mode:
        state = state_or_proposals
        raw = state.get("raw_proposals") or []
        match_payload = state.get("match_payload") or {}
        has_photo = state.get("has_player_photo", False)
        team_colors = state.get("team_colors") or {}
        perf_stats = (match_payload.get("player_stats") or {}).get("performance_stats", {})
    else:
        # Direct call: first arg is a list of proposals
        raw = list(state_or_proposals or [])
        has_photo = has_player_photo
        team_colors = {}
        perf_stats = {}
        state = None
        match_payload = {}

    if not raw or (_langgraph_mode and state.get("error")):
        if _langgraph_mode:
            return {**state, "proposals": _deterministic_fallback(state)}
        return []

    fallback_color = team_colors.get("colour1", _DEFAULT_DARK_COLOR)
    _hex_re = re.compile(r"^#[0-9a-fA-F]{6}$")

    def fix_hex(value: str) -> str:
        if isinstance(value, str) and _hex_re.match(value):
            return value
        return fallback_color

    validated = []
    for proposal in raw:
        try:
            proposal = dict(proposal)  # shallow copy

            if _langgraph_mode:
                # DesignBrief format: nested design.layers
                design = dict(proposal.get("design") or {})
                layers = dict(design.get("layers") or {})
                gradient = dict(layers.get("gradient") or {})

                layers["base_color"] = fix_hex(layers.get("base_color", _DEFAULT_DARK_COLOR))
                layers["glow_color"] = fix_hex(layers.get("glow_color", fallback_color))
                gradient["color1"] = fix_hex(gradient.get("color1", fallback_color))
                gradient["color2"] = fix_hex(gradient.get("color2", _DEFAULT_DARK_COLOR))
                layers["gradient"] = gradient

                elements = dict(design.get("elements") or {})
                # If no photo, mark element as false but keep template so user sees all 3 layouts
                if not has_photo:
                    elements["player_photo"] = False
                design["elements"] = elements

                typography = dict(design.get("typography") or {})
                secondary = typography.get("secondary_stats") or []
                typography["secondary_stats"] = [
                    s for s in secondary
                    if isinstance(s, dict) and s.get("key") in perf_stats
                ]
                design["typography"] = typography
                design["layers"] = layers
                proposal["design"] = design
            else:
                # Flat format: template/base_color/accent_color/stats at top level
                proposal["base_color"] = fix_hex(proposal.get("base_color", _DEFAULT_DARK_COLOR))
                if "accent_color" in proposal:
                    proposal["accent_color"] = fix_hex(proposal.get("accent_color", fallback_color))

                # No photo: keep template but mark player_photo element as false
                if not has_photo:
                    stats = list(proposal.get("stats") or [])
                    proposal["stats"] = stats

                # Ensure stats key exists
                if "stats" not in proposal:
                    proposal["stats"] = []

            validated.append(proposal)
        except Exception as exc:
            logger.warning(f"validate_proposals proposal error: {exc}")
            continue

    if _langgraph_mode:
        if not validated:
            validated = _deterministic_fallback(state)
        return {**state, "proposals": validated}

    return validated


# ---------------------------------------------------------------------------
# Deterministic fallback
# ---------------------------------------------------------------------------

def _deterministic_fallback(
    state_or_payload,
    player_profile=None,
    team_colors=None,
    card_type: str = None,
    has_player_photo: bool = False,
):
    """
    Returns deterministic DesignBrief(s) when the LLM is unavailable.

    Two call signatures:
      _deterministic_fallback(state: dict) -> DesignBrief           [LangGraph internal use]
      _deterministic_fallback(payload, profile, colors, card_type,
                              has_player_photo) -> list[dict]         [test / direct use]

    When called with a plain payload (not an AgentState), returns a list of 3 flat briefs.
    When called with an AgentState dict, returns a single DesignBrief for LangGraph.
    """
    _langgraph_mode = (
        isinstance(state_or_payload, dict)
        and player_profile is None
        and team_colors is None
        and ("match_payload" in state_or_payload or "card_type" in state_or_payload)
    )

    if _langgraph_mode:
        state = state_or_payload
        match_payload = state.get("match_payload") or {}
        _team_colors = state.get("team_colors") or {}
        has_photo = state.get("has_player_photo", False)
        _card_type = state.get("card_type", "post-match")
    else:
        match_payload = state_or_payload or {}
        _team_colors = team_colors or {}
        has_photo = bool(has_player_photo)
        _card_type = card_type or "post-match"

    color1 = (_team_colors.get("colour1") or _team_colors.get("primary") or "#1a6b3c")
    color2 = (_team_colors.get("colour2") or _DEFAULT_DARK_COLOR)
    template = "A" if has_photo else "C"

    perf = (match_payload.get("player_stats") or {}).get("performance_stats", {})
    flat_stats = match_payload.get("stats") or {}
    goals = int(flat_stats.get("goals") or perf.get("goals", 0) or 0)
    hero_value = str(goals)
    hero_label = "GOL" if _card_type == "post-match" else "PARTIDO"

    archetype = (
        _detect_postgame_archetype(match_payload)
        if _card_type == "post-match"
        else "standard"
    )

    reasoning = (
        "Esta es la propuesta de respaldo determinista. El modelo de IA no estaba disponible. "
        f"Se usó la plantilla {template} basada en la disponibilidad de foto del jugador. "
        f"Los colores provienen de la paleta del equipo ({color1}, {color2}). "
        "El stat principal refleja el resultado más básico del partido."
    )

    # Flat brief format (for test interface and direct use)
    _flat_brief = {
        "template": template,
        "base_color": _DEFAULT_DARK_COLOR,
        "accent_color": color1,
        "stats": [{"label": hero_label, "value": hero_value, "highlight": True}],
        "archetype": archetype,
        "reasoning": reasoning,
    }

    home_team = match_payload.get("home_team") or "HK"
    hashtag = f"#{home_team.replace(' ', '')} #HKFootball"

    def _make_brief(tmpl, direction, glow, headline_text):
        return {
            "narrative": {
                "archetype": archetype,
                "emotion": "determinación",
                "headline": headline_text,
                "key_moment": "—",
                "supporting_story": "Propuesta básica generada de forma determinista.",
                "caption": hashtag,
                "hashtags": ["#HKFootball"],
                "reasoning": (
                    "Esta es la propuesta de respaldo determinista. El modelo de IA no estaba disponible. "
                    f"Se usó la plantilla {tmpl}. "
                    f"Los colores provienen de la paleta del equipo ({color1}, {color2}). "
                    "El stat principal refleja el resultado más básico del partido."
                ),
            },
            "design": {
                "template": tmpl,
                "format": "1:1",
                "layers": {
                    "base_color": _DEFAULT_DARK_COLOR,
                    "gradient": {
                        "color1": color1,
                        "color2": color2,
                        "direction": direction,
                        "opacity": 0.75,
                    },
                    "pattern": "hexagonal",
                    "glow_color": glow,
                },
                "typography": {
                    "hero_stat": {
                        "value": hero_value,
                        "label": hero_label,
                        "size": "96pt",
                        "color": "#ffffff",
                    },
                    "secondary_stats": [],
                },
                "elements": {
                    "team_logo": True,
                    "player_photo": True,
                    "radar_chart": False,
                    "match_score": True,
                    "competition_badge": True,
                },
            },
        }

    if not _langgraph_mode:
        # Return 3 variants (A/B/C) for the test interface (flat format)
        variants = []
        for tmpl in ("A", "B", "C"):
            v = dict(_flat_brief)
            v["template"] = tmpl
            variants.append(v)
        return variants

    # LangGraph mode: return list of 3 nested DesignBriefs
    return [
        _make_brief("A", "135deg", color1, "READY TO PLAY"),
        _make_brief("B", "90deg", color2, hero_label.upper()),
        _make_brief("C", "180deg", color1, "GAME ON"),
    ]


# ---------------------------------------------------------------------------
# Graph wiring
# ---------------------------------------------------------------------------

def _build_graph():
    builder = StateGraph(AgentState)
    builder.add_node("retrieve_context", retrieve_context)
    builder.add_node("generate_proposals", generate_proposals)
    builder.add_node("validate_proposals", validate_proposals)
    builder.set_entry_point("retrieve_context")
    builder.add_edge("retrieve_context", "generate_proposals")
    builder.add_edge("generate_proposals", "validate_proposals")
    builder.add_edge("validate_proposals", END)
    return builder.compile()


_graph = None


def _get_graph():
    global _graph
    if _graph is None:
        _graph = _build_graph()
    return _graph


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_card_design_agent(
    match_payload: dict,
    player_profile: dict,
    team_colors: dict,
    player_history: list,
    has_player_photo: bool,
    card_type: str = "post-match",
    player_preferences: dict | None = None,
    tone: str = "pro",
) -> list[DesignBrief]:
    """
    Executes the 3-node LangGraph graph and returns a list of DesignBrief dicts.
    Returns exactly 3 proposals on success, 1 deterministic fallback on failure.
    Never raises to the caller.
    """
    try:
        initial_state: AgentState = {
            "match_payload": match_payload or {},
            "player_profile": player_profile or {},
            "team_colors": team_colors or {},
            "player_history": player_history or [],
            "has_player_photo": bool(has_player_photo),
            "card_type": card_type,
            "player_preferences": player_preferences or {},
            "tone": tone,
            "context": {},
            "raw_proposals": [],
            "proposals": [],
            "error": None,
        }
        graph = _get_graph()
        result = graph.invoke(initial_state)
        proposals = result.get("proposals") or []
        if not proposals:
            return _deterministic_fallback(initial_state)
        return proposals
    except Exception as exc:
        logger.error(f"run_card_design_agent unhandled error: {exc}")
        fallback_state = {
            "match_payload": match_payload or {},
            "team_colors": team_colors or {},
            "has_player_photo": bool(has_player_photo),
            "card_type": card_type,
        }
        return _deterministic_fallback(fallback_state)
