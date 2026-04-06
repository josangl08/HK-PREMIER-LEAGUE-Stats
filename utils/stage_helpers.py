# ABOUTME: Helper functions for rendering Stage scenarios, AI widgets, and image gallery (Feature G).
# ABOUTME: Renders player dashboard (default), post-match, pre-match, career-insights, and Action Node gallery views.

import logging
import os
import threading
import html as _html_lib
from pathlib import Path
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from dash import html, dcc
import dash_bootstrap_components as dbc
from typing import Dict, List, Any, Optional
from flask_login import current_user
from sqlalchemy import select

from utils.app_context import get_hong_kong_data_manager
from utils.chart_helpers import apply_hkfa_theme, glass_figure_layout, HKFATheme
import dash_cytoscape as cyto
from utils.ai_helpers import umap_scatter_chart, constellation_chart, _build_knn_edges
from data.processors.hong_kong_processor import POSITION_FULL_NAMES
from utils.competition_helpers import get_competition_logo, normalize_competition

# Numba/UMAP is not thread-safe with the default workqueue layer.
# This lock serializes concurrent calls to fit_umap across Flask threads.
_umap_lock = threading.Lock()

logger = logging.getLogger(__name__)


def _get_logged_in_player_id() -> str:
    try:
        player_id = getattr(current_user, "player_id", None)
        if isinstance(player_id, str) and player_id.strip():
            return player_id.strip()
    except Exception:
        pass
    return ""


def _clean_url(url: str) -> str:
    """Unescape HTML entities in a URL and strip trailing quotes/whitespace."""
    if not url:
        return url
    return _html_lib.unescape(url).rstrip('"').strip()


def _normalize_position_code(raw: Any) -> str:
    value = str(raw or "").strip().upper()
    if not value:
        return ""
    return {
        "ED": "RW",
        "EI": "LW",
        "ID": "RM",
        "II": "LM",
        "MCO": "AMF",
        "CMF": "CM",
        "DMF": "DM",
    }.get(value, value)


def _get_logged_in_player_current_role() -> str:
    player_id = _get_logged_in_player_id()
    if not player_id:
        return ""
    try:
        from models.db_models import MatchHistory
        from utils.db_engine import SessionFactory

        with SessionFactory() as session:
            stmt = (
                select(MatchHistory)
                .where(MatchHistory.player_id == player_id)
                .order_by(MatchHistory.date.desc())
                .limit(8)
            )
            matches = session.execute(stmt).scalars().all()
    except Exception:
        return ""

    weighted: Dict[str, int] = {}
    for idx, match in enumerate(matches):
        code = _normalize_position_code(getattr(match, "position", None))
        if not code:
            continue
        minutes = int(getattr(match, "minutes_played", 0) or 0)
        weight = max(minutes, 1) + max(0, 8 - idx)
        weighted[code] = weighted.get(code, 0) + weight
    if not weighted:
        return ""
    return max(weighted.items(), key=lambda item: item[1])[0]

# Hex color palettes per competition — sourced from official branding
# Sync with player_portal_callbacks.py
_COMPETITION_COLOR_MAP = {
    "HK Premier League": ["#ac0c34", "#1c1c1c", "#b40c34"],
    "Sapling Cup": ["#153465", "#c1cf31", "#78ac46"],
    "Senior Shield": ["#050505", "#b8b8b8", "#444444"],
    "HKFA Cup": ["#bb9d5e", "#bcbcbc", "#bcbcc4"],
    "AFC Cup": ["#c6bcb6", "#318cd6", "#191c1a", "#61af69", "#eb8b3e"],
    "AFC Champions League Two": ["#111112", "#cec9c1", "#218ec2", "#f7a240", "#959b9e"],
    "AFC Champions League": ["#111112", "#cec9c1", "#218ec2", "#f7a240", "#959b9e"],
}

def _normalize_comp(raw: str) -> str:
    """Normalize a competition name using central helper."""
    return normalize_competition(raw)

def _competition_color(competition: str) -> str:
    """Return primary hex color for a competition name."""
    palette = _COMPETITION_COLOR_MAP.get(_normalize_comp(competition), ["#0d6efd"])
    return palette[0]

def _comp_badge(competition: str) -> "html.Span | None":
    """Return a styled Span badge with the competition name."""
    comp = _normalize_comp(competition)
    if not comp:
        return None
    bg_color = _competition_color(comp)
    text_color = "#ffffff"
    light_bgs = [
        "#cec9c1", "#bcbcbc", "#d1dee6", "#ededec", "#e1e3e5", 
        "#c6bcb6", "#bb9d5e", "#d0d0d5", "#f7e4e7"
    ]
    if bg_color.lower() in [c.lower() for c in light_bgs]:
        text_color = "#18181a"

    return html.Span(
        comp,
        className="small px-2 py-0 rounded-1 fw-semibold",
        style={
            "backgroundColor": bg_color,
            "color": text_color,
            "fontSize": "0.7rem",
            "display": "inline-block",
            "lineHeight": "1.4",
        }
    )

# Metrics displayed in the projector per position group.
# Keys match the Position_Group values from the processed DataFrame.
POSITION_METRICS: Dict[str, List[str]] = {
    "Forward":    ["Goals", "xG", "Shots on target, %", "Goal conversion, %"],
    "Winger":     ["Goals", "Assists", "Dribbles per 90", "Crosses per 90"],
    "Midfielder": ["Assists", "xA", "Key passes per 90", "Accurate passes, %"],
    "Defender":   ["Interceptions per 90", "Defensive duels won, %", "Aerial duels won, %", "Shots blocked per 90"],
    "Goalkeeper": ["Save rate, %", "Clean sheets", "Prevented goals per 90", "xG against per 90"],
}

# Extra composite metrics to show as a 5th bar when available.
COMPOSITE_METRICS: Dict[str, str] = {
    "Forward": "efficiency_index",
    "Winger": "efficiency_index",
    "Midfielder": "efficiency_index",
    "Defender": "defensive_wall"
}

# General metrics added to the radar on top of POSITION_METRICS for a fuller player picture.
# These must be present in PercentileRankingSystem.key_metrics to have percentile data.
SUPPLEMENTAL_RADAR_METRICS: Dict[str, List[str]] = {
    "Forward":    ["Passes per 90", "Duels won, %"],
    "Winger":     ["Defensive duels won, %", "Passes per 90"],
    "Midfielder": ["Interceptions per 90", "Defensive duels won, %"],
    "Defender":   ["Passes per 90", "xG"],
    "Goalkeeper": [],
}

# Top-3 metrics shown as active lines in the multi-metric Career Arc chart.
# All other metrics in CAREER_ARC_ALL_METRICS are rendered as "legendonly".
TOP3_CAREER_METRICS: Dict[str, List[str]] = {
    "Forward":    ["Goals", "xG", "Assists"],
    "Winger":     ["Goals", "Assists", "Successful dribbles, %"],
    "Midfielder": ["Assists", "xA", "Accurate passes, %"],
    "Defender":   ["PAdj interceptions per 90", "Defensive duels won, %", "Aerial duels won, %"],
    "Goalkeeper": ["Prevented goals", "Save rate, %", "Clean sheets"],
}

# Full ordered metric list for the Career Arc multi-line chart (5-10 metrics).
CAREER_ARC_ALL_METRICS: Dict[str, List[str]] = {
    "Forward":    ["Goals", "xG", "Assists", "xA", "Shots on target, %", "Goal conversion, %", "Minutes played"],
    "Winger":     ["Goals", "Assists", "xA", "Successful dribbles, %", "Crosses per 90", "Minutes played"],
    "Midfielder": ["Assists", "xA", "Accurate passes, %", "Key passes per 90", "Goals", "Minutes played"],
    "Defender":   ["PAdj interceptions per 90", "Defensive duels won, %", "Aerial duels won, %", "Shots blocked per 90", "Minutes played"],
    "Goalkeeper": ["Prevented goals", "Save rate, %", "Clean sheets", "xG against per 90", "Minutes played"],
}


def get_career_arc_visibility(metric_name: str, pos_group: str) -> Any:
    """
    Returns Plotly visibility value for a Career Arc trace.
    Top-3 positional metrics → True (visible); all others → 'legendonly'.
    Used by _build_career_arc to set trace visibility without manual toggling.
    """
    top3 = TOP3_CAREER_METRICS.get(pos_group, [])
    return True if metric_name in top3 else "legendonly"


_CURRENT_SEASON_FALLBACK = "2025-26"
_CARD_CACHE_DIR = Path("data/cache/cards")


def _hex_to_rgb(hex_color: str) -> str:
    """Converts '#RRGGBB' to 'R, G, B' string for rgba() CSS usage."""
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"{r}, {g}, {b}"


def _get_current_season() -> str:
    """Returns the active season from the data manager, falling back to a constant."""
    try:
        return get_hong_kong_data_manager().current_season or _CURRENT_SEASON_FALLBACK
    except Exception:
        return _CURRENT_SEASON_FALLBACK


_PLAYER_CARDS_ROOT = Path("data/player_cards")


def _resolve_team_logo(team_name: str) -> Optional[str]:
    """Busca logo en assets/team_logos/ por nombre normalizado."""
    if not team_name:
        return None
    normalized = team_name.lower().replace(" ", "_").replace("-", "_")
    for ext in ("png", "svg"):
        candidate = Path(f"assets/team_logos/{normalized}.{ext}")
        if candidate.exists():
            return str(candidate)
    return None


def get_cached_image_path(milestone_id: str, player_id: str = "") -> Optional[str]:
    """
    Returns the path to a generated card PNG for the given milestone ID.
    Checks data/player_cards/{player_id}/{milestone_id}/ first (new Card Studio path),
    then falls back to data/cache/cards/ for backward compatibility.
    """
    if not milestone_id:
        return None
    try:
        # New path: data/player_cards/{player_id}/{milestone_id}/card_*.png
        if player_id:
            new_dir = _PLAYER_CARDS_ROOT / player_id / milestone_id
            if new_dir.exists():
                for fmt in ("1_1", "9_16", "16_9"):
                    candidate = new_dir / f"card_{fmt}.png"
                    if candidate.exists():
                        return str(candidate)
        # Wildcard search across all player dirs for this milestone
        for candidate in _PLAYER_CARDS_ROOT.glob(f"*/{milestone_id}/card_*.png"):
            if candidate.exists():
                return str(candidate)
        # Legacy fallback: data/cache/cards/{milestone_id}.*
        for ext in (".png", ".jpg", ".jpeg", ".webp"):
            candidate = _CARD_CACHE_DIR / f"{milestone_id}{ext}"
            if candidate.exists():
                return str(candidate)
    except Exception as e:
        logger.warning(f"get_cached_image_path error for '{milestone_id}': {e}")
    return None


def render_image_gallery(image_path: Optional[str]) -> html.Div:
    """
    Returns a glassmorphic image gallery view for the Stage panel.
    Shows the image if path is valid, otherwise a graceful placeholder.
    Close button is rendered statically in the layout (gallery-close-btn).
    """
    if image_path and os.path.isfile(image_path):
        content = html.Div(
            [
                html.Div(
                    html.Img(
                        src=image_path,
                        className="img-fluid rounded",
                        style={"maxHeight": "400px", "objectFit": "contain"},
                    ),
                    className="text-center",
                ),
                html.Small(
                    os.path.basename(image_path),
                    className="text-muted d-block text-center mt-2",
                ),
            ]
        )
    else:
        content = html.Div(
            [
                html.I(className="bi bi-image text-muted", style={"fontSize": "3rem"}),
                html.P("No hay imagen disponible", className="text-muted mt-2 mb-0"),
            ],
            className="text-center py-4",
        )

    return html.Div(
        content,
        className="stage-gallery-view",
    )


def _infer_position_group(position: str) -> str:
    """Maps a raw Wyscout position string to one of the POSITION_METRICS keys."""
    if not position:
        return "Midfielder"
    p = position.upper()
    if "GK" in p:
        return "Goalkeeper"
    # CF (Center Forward) has absolute priority
    if "CF" in p:
        return "Forward"
    if any(x in p for x in ("RWF", "LWF")):
        return "Forward"
    if any(x in p for x in ("RW", "LW", "RAMF", "LAMF", "SS")):
        return "Winger"
    if any(x in p for x in ("CB", "RCB", "LCB", "RB", "LB", "RWB", "LWB")):
        return "Defender"
    return "Midfielder"

_METRIC_TO_ARCHETYPE: Dict[str, str] = {
    "Goals": "Lethal Finisher",
    "xG": "Clinical Striker",
    "Goal conversion, %": "Efficient Finisher",
    "Shots on target, %": "Precise Shooter",
    "Assists": "Creative Force",
    "Key passes per 90": "Playmaker",
    "Accurate passes, %": "Metronome",
    "xA": "Chance Creator",
    "Dribbles per 90": "Tricky Dribbler",
    "Crosses per 90": "Wide Threat",
    "Interceptions per 90": "Ball Winner",
    "Defensive duels won, %": "Defensive Wall",
    "Aerial duels won, %": "Aerial Threat",
    "Shots blocked per 90": "Shot Blocker",
    "Save rate, %": "Shot Stopper",
    "Clean sheets": "Reliable Keeper",
    "Prevented goals per 90": "Last Line",
}


def _fetch_player_season_history(player_name: str) -> pd.DataFrame:
    """
    Queries PlayerSeasonStat across all seasons for a player directly from SQL.
    Returns a DataFrame sorted ascending by season_id with core + advanced metrics.
    Never modifies the DataManager state.
    """
    try:
        from sqlalchemy import select
        from models.db_models import Player, PlayerSeasonStat
        from utils.db_engine import SessionFactory

        session = SessionFactory()
        try:
            stmt = (
                select(PlayerSeasonStat, Player.name)
                .join(Player, PlayerSeasonStat.player_id == Player.id)
                .where(Player.name == player_name)
                .order_by(PlayerSeasonStat.season_id)
            )
            results = session.execute(stmt).all()
            rows = []
            for stat_obj, _name in results:
                row = {
                    "Season": stat_obj.season_id,
                    "Goals": stat_obj.goals or 0,
                    "Assists": stat_obj.assists or 0,
                    "Minutes played": stat_obj.minutes_played or 0,
                    "Matches played": stat_obj.matches_played or 0,
                    "Yellow cards": stat_obj.yellow_cards or 0,
                    "Red cards": stat_obj.red_cards or 0,
                }
                if stat_obj.advanced_stats:
                    row.update(stat_obj.advanced_stats)
                    # Normalize key aliases so downstream code has consistent names
                    # regardless of Wyscout API version casing variations.
                    _STAT_ALIASES = {
                        "xg": "xG", "xG_per_90": "xG", "expected_goals": "xG",
                        "xa": "xA", "xA_per_90": "xA", "expected_assists": "xA",
                        "padj_interceptions_per_90": "PAdj interceptions per 90",
                        # Wyscout stores PAdj Interceptions without "per 90" suffix
                        "PAdj Interceptions": "PAdj interceptions per 90",
                        "progressive_runs_per_90": "Progressive runs per 90",
                        "successful_dribbles_pct": "Successful dribbles, %",
                        "save_pct": "Save rate, %", "save_rate": "Save rate, %",
                        "xclean_sheets": "xClean sheets", "xcleansheeets": "xClean sheets",
                    }
                    for src, dest in _STAT_ALIASES.items():
                        if src in row and dest not in row:
                            row[dest] = row[src]
                    # Compute Prevented goals for GKs when not already present
                    if "Prevented goals" not in row:
                        xg_against = row.get("xG against", row.get("xg_against", 0)) or 0
                        goals_conceded = row.get("Goals conceded", row.get("goals_conceded", 0)) or 0
                        if xg_against or goals_conceded:
                            row["Prevented goals"] = round(float(xg_against) - float(goals_conceded), 2)
                rows.append(row)
            df = pd.DataFrame(rows) if rows else pd.DataFrame()
            # Sort by season string ascending (e.g. "2018-19" < "2020-21")
            if not df.empty and "Season" in df.columns:
                df = df.sort_values("Season").reset_index(drop=True)
            return df
        finally:
            session.close()
    except Exception as e:
        logger.warning(f"_fetch_player_season_history error for '{player_name}': {e}")
        return pd.DataFrame()


def _get_archetype_label(player_name: str, pos_group: str, dm) -> Optional[str]:
    """
    Returns a human-readable archetype label for a player based on which position
    metric they outperform the league average most.
    Falls back to '<Position> Specialist' when data is insufficient.
    """
    try:
        df = dm.processed_data
        if df is None or df.empty:
            return None
        player_row = df[df["Player"] == player_name]
        if player_row.empty:
            return None

        pos_df = (
            df[df["Position_Group"] == pos_group]
            if "Position_Group" in df.columns
            else df
        )
        metrics = POSITION_METRICS.get(pos_group, [])

        best_metric = None
        best_percentile = -1.0
        for m in metrics:
            if m not in df.columns:
                continue
            player_val = float(player_row.iloc[0].get(m) or 0)
            league_vals = pos_df[m].dropna()
            if len(league_vals) < 2:
                continue
            pct = float((league_vals < player_val).mean() * 100)
            if pct > best_percentile:
                best_percentile = pct
                best_metric = m

        if best_metric and best_percentile > 40:
            return _METRIC_TO_ARCHETYPE.get(best_metric, f"{pos_group} Specialist")
        return f"{pos_group} Specialist"
    except Exception as e:
        logger.debug(f"_get_archetype_label error: {e}")
        return None


_CLUSTER_PALETTE = [
    "#00b4d8", "#06d6a0", "#ffb703", "#e63946", "#a8dadc",
    "#8338ec", "#fb8500", "#3a86ff", "#ff006e", "#43aa8b",
]


_ARCHETYPE_STYLE = {
    # (archetype_keyword, position_group) -> style sentence
    ("creative",  "Forward"):    "As a forward, his creative output adds a rare distributional layer to his attacking play.",
    ("creative",  "Midfielder"): "As a midfielder, his passing vision and precision make him the team's primary playmaker.",
    ("creative",  "Winger"):     "As a winger, he combines delivery quality with smart movement to unlock defences.",
    ("creative",  "Defender"):   "As a defender, his ball-playing ability allows him to initiate attacks from the back.",
    ("maestro",   "Forward"):    "As a forward, his creative output adds a rare distributional layer to his attacking play.",
    ("maestro",   "Midfielder"): "As a midfielder, his passing vision and precision make him the team's primary playmaker.",
    ("maestro",   "Winger"):     "As a winger, he combines delivery quality with smart movement to unlock defences.",
    ("maestro",   "Defender"):   "As a defender, his ball-playing ability allows him to initiate attacks from the back.",
    ("striker",   "Forward"):    "As a forward, his clinical finishing and movement into scoring positions define his threat.",
    ("striker",   "Winger"):     "As a winger, his cutting edge and direct runs make him a constant scoring danger.",
    ("forward",   "Forward"):    "As a forward, his goal output and positional instinct give his team a reliable focal point.",
    ("forward",   "Midfielder"): "As a midfielder, his late runs and finishing add a decisive dimension to his game.",
    ("defender",  "Defender"):   "As a defender, he reads the game early, wins duels, and cuts out danger before it develops.",
    ("defender",  "Midfielder"): "As a midfielder, his defensive awareness protects the team and disrupts opposition build-up.",
    ("physical",  "Defender"):   "As a defender, his strength and aerial power make him dominant in defensive duels.",
    ("physical",  "Forward"):    "As a forward, his physicality wins knock-downs and stretches opposition defensive lines.",
    ("physical",  "Midfielder"): "As a midfielder, his power helps him win possession and drive forward through pressure.",
    ("engine",    "Midfielder"): "As a midfielder, his relentless work rate links every line and covers ground continuously.",
    ("engine",    "Winger"):     "As a winger, his energy and pressing off the ball create turnovers high up the pitch.",
    ("winger",    "Winger"):     "As a winger, he beats defenders with pace and dribbling before delivering into danger areas.",
    ("winger",    "Forward"):    "As a forward, his wide movement and dribbling create space and stretch defensive blocks.",
    ("goalkeep",  "Goalkeeper"): "As a goalkeeper, his distribution and shot-stopping make him a key starting point for attacks.",
}


def _build_archetype_bio(
    player_name: str,
    cluster_label: str,
    pos_group: str,
    trait_pct_pairs: list,  # [(clean_trait_name, pct_label), ...]
) -> str:
    """Generates a player-specific 2-sentence archetype description."""
    first_name = player_name.split()[0] if player_name else "This player"

    # Sentence 1: qualifying traits
    if len(trait_pct_pairs) >= 2:
        t1, p1 = trait_pct_pairs[0]
        t2, p2 = trait_pct_pairs[1]
        sent1 = f"{first_name} qualifies as a {cluster_label} through his {t1} ({p1}) and {t2} ({p2})."
    elif len(trait_pct_pairs) == 1:
        t1, p1 = trait_pct_pairs[0]
        sent1 = f"{first_name} qualifies as a {cluster_label} through his elite {t1} ({p1})."
    else:
        sent1 = f"{first_name} is classified as a {cluster_label}."

    # Sentence 2: positional style
    label_lower = cluster_label.lower()
    sent2 = ""
    for (kw, pos), style in _ARCHETYPE_STYLE.items():
        if kw in label_lower and pos_group.lower().startswith(pos.lower()):
            sent2 = style
            break
    if not sent2:
        # Generic fallback by position
        _pos_fallback = {
            "Forward":    "His standout metrics make him one of the most distinctive attackers in HKPL.",
            "Midfielder": "His standout metrics make him one of the most distinctive midfielders in HKPL.",
            "Defender":   "His standout metrics make him one of the most distinctive defenders in HKPL.",
            "Winger":     "His standout metrics make him one of the most distinctive wide players in HKPL.",
            "Goalkeeper": "His standout metrics make him one of the most distinctive keepers in HKPL.",
        }
        sent2 = _pos_fallback.get(pos_group, "His standout metrics set him apart across the HKPL.")

    return f"{sent1} {sent2}"


def _build_cluster_dna(data: Dict) -> html.Div:
    """§2 Cluster DNA: K-Means cluster label, HKPL % share, DNA mini-bars vs. centroid."""
    from scipy.stats import norm as _norm

    cluster_id    = data.get("cluster_id")
    cluster_label = data.get("cluster_label")
    cluster_size  = data.get("cluster_size_pct")
    centroid      = data.get("cluster_centroid") or {}
    player_vec    = data.get("player_scaled_vec") or {}
    pos_group     = data.get("pos_group") or ""
    player_name   = data.get("player_name") or ""
    archetype     = data.get("archetype") or pos_group or "Player"

    # Gold used for the avg marker — contrasts well against dark backgrounds
    AVG_MARKER_COLOR = HKFATheme.ACCENT_GOLD

    header = html.H6([
        html.I(className="bi bi-hexagon-fill me-2"),
        html.Span("Tactical DNA", className="animate-glass-draw"),
    ], className="mb-2 fw-semibold", style={"color": "var(--accent-cyan, #00d4ff)"})

    # ── Fallback to legacy badge when K-Means not available ───────────────
    if cluster_id is None:
        pos_icons = {
            "Forward": "bi-lightning-charge-fill", "Winger": "bi-wind",
            "Midfielder": "bi-shuffle", "Defender": "bi-shield-fill",
            "Goalkeeper": "bi-bullseye",
        }
        fallback_badge = html.Span([
            html.I(className=f"bi {pos_icons.get(pos_group, 'bi-person-fill')} me-1",
                   style={"color": HKFATheme.ACCENT_GOLD, "fontSize": "0.75rem"}),
            html.Span(archetype, style={"color": HKFATheme.ACCENT_GOLD, "fontWeight": "700", "fontSize": "0.75rem"}),
        ], style={
            "display": "inline-flex", "alignItems": "center",
            "padding": "2px 10px", "borderRadius": "12px",
            "background": f"rgba({_hex_to_rgb(HKFATheme.ACCENT_GOLD)}, 0.1)",
            "border": f"1px solid rgba({_hex_to_rgb(HKFATheme.ACCENT_GOLD)}, 0.35)",
        })
        return html.Div([header, fallback_badge])

    cluster_color = _CLUSTER_PALETTE[cluster_id % len(_CLUSTER_PALETTE)]

    # ── Pre-compute percentile labels (needed for description + bars) ─────
    def _pct_label(p_val):
        norm_pct = _norm.cdf(p_val) * 100
        if p_val > 0:
            return f"Top {max(1, round(100 - norm_pct))}%", cluster_color
        return f"Btm {max(1, round(norm_pct))}%", HKFATheme.TEXT_SECONDARY

    def _clean_trait(name):
        return name.split(",")[0].split(" per")[0].replace("Successful ", "").strip()

    trait_pct_pairs = [
        (_clean_trait(t), _pct_label(player_vec[t])[0])
        for t in list(centroid.keys())[:2]
        if t in player_vec
    ]

    # ── Archetype description: player-specific ────────────────────────────
    description = _build_archetype_bio(player_name, cluster_label, pos_group, trait_pct_pairs)

    label_row = html.Div([
        # Left: archetype badge
        html.Div([
            html.Span("⬡", style={"color": cluster_color, "marginRight": "6px", "fontSize": "1rem"}),
            html.Span(cluster_label, style={"fontWeight": "700", "fontSize": "0.95rem", "color": HKFATheme.TEXT_PRIMARY, "whiteSpace": "nowrap"}),
        ], style={"display": "flex", "alignItems": "center", "flexShrink": "0"}),
        # Right: title + description block
        html.Div([
            html.Div("Archetype Profile", style={
                "fontSize": "0.6rem", "fontWeight": "700", "letterSpacing": "0.08em",
                "textTransform": "uppercase", "color": cluster_color,
                "marginBottom": "3px", "textAlign": "right",
            }),
            html.Span(description, style={
                "fontSize": "0.7rem", "color": HKFATheme.TEXT_SECONDARY,
                "fontStyle": "italic", "lineHeight": "1.35",
                "display": "block", "textAlign": "right",
            }),
        ], style={"maxWidth": "55%", "paddingLeft": "10px"}),
    ], style={"display": "flex", "justifyContent": "space-between", "alignItems": "flex-start", "marginBottom": "4px"})

    share_text = html.Div(
        f"{cluster_size:.1f}% of HKPL players",
        style={"fontSize": "0.75rem", "color": HKFATheme.TEXT_SECONDARY, "marginBottom": "14px", "marginLeft": "22px"},
    )

    # ── DNA Traits: bar on top, avg marker crossing bar, text below ───────
    dna_rows = []
    if centroid and player_vec:
        try:
            for t in list(centroid.keys()):
                c_val = centroid[t]
                p_val = player_vec[t]

                p_pct = max(5, min(95, (p_val + 2) / 4 * 100))
                c_pct = max(5, min(95, (c_val + 2) / 4 * 100))

                pct_label, label_color = _pct_label(p_val)
                trait_label = _clean_trait(t)

                dna_rows.append(html.Div([
                    # Trait name + percentile
                    html.Div([
                        html.Span(trait_label, style={"fontSize": "0.68rem", "color": HKFATheme.TEXT_SECONDARY, "flex": "1"}),
                        html.Span(pct_label, style={"fontSize": "0.65rem", "fontWeight": "700", "color": label_color}),
                    ], style={"display": "flex", "justifyContent": "space-between", "marginBottom": "3px"}),

                    # Bar track + player fill + avg marker crossing through bar
                    html.Div(style={
                        "position": "relative",
                        "height": "4px",
                        "background": "rgba(255,255,255,0.07)",
                        "borderRadius": "2px",
                    }, children=[
                        # Player fill
                        html.Div(style={
                            "height": "100%", "width": f"{p_pct}%",
                            "background": cluster_color, "borderRadius": "2px",
                            "boxShadow": f"0 0 8px {cluster_color}66",
                        }),
                        # Avg marker — crosses above and below the bar
                        html.Div(style={
                            "position": "absolute",
                            "left": f"{c_pct}%", "top": "-4px",
                            "transform": "translateX(-50%)",
                            "height": "12px", "width": "2px",
                            "background": AVG_MARKER_COLOR,
                            "boxShadow": f"0 0 5px {AVG_MARKER_COLOR}99",
                            "borderRadius": "1px",
                            "zIndex": "2",
                        }),
                    ]),

                    # "avg" label below bar, aligned with the marker
                    html.Div(style={"position": "relative", "height": "14px"}, children=[
                        html.Span("avg", style={
                            "position": "absolute",
                            "left": f"{c_pct}%",
                            "top": "2px",
                            "transform": "translateX(-50%)",
                            "fontSize": "0.48rem",
                            "color": AVG_MARKER_COLOR,
                            "letterSpacing": "0.04em",
                            "fontWeight": "600",
                        }),
                    ]),
                ], style={"marginBottom": "6px"}))
        except Exception as e:
            logger.warning(f"_build_cluster_dna chart error: {e}")

    return html.Div([
        header,
        label_row,
        share_text,
        html.Div("Core Identity Traits", style={
            "fontSize": "0.6rem", "color": HKFATheme.TEXT_TERTIARY,
            "textTransform": "uppercase", "letterSpacing": "0.08em", "marginBottom": "8px"
        }),
        html.Div(dna_rows, style={"padding": "0 4px"}),
    ])


def _build_career_cluster_evolution(data: Dict) -> html.Div:
    """§5 Career Cluster Evolution: horizontal timeline of K-Means cluster per season."""
    history_df = data.get("history_df", pd.DataFrame())

    if history_df.empty or len(history_df) < 2:
        return html.P("Evolución disponible a partir de 2 temporadas", className="text-muted small")

    try:
        from ai_models.model_registry import ModelRegistry
        from ai_models.clustering import label_archetypes

        km = ModelRegistry().load("kmeans_overall_k5")
        if km is None:
            return html.Span()

        dm_e = get_hong_kong_data_manager()
        df_e = dm_e.processed_data
        if df_e is None or df_e.empty:
            return html.Span()

        meta_cols_e = {"Player", "Season", "Team", "Position"}
        feature_cols_e = [
            c for c in df_e.columns
            if c not in meta_cols_e and pd.api.types.is_numeric_dtype(df_e[c])
        ]
        archetype_labels_e = label_archetypes(km, feature_cols_e)

        timeline_items = []
        for _, row in history_df.iterrows():
            season = row.get("Season", "?")
            # Build vector from history row using matching feature columns
            feat_vals = [float(row.get(c, 0) or 0) for c in feature_cols_e]
            vector = np.array(feat_vals).reshape(1, -1)
            cid = int(km.predict(vector)[0])
            clabel = archetype_labels_e[cid] if cid < len(archetype_labels_e) else f"Cluster {cid}"
            color = _CLUSTER_PALETTE[cid % len(_CLUSTER_PALETTE)]

            timeline_items.append(
                dbc.Badge(
                    [html.Span(str(season), style={"fontSize": "0.6rem", "display": "block",
                                                    "opacity": "0.8"}),
                     html.Span(clabel, style={"fontSize": "0.68rem", "fontWeight": "600"})],
                    style={"backgroundColor": color, "color": "#fff", "padding": "4px 8px",
                           "borderRadius": "8px", "whiteSpace": "nowrap"},
                )
            )

        # Interleave arrows
        items_with_arrows = []
        for i, item in enumerate(timeline_items):
            items_with_arrows.append(item)
            if i < len(timeline_items) - 1:
                items_with_arrows.append(
                    html.Span("→", style={"color": HKFATheme.TEXT_SECONDARY,
                                          "margin": "0 4px", "alignSelf": "center", "fontSize": "0.75rem"})
                )

        return html.Div([
            html.Div("Cluster evolution", style={
                "fontSize": "0.65rem", "color": HKFATheme.TEXT_SECONDARY,
                "textTransform": "uppercase", "letterSpacing": "0.04em", "marginBottom": "6px",
            }),
            html.Div(items_with_arrows, style={
                "display": "flex", "alignItems": "center", "flexWrap": "wrap", "gap": "4px",
            }),
        ])

    except Exception as e:
        logger.debug(f"_build_career_cluster_evolution error: {e}")
        return html.Span()


def _generate_career_insight(
    history_df: pd.DataFrame,
    primary_metric: str,
    player_name: str,
    pos_group: str = "",
    form_trend: Optional[Dict] = None,
    transferability: Optional[Dict] = None,
) -> Optional[str]:
    """
    Returns a tactical insight about a player's career trajectory.

    Attempts a Gemini API call that synthesises LSTM form data and TabPFN
    transferability scores into a 2-sentence scout-level report.
    Falls back to the original template-based approach when the API is
    unavailable or the API key is not configured.

    Args:
        history_df:       Multi-season history DataFrame.
        primary_metric:   Key metric to highlight (position-specific).
        player_name:      Player display name.
        pos_group:        Position group for contextual prompting.
        form_trend:       Output of ``get_form_trend`` (optional).
        transferability:  Output of ``get_transferability_score`` (optional).
    """
    def _template_fallback() -> Optional[str]:
        try:
            if history_df.empty or primary_metric not in history_df.columns:
                return None
            vals = history_df[primary_metric].dropna().tolist()
            seasons = history_df["Season"].tolist()
            if not vals:
                return None
            current = vals[-1]
            metric_label = primary_metric.split(",")[0].strip().lower()
            if len(vals) == 1:
                return f"{int(current)} {metric_label} in {seasons[-1]}."
            if current == max(vals) and len(vals) > 1:
                return f"Best-ever season for {metric_label} — {int(current)} recorded in {seasons[-1]}."
            delta = current - vals[-2]
            if delta > 0:
                return f"▲ {int(delta)} more {metric_label} than last season — upward trajectory."
            elif delta < 0:
                return f"▼ {int(abs(delta))} fewer {metric_label} than last season."
            return f"Consistent output — same {metric_label} as last season ({int(current)})."
        except Exception:
            return None

    try:
        from utils.ai_config import GOOGLE_API_KEY, AI_DEFAULTS
        if not GOOGLE_API_KEY:
            return _template_fallback()

        import google.generativeai as genai  # type: ignore

        # ── Build brief stats string ───────────────────────────────────────
        brief_stats = ""
        if not history_df.empty and primary_metric in history_df.columns:
            last3 = history_df.tail(3)
            parts = []
            for _, r in last3.iterrows():
                val = r.get(primary_metric, 0)
                parts.append(f"{r['Season']}: {val:.1f}")
            brief_stats = ", ".join(parts)

        trend_str    = form_trend.get("trend", "stable") if form_trend else "unknown"
        slope_str    = f"{form_trend.get('slope', 0.0):+.3f}" if form_trend else "N/A"
        t_score      = f"{round((transferability or {}).get('score', 0) * 100)}%" if transferability else "N/A"
        t_label      = (transferability or {}).get("label", "")

        prompt = (
            f"Football scout context. Player: {player_name} ({pos_group}).\n"
            f"Last 5-match form trend: {trend_str} (slope {slope_str}).\n"
            f"Transferability Score for a higher-tier league: {t_score} ({t_label}).\n"
            f"Season {primary_metric.split(',')[0].strip()} history: {brief_stats}.\n"
            f"Write exactly 2 concise sentences of tactical insight for a professional scout. "
            f"Focus on development trajectory and transfer potential. No bullet points."
        )

        genai.configure(api_key=GOOGLE_API_KEY)
        model_name = AI_DEFAULTS.get("gemini", {}).get("model", "gemini-2.5-flash")
        model = genai.GenerativeModel(model_name)
        response = model.generate_content(
            prompt,
            generation_config={"temperature": 0.6, "max_output_tokens": 150},
            request_options={"timeout": 30},
        )
        text = response.text.strip()
        if text:
            return text

    except Exception as e:
        logger.debug(f"_generate_career_insight Gemini error: {e}")

    return _template_fallback()


def _build_delta_kpis(
    current_row: pd.Series,
    prev_row: pd.Series,
    metrics: List[str],
) -> html.Div:
    """
    Renders a row of compact KPI badges showing season-over-season deltas.
    Green arrow = improvement, red arrow = decline, neutral = no change.
    """
    kpis = []
    for m in metrics:
        curr = float(current_row.get(m) or 0)
        prev = float(prev_row.get(m) or 0)
        delta = curr - prev
        label = m.split(",")[0].split(" per")[0].strip()

        if delta > 0.05:
            icon = "bi-arrow-up-circle-fill"
            color = HKFATheme.POSITIVE
            delta_txt = f"+{delta:.1f}"
        elif delta < -0.05:
            icon = "bi-arrow-down-circle-fill"
            color = HKFATheme.NEGATIVE
            delta_txt = f"{delta:.1f}"
        else:
            icon = "bi-dash-circle"
            color = HKFATheme.TEXT_SECONDARY
            delta_txt = "—"

        kpis.append(
            html.Div(
                [
                    html.Div(
                        f"{curr:.1f}",
                        style={
                            "fontSize": "1.1rem",
                            "fontWeight": "700",
                            "color": HKFATheme.TEXT_PRIMARY,
                            "lineHeight": "1",
                        },
                    ),
                    html.Div(
                        [
                            html.I(className=f"bi {icon} me-1", style={"fontSize": "0.7rem", "color": color}),
                            html.Span(delta_txt, style={"fontSize": "0.7rem", "color": color}),
                        ],
                        style={"lineHeight": "1", "marginTop": "2px"},
                    ),
                    html.Div(
                        label,
                        style={
                            "fontSize": "0.65rem",
                            "color": HKFATheme.TEXT_SECONDARY,
                            "marginTop": "4px",
                            "textTransform": "uppercase",
                            "letterSpacing": "0.04em",
                        },
                    ),
                ],
                style={
                    "textAlign": "center",
                    "padding": "8px 12px",
                    "background": "rgba(255,255,255,0.04)",
                    "borderRadius": "8px",
                    "border": f"1px solid {HKFATheme.BORDER_COLOR}",
                    "minWidth": "70px",
                },
            )
        )

    return html.Div(
        kpis,
        style={
            "display": "flex",
            "gap": "8px",
            "flexWrap": "wrap",
            "marginBottom": "12px",
        },
    )


def render_post_match(payload: Dict[str, Any]) -> html.Div:
    """
    Renders the Post-Match analysis stage.
    Shows a match header, Radar Chart, and Percentile bars for the player's season stats.
    """
    opponent = payload.get("opponent", "Opponent")
    date_str = payload.get("kickoff_display") or str(payload.get("date", ""))[:10]
    home = payload.get("home_team", "")
    away = payload.get("away_team", "")
    player_stats = payload.get("player_stats") or {}

    # ── Match header card ──────────────────────────────────────────────────
    match_label = f"{home} vs {away}" if home and away else f"vs {opponent}"
    header = dbc.Card([
        dbc.CardBody([
            dbc.Row([
                dbc.Col(html.Div([
                    html.Span(match_label, className="fw-bold fs-5"),
                ]), width="auto"),
                dbc.Col(html.Small(date_str, className="text-muted"), width="auto", className="ms-auto"),
            ], align="center"),
        ])
    ], className="mb-3 border-0 shadow-sm")

    # ── Performance stats from data manager ───────────────────────────────
    perf = player_stats.get("performance_stats", {})
    percentiles = player_stats.get("percentiles", {})
    basic = player_stats.get("basic_info", {})
    player_name = basic.get("name", "Player")
    position = basic.get("position_primary", basic.get("position", ""))

    # Radar: use available numeric stats normalized 0-100 via percentiles
    radar_metrics = ["Goals", "Assists", "Accurate passes, %", "Minutes played"]
    radar_values = [percentiles.get(m, 50) for m in radar_metrics]
    radar_labels = ["Goals", "Assists", "Pass Accuracy", "Minutes"]

    from utils.chart_helpers import create_radar_chart
    radar_fig = glass_figure_layout(create_radar_chart(
        values=radar_values,
        metrics=radar_labels,
        title=f"{player_name} — Season Percentiles",
        name=player_name,
    ))

    from utils.chart_helpers import create_percentile_bars
    percentile_display = {
        "Goals": percentiles.get("Goals", 0),
        "Assists": percentiles.get("Assists", 0),
        "Pass %": percentiles.get("Accurate passes, %", 0),
        "Minutes": percentiles.get("Minutes played", 0),
    }

    # ── Rating-based glass modifier ─────────────────────────────────────────
    rating = payload.get("rating") or player_stats.get("performance_stats", {}).get("rating")
    try:
        rating = float(rating) if rating is not None else None
    except (ValueError, TypeError):
        rating = None
    glass_modifier = "glass-danger" if (rating is not None and rating < 6.0) else "glass-success"

    # ── KPI icons with animate-glass-pulse (task 6.4) ─────────────────────
    kpi_icon = html.I(className="bi bi-person-fill me-1 animate-glass-pulse")

    # ── Performance badge: how does this match rank vs player's season? ────
    performance_badge = None
    vs_avg_row = None
    try:
        dm = get_hong_kong_data_manager()
        df = dm.processed_data
        if df is not None and player_name in df["Player"].values:
            p_row = df[df["Player"] == player_name].iloc[0]
            matches = float(p_row.get("Matches played") or 1) or 1
            season_goals = float(p_row.get("Goals") or 0)
            season_assists = float(p_row.get("Assists") or 0)
            avg_goals = season_goals / matches
            avg_assists = season_assists / matches

            match_goals = float(payload.get("goals") or 0)
            match_assists = float(payload.get("assists") or 0)

            # Determine performance badge from rating vs player's historical context
            badge_text = None
            badge_color = HKFATheme.ACCENT_GOLD
            if rating is not None:
                if rating >= 8.5:
                    badge_text, badge_color = "Outstanding Performance", HKFATheme.ACCENT_GOLD
                elif rating >= 7.5:
                    badge_text, badge_color = "Strong Performance", HKFATheme.POSITIVE
                elif rating >= 7.0:
                    badge_text, badge_color = "Solid Performance", HKFATheme.ACCENT_BLUE
                elif rating < 6.0:
                    badge_text, badge_color = "Difficult Game", HKFATheme.NEGATIVE

            if badge_text:
                performance_badge = html.Div(
                    [
                        html.I(className="bi bi-star-fill me-1", style={"fontSize": "0.75rem"}),
                        html.Span(badge_text, style={"fontSize": "0.8rem", "fontWeight": "600"}),
                    ],
                    style={
                        "display": "inline-flex",
                        "alignItems": "center",
                        "padding": "4px 10px",
                        "borderRadius": "20px",
                        "background": f"rgba({_hex_to_rgb(badge_color)}, 0.15)",
                        "border": f"1px solid {badge_color}",
                        "color": badge_color,
                        "marginBottom": "10px",
                    },
                )

            # vs season average row
            def _fmt_cmp(match_val: float, avg_val: float, label: str) -> html.Span:
                """Helper for match value vs season average display."""
                delta = match_val - avg_val
                if delta > 0.05:
                    clr = HKFATheme.POSITIVE
                    arr = "↑"
                elif delta < -0.05:
                    clr = HKFATheme.NEGATIVE
                    arr = "↓"
                else:
                    clr = HKFATheme.TEXT_SECONDARY
                    arr = "→"
                return html.Span(
                    [
                        html.Span(f"{label}: ", style={"color": HKFATheme.TEXT_SECONDARY, "fontSize": "0.8rem"}),
                        html.Span(f"{match_val:.0f}", style={"color": HKFATheme.TEXT_PRIMARY, "fontWeight": "600", "fontSize": "0.8rem"}),
                        html.Span(f" {arr} avg {avg_val:.1f}", style={"color": clr, "fontSize": "0.75rem"}),
                    ],
                    className="me-3",
                )

            vs_avg_row = html.Div(
                [
                    html.Small(
                        [
                            html.I(className="bi bi-bar-chart-line me-1", style={"color": HKFATheme.ACCENT_BLUE}),
                            html.Span("vs your season avg: ", style={"color": HKFATheme.TEXT_SECONDARY}),
                        ],
                        className="me-2",
                    ),
                    _fmt_cmp(match_goals, avg_goals, "Goals"),
                    _fmt_cmp(match_assists, avg_assists, "Assists"),
                ],
                className="mb-3",
                style={"display": "flex", "flexWrap": "wrap", "alignItems": "center"},
            )
    except Exception as e:
        logger.debug(f"render_post_match enrichment error: {e}")

    # ── Layout ─────────────────────────────────────────────────────────────
    return html.Div(
        html.Div([
            header,
            html.P([
                kpi_icon,
                html.Span(f"{player_name}", className="fw-semibold me-2"),
                html.Small(position, className="text-muted badge bg-secondary"),
            ], className="mb-2"),
            performance_badge,
            vs_avg_row,
            dbc.Row([
                dbc.Col([
                    html.H6("Performance Radar", className="text-muted mb-2"),
                    dcc.Graph(figure=radar_fig, config={"displayModeBar": False}, className="w-100"),
                ], width=12, md=7),
                dbc.Col([
                    html.H6("Percentiles", className="text-muted mb-3"),
                    create_percentile_bars(percentile_display),
                ], width=12, md=5),
            ]),
        ]),
        className=f"glass-card {glass_modifier}",
    )


# Positions that face each other in direct duels
_RIVAL_POSITION_MAP: Dict[str, List[str]] = {
    "Forward":    ["Defender"],
    "Winger":     ["Defender", "Midfielder"],
    "Midfielder": ["Midfielder"],
    "Defender":   ["Forward", "Winger"],
    "Goalkeeper": [],
}

_RIVAL_SUBPOSITION_MAP: Dict[str, List[str]] = {
    "RW": ["LB", "LWB", "LB5", "LM"],
    "RWF": ["LB", "LWB", "LB5", "LM"],
    "RM": ["LB", "LWB", "LB5", "LM"],
    "LW": ["RB", "RWB", "RB5", "RM"],
    "LWF": ["RB", "RWB", "RB5", "RM"],
    "LM": ["RB", "RWB", "RB5", "RM"],
    "ST": ["CB", "LCB", "RCB", "CB3", "LCB3", "RCB3"],
    "CF": ["CB", "LCB", "RCB", "CB3", "LCB3", "RCB3"],
}


def _split_position_tokens(value: Any) -> List[str]:
    raw = str(value or "").upper()
    if not raw or raw in {"UNKNOWN", "NAN"}:
        return []
    return [part.strip() for part in raw.split(",") if part.strip()]


def _parse_match_outcome(result_str: str, opponent_label: str, player_team: str) -> str:
    score = str(result_str or "").strip().lower()
    if not score or ":" not in score:
        return "EMPTY"
    penalties = "pen" in score
    score_part = score.replace("pen.", "").replace("pen", "").strip()
    try:
        left, right = [int(x) for x in score_part.split(":", 1)]
    except Exception:
        return "EMPTY"

    parts = str(opponent_label or "").split(" vs ")
    if len(parts) != 2:
        return "EMPTY"
    home_team, away_team = parts[0].strip(), parts[1].strip()
    player_team = str(player_team or "").strip().lower()
    is_home = player_team and player_team in home_team.lower()
    is_away = player_team and player_team in away_team.lower()
    if not is_home and not is_away:
        return "EMPTY"
    player_score = left if is_home else right
    rival_score = right if is_home else left
    if player_score > rival_score:
        return "W"
    if player_score < rival_score:
        return "L"
    if penalties:
        return "W" if player_score > rival_score else "L"
    return "D"


def _extract_numeric_metric(raw_data: Any, *keys: str) -> float:
    """Best-effort numeric extraction from MatchHistory.raw_data."""
    if not isinstance(raw_data, dict):
        return 0.0
    lower_map = {str(k).strip().lower(): v for k, v in raw_data.items()}
    for key in keys:
        value = lower_map.get(str(key).strip().lower())
        if value in (None, "", "None"):
            continue
        try:
            return float(str(value).replace(",", "."))
        except Exception:
            continue
    return 0.0


def _extract_score_text(result_str: Any) -> str:
    raw = str(result_str or "").strip()
    if not raw:
        return "—"
    if ":" in raw:
        cleaned = raw.replace("pen.", "").replace("pen", "").strip()
        parts = cleaned.split()
        for part in reversed(parts):
            if ":" in part:
                return part
        return cleaned
    if len(raw) > 2 and raw[1] == " ":
        return raw[2:].strip()
    return raw


def _extract_outcome_from_result(result_str: Any, opponent_label: str = "", player_team: str = "") -> str:
    raw = str(result_str or "").strip()
    if not raw:
        return "EMPTY"
    first = raw[:1].upper()
    if first in {"W", "D", "L"}:
        return first
    return _parse_match_outcome(raw, opponent_label, player_team)


def _get_recent_form_summary(player_id: str, limit: int = 5) -> Dict[str, Any]:
    """
    Returns recent form for the logged-in player.
    Includes result chips, aggregated output totals, and per-90 stats.
    """
    summary = {
        "results": [],
        "goals_total": 0,
        "assists_total": 0,
        "minutes_total": 0,
        "xg_total": 0.0,
        "xa_total": 0.0,
        "goals_per90": 0.0,
        "assists_per90": 0.0,
        "xg_per90": 0.0,
        "xa_per90": 0.0,
    }
    if not player_id:
        return summary
    try:
        from models.db_models import MatchHistory, Player
        from utils.db_engine import SessionFactory

        with SessionFactory() as session:
            player = session.get(Player, player_id)
            player_team = ""
            if player is not None:
                try:
                    player_team = str(player.current_team.name or "").strip()
                except Exception:
                    player_team = ""
            matches = (
                session.query(MatchHistory)
                .filter(MatchHistory.player_id == player_id)
                .order_by(MatchHistory.date.desc())
                .limit(limit)
                .all()
            )
            matches = sorted(
                matches,
                key=lambda match: getattr(match, "date", None) or pd.Timestamp.min,
                reverse=True,
            )
    except Exception as exc:
        logger.debug(f"_get_recent_form_summary error: {exc}")
        return summary

    for match in matches:
        raw_result = getattr(match, "result", "") or ""
        outcome = _extract_outcome_from_result(raw_result, getattr(match, "opponent", ""), player_team)
        penalties = "pen" in str(raw_result).lower()
        summary["results"].append({
            "outcome": outcome,
            "score": _extract_score_text(raw_result),
            "penalties": penalties,
        })
        summary["goals_total"] += int(getattr(match, "goals", 0) or 0)
        summary["assists_total"] += int(getattr(match, "assists", 0) or 0)
        summary["minutes_total"] += int(getattr(match, "minutes_played", 0) or 0)
        raw_data = getattr(match, "raw_data", None)
        summary["xg_total"] += _extract_numeric_metric(raw_data, "xg", "xG", "expected goals")
        summary["xa_total"] += _extract_numeric_metric(raw_data, "xa", "xA", "expected assists")

    minutes = summary["minutes_total"]
    if minutes > 0:
        factor = 90.0 / minutes
        summary["goals_per90"] = summary["goals_total"] * factor
        summary["assists_per90"] = summary["assists_total"] * factor
        summary["xg_per90"] = summary["xg_total"] * factor
        summary["xa_per90"] = summary["xa_total"] * factor

    return summary


def _coerce_cutoff_datetime(payload: Dict[str, Any]) -> Optional[pd.Timestamp]:
    for key in ("kickoff_utc", "kickoff_hkt", "date_utc", "date"):
        value = payload.get(key)
        if not value:
            continue
        try:
            ts = pd.to_datetime(value)
            if pd.isna(ts):
                continue
            if getattr(ts, "tzinfo", None) is not None:
                return ts.tz_convert(None)
            return ts
        except Exception:
            continue
    return None


def _get_head_to_head_summary(player_id: str, opponent_team: str, limit: int = 3) -> List[Dict[str, Any]]:
    """Returns the player's last matches against the current opponent."""
    if not player_id or not opponent_team:
        return []
    try:
        from models.db_models import MatchHistory, Player
        from utils.db_engine import SessionFactory

        with SessionFactory() as session:
            player = session.get(Player, player_id)
            player_team = ""
            if player is not None:
                try:
                    player_team = str(player.current_team.name or "").strip()
                except Exception:
                    player_team = ""

            matches = (
                session.query(MatchHistory)
                .filter(MatchHistory.player_id == player_id)
                .order_by(MatchHistory.date.desc())
                .all()
            )
    except Exception as exc:
        logger.debug(f"_get_head_to_head_summary error: {exc}")
        return []

    opponent_norm = opponent_team.lower().strip()
    results: List[Dict[str, Any]] = []
    for match in matches:
        opponent_label = str(getattr(match, "opponent", "") or "")
        if opponent_norm not in opponent_label.lower():
            continue
        raw_result = getattr(match, "result", "") or ""
        results.append({
            "outcome": _extract_outcome_from_result(raw_result, opponent_label, player_team),
            "score": _extract_score_text(raw_result),
            "goals": int(getattr(match, "goals", 0) or 0),
            "assists": int(getattr(match, "assists", 0) or 0),
            "penalties": "pen" in str(raw_result).lower(),
        })
        if len(results) >= limit:
            break
    return results


def _get_rival_recent_form(player_name: str, team_name: str, limit: int = 5) -> Dict[str, Any]:
    """
    Returns a lightweight recent-form snapshot for a rival player.
    Based on minutes, team results, goals, assists and cards in the last 5 matches.
    """
    default = {
        "label": "Stable",
        "minutes": 0,
        "team_points": 0,
        "goals": 0,
        "assists": 0,
        "yellow_cards": 0,
        "red_cards": 0,
    }
    try:
        from models.db_models import MatchHistory, Player
        from utils.db_engine import SessionFactory
        from utils.player_index import get_player_index

        player_id = get_player_index().get_player_id(player_name, team_name=team_name)
        if not player_id:
            return default

        with SessionFactory() as session:
            player = session.get(Player, player_id)
            player_team = ""
            if player is not None:
                try:
                    player_team = str(player.current_team.name or "").strip()
                except Exception:
                    player_team = ""
            matches = (
                session.query(MatchHistory)
                .filter(MatchHistory.player_id == player_id)
                .order_by(MatchHistory.date.desc())
                .limit(limit)
                .all()
            )
    except Exception as exc:
        logger.debug(f"_get_rival_recent_form error: {exc}")
        return default

    if not matches:
        return default

    minutes = 0
    team_points = 0
    goals = 0
    assists = 0
    yellow_cards = 0
    red_cards = 0
    for match in matches:
        minutes += int(getattr(match, "minutes_played", 0) or 0)
        goals += int(getattr(match, "goals", 0) or 0)
        assists += int(getattr(match, "assists", 0) or 0)
        yellow_cards += int(getattr(match, "yellow_cards", 0) or 0)
        red_cards += int(getattr(match, "red_cards", 0) or 0)
        outcome = _extract_outcome_from_result(
            getattr(match, "result", ""),
            getattr(match, "opponent", ""),
            player_team,
        )
        if outcome == "W":
            team_points += 3
        elif outcome == "D":
            team_points += 1

    involvement = goals + assists
    if minutes >= 300 and (involvement >= 2 or team_points >= 10):
        label = "In Form"
    elif minutes < 90 or (team_points <= 2 and involvement == 0):
        label = "Out of Form"
    else:
        label = "Stable"

    return {
        "label": label,
        "minutes": minutes,
        "team_points": team_points,
        "goals": goals,
        "assists": assists,
        "yellow_cards": yellow_cards,
        "red_cards": red_cards,
    }


def _get_rival_current_role(player_name: str, team_name: str, fallback_tokens: Optional[List[str]] = None) -> List[str]:
    """
    Resolve a rival's current role from recent match history first, then canonical position.
    Returns one or more normalized position tokens.
    """
    fallback_tokens = [token for token in (fallback_tokens or []) if token]
    try:
        from models.db_models import MatchHistory, Player
        from utils.db_engine import SessionFactory
        from utils.player_index import get_player_index

        player_id = get_player_index().get_player_id(player_name, team_name=team_name)
        if not player_id:
            return fallback_tokens

        with SessionFactory() as session:
            player = session.get(Player, player_id)
            recent_matches = (
                session.query(MatchHistory)
                .filter(MatchHistory.player_id == player_id)
                .order_by(MatchHistory.date.desc())
                .limit(6)
                .all()
            )
            weighted: Dict[str, int] = {}
            for idx, match in enumerate(recent_matches):
                code = _normalize_position_code(getattr(match, "position", None))
                if not code:
                    continue
                minutes = int(getattr(match, "minutes_played", 0) or 0)
                weight = max(minutes, 1) + max(0, 6 - idx)
                weighted[code] = weighted.get(code, 0) + weight

            if weighted:
                ordered = sorted(weighted.items(), key=lambda item: item[1], reverse=True)
                return [token for token, _ in ordered]

            canonical_tokens = _split_position_tokens(getattr(player, "position_main", "") if player else "")
            if canonical_tokens:
                return canonical_tokens
    except Exception as exc:
        logger.debug(f"_get_rival_current_role error: {exc}")

    return fallback_tokens


def _get_opponent_rivals(
    opponent_team: str,
    player_pos_group: str,
    player_position_main: str = "",
    dm=None,
) -> List[Dict]:
    """Returns enriched rival scouting cards for the opponent team."""
    try:
        if dm is None:
            return []
        df = dm.processed_data
        if df is None or df.empty:
            return []

        rival_pos_groups = _RIVAL_POSITION_MAP.get(player_pos_group, [])
        preferred_tokens = _RIVAL_SUBPOSITION_MAP.get(str(player_position_main or "").upper(), [])
        if not rival_pos_groups:
            return []

        team_df = df[df["Team"].str.lower() == opponent_team.lower()] if "Team" in df.columns else pd.DataFrame()
        if team_df.empty:
            # Try partial match
            team_df = df[df["Team"].str.lower().str.contains(opponent_team.lower(), na=False)] if "Team" in df.columns else pd.DataFrame()

        if team_df.empty:
            return []

        def _row_tokens(row: pd.Series) -> List[str]:
            for column in ("Position_Confirmed", "Position_Clean", "Primary position", "Position", "position_main"):
                if column in row.index:
                    tokens = _split_position_tokens(row.get(column))
                    if tokens:
                        return tokens
            return []

        def _candidate_tokens(row: pd.Series) -> List[str]:
            row_tokens = _row_tokens(row)
            resolved_tokens = _get_rival_current_role(
                str(row.get("Player", "Unknown")),
                opponent_team,
                fallback_tokens=row_tokens,
            )
            return resolved_tokens or row_tokens

        if preferred_tokens:
            rival_df = team_df[
                team_df.apply(
                    lambda row: bool(set(_candidate_tokens(row)) & set(preferred_tokens)),
                    axis=1,
                )
            ]
        elif "Position_Group" in team_df.columns:
            rival_df = team_df[team_df["Position_Group"].isin(rival_pos_groups)]
        else:
            rival_df = team_df

        if rival_df.empty:
            rival_df = team_df

        def _display_role(row: pd.Series) -> str:
            tokens = _row_tokens(row)
            if not tokens:
                return str(row.get("Position_Group", "Unknown"))
            token = tokens[0]
            return POSITION_FULL_NAMES.get(token, token.replace("_", " ").title())

        def _metric_value(row: pd.Series, columns: List[str]) -> tuple[str, float]:
            for column in columns:
                if column in row.index:
                    try:
                        return column, float(row.get(column) or 0)
                    except Exception:
                        continue
            return columns[0], 0.0

        def _normalize_metric_label(label: str) -> str:
            return label.replace(" per 90", " /90").replace(", %", "%").strip()

        def _strength_and_weakness(pos_group: str, key_label: str, sec_label: str, key_val: float, sec_val: float) -> tuple[str, str]:
            if pos_group == "Defender":
                strength = "Strong in defensive duels" if "duels" in key_label.lower() else "Reliable defensive profile"
                weakness = "Can be exposed when forced to turn" if sec_val < 5 else "Can leave space behind on recovery"
            elif pos_group == "Midfielder":
                strength = "Helps control possession under pressure"
                weakness = "Can be rushed when play accelerates"
            elif pos_group in {"Forward", "Winger"}:
                strength = "Dangerous attacking outlet in transition"
                weakness = "Offers limited defensive cover"
            else:
                strength = f"Stands out in {key_label.lower()}"
                weakness = f"Less reliable in {sec_label.lower()}"
            return strength, weakness

        physical_candidates = [
            "Sprinting Distance per 90 (+25 km/h)",
            "Count Sprint per 90 (+25 km/h)",
            "HSR Distance per 90 (20-25 km/h)",
            "Count HSR per 90 (20-25 km/h)",
        ]

        primary_metrics = {
            "Defender": (["Defensive duels won, %", "Defensive duels per 90"], ["Interceptions per 90", "Aerial duels won, %"]),
            "Midfielder": (["Accurate passes, %", "Key passes per 90"], ["Interceptions per 90", "Progressive passes per 90"]),
            "Forward": (["Goals", "xG"], ["Shots per 90", "xG per 90"]),
            "Winger": (["Successful dribbles, %", "Dribbles per 90", "Goals"], ["Key passes per 90", "xA per 90"]),
        }
        sort_group = rival_pos_groups[0] if rival_pos_groups else "Midfielder"
        prim_cols, sec_cols = primary_metrics.get(sort_group, (["Goals"], ["Assists"]))

        for _, row in rival_df.iterrows():
            tokens = _candidate_tokens(row)
            if not tokens:
                continue

        def _score_row(row: pd.Series) -> float:
            tokens = _candidate_tokens(row)
            if not tokens:
                return -1.0
            tactical_bonus = 18.0 if preferred_tokens and set(tokens) & set(preferred_tokens) else 0.0
            _, key_val = _metric_value(row, prim_cols)
            _, sec_val = _metric_value(row, sec_cols)
            minutes = float(row.get("Minutes played", 0) or 0)
            return tactical_bonus + key_val + (sec_val * 0.35) + (minutes / 300.0)

        rival_df = rival_df.assign(_rival_score=rival_df.apply(_score_row, axis=1))
        rival_df = rival_df[rival_df["_rival_score"] >= 0].sort_values("_rival_score", ascending=False)

        results = []
        for idx, (_, row) in enumerate(rival_df.head(3).iterrows()):
            tokens = _candidate_tokens(row)
            if not tokens:
                continue
            role_token = tokens[0]
            key_label, key_val = _metric_value(row, prim_cols)
            sec_label, sec_val = _metric_value(row, sec_cols)
            physical_label, physical_val = _metric_value(row, physical_candidates)
            strength_text, weakness_text = _strength_and_weakness(
                str(row.get("Position_Group", sort_group)),
                key_label,
                sec_label,
                key_val,
                sec_val,
            )
            recent_form = _get_rival_recent_form(
                str(row.get("Player", "Unknown")),
                opponent_team,
            )
            form_label = recent_form.get("label", "Stable")
            results.append({
                "name": str(row.get("Player", "Unknown")),
                "position_group": role_token,
                "role_label": POSITION_FULL_NAMES.get(role_token, _display_role(row)),
                "matchup_tier": "Primary Matchup" if idx == 0 else "Support Matchup",
                "form_label": form_label,
                "recent_minutes": int(recent_form.get("minutes", 0) or 0),
                "recent_goals": int(recent_form.get("goals", 0) or 0),
                "recent_assists": int(recent_form.get("assists", 0) or 0),
                "recent_yellow_cards": int(recent_form.get("yellow_cards", 0) or 0),
                "recent_red_cards": int(recent_form.get("red_cards", 0) or 0),
                "strength_text": strength_text,
                "weakness_text": weakness_text,
                "key_label": _normalize_metric_label(key_label),
                "key_val": float(key_val or 0),
                "sec_label": _normalize_metric_label(sec_label),
                "sec_val": float(sec_val or 0),
                "physical_label": _normalize_metric_label(physical_label),
                "physical_val": float(physical_val or 0),
            })
        return results
    except Exception as e:
        logger.debug(f"_get_opponent_rivals error: {e}")
        return []


# ──────────────────────────────────────────────────────────────────────────────
# PLAYER DASHBOARD — Estado A (no card open)
# ──────────────────────────────────────────────────────────────────────────────

def _fetch_dashboard_data(player_name: str, player_id: str) -> Dict:
    """
    Centralized DB fetch for the player dashboard (Estado A).
    Opens SQLAlchemy session(s), loads all data required by the 6 dashboard builders,
    and returns a single dict. This is the sole DB entry point for the dashboard.
    """
    from sqlalchemy import select
    from models.db_models import Player, PlayerPhoto, PlayerSeasonStat, MatchHistory
    from utils.db_engine import SessionFactory

    current_season = _get_current_season()
    result: Dict = {
        "player_name": player_name,
        "player_id": player_id,
        "current_season": current_season,
        "position_main": None,
        "pos_group": None,
        "team_name": None,
        "archetype": None,
        "age": None,
        "foot": None,
        "height": None,
        "cutout_path": None,
        "matches_played": 0,
        "goals": 0,
        "assists": 0,
        "minutes_played": 0,
        "last5_results": [],
        "percentiles_data": {},
        "history_df": pd.DataFrame(),
    }

    session = SessionFactory()
    try:
        # ── Player + photo + team ──────────────────────────────────────────
        # Query by primary key first (reliable), fall back to name match
        player_obj = session.get(Player, player_id) if player_id else None
        if player_obj is None and player_name:
            player_obj = session.execute(
                select(Player).where(Player.name == player_name)
            ).scalars().first()
        if player_obj:
            result["position_main"] = player_obj.position_main
            result["age"]           = player_obj.age
            result["foot"]          = player_obj.foot
            result["height"]        = player_obj.height
            if player_obj.current_team:
                result["team_name"] = player_obj.current_team.name

            # Primary photo: blob > cutout_path > original_path
            primary_photo = next(
                (p for p in player_obj.photos if getattr(p, "is_primary", False)),
                player_obj.photos[0] if player_obj.photos else None,
            )
            if primary_photo:
                if primary_photo.photo_data:
                    import base64
                    b64 = base64.b64encode(primary_photo.photo_data).decode("utf-8")
                    result["cutout_path"] = f"data:image/jpeg;base64,{b64}"
                else:
                    raw_path = primary_photo.cutout_path or primary_photo.original_path
                    if raw_path:
                        web_path = "/" + raw_path if not raw_path.startswith("/") else raw_path
                        result["cutout_path"] = web_path

        # ── Career-wide totals and latest active season ───────────────────
        stmt_career = (
            select(PlayerSeasonStat)
            .where(PlayerSeasonStat.player_id == player_id)
            .order_by(PlayerSeasonStat.season_id.desc())
        )
        all_seasons_stats = session.execute(stmt_career).scalars().all()
        
        latest_active_season = current_season
        if all_seasons_stats:
            latest_active_season = all_seasons_stats[0].season_id
            result["matches_played"] = sum(s.matches_played or 0 for s in all_seasons_stats)
            result["goals"]          = sum(s.goals or 0 for s in all_seasons_stats)
            result["assists"]        = sum(s.assists or 0 for s in all_seasons_stats)
            result["minutes_played"] = sum(s.minutes_played or 0 for s in all_seasons_stats)

        # ── Last 5 match results ───────────────────────────────────────────
        stmt_mh = (
            select(MatchHistory)
            .where(MatchHistory.player_id == player_id)
            .order_by(MatchHistory.date.desc())
            .limit(5)
        )
        matches = session.execute(stmt_mh).scalars().all()
        
        # ── Process match outcomes (W/D/L) ─────────────────────────────────
        last5_data = []
        player_team = result.get("team_name")
        import re
        
        for m in reversed(matches):
            res_str = m.result or ""
            if not res_str: continue
            
            outcome = "EMPTY"
            score_display = res_str
            
            # 1. Check if it's already a code (W/D/L)
            if res_str.upper() in ["W", "D", "L"]:
                outcome = res_str.upper()
                score_display = outcome
            
            # 2. Try to derive from score "2:1" and opponent "Home vs Away"
            elif ":" in res_str and player_team:
                try:
                    score_part = res_str.split()[0]
                    h_score, a_score = map(int, score_part.split(":"))
                    opp = m.opponent or ""
                    parts = opp.split(" vs ")
                    if len(parts) == 2:
                        h_team_raw, a_team_raw = parts
                        h_team = re.sub(r'\(\d+\.\)', '', h_team_raw).strip()
                        a_team = re.sub(r'\(\d+\.\)', '', a_team_raw).strip()
                        
                        is_home = player_team.lower() in h_team.lower()
                        is_away = player_team.lower() in a_team.lower()
                        
                        if is_home:
                            if h_score > a_score: outcome = "W"
                            elif h_score < a_score: outcome = "L"
                            else: outcome = "D"
                        elif is_away:
                            if a_score > h_score: outcome = "W"
                            elif a_score < h_score: outcome = "L"
                            else: outcome = "D"
                except:
                    pass
            
            last5_data.append({"outcome": outcome, "score": score_display})
                
        result["last5_results"] = last5_data

    except Exception as e:
        logger.warning(f"_fetch_dashboard_data DB error for '{player_name}': {e}")
    finally:
        session.close()

    # ── Position group + archetype (uses DM, no extra session) ────────────
    try:
        dm = get_hong_kong_data_manager()
        result["pos_group"] = _get_position_group(player_name, dm)
        result["archetype"] = _get_archetype_label(player_name, result["pos_group"], dm)

        # ── Percentiles via PercentileRankingSystem ────────────────────────
        try:
            # Determine cohort season: current OR player's last active season
            cohort_season = current_season
            if dm.processed_data is not None:
                if player_name not in dm.processed_data["Player"].values:
                    # Player not in current season, use their latest recorded season as comparison group
                    cohort_season = latest_active_season
            
            # If cohort is different from loaded, use a temporary system
            if cohort_season != dm.current_season:
                from utils.efficiency_metrics import PercentileRankingSystem
                historical_df = dm._load_season_dataframe(cohort_season)
                historical_df = dm.processor.process_season_data(historical_df, cohort_season)
                ranker = PercentileRankingSystem(historical_df)
            else:
                ranker = dm.aggregator.percentile_system

            if ranker:
                raw = ranker.get_player_percentiles(player_name, by_position=True)
                # Pass full metric objects (including benchmarks) to support UI markers
                result["percentiles_data"] = raw.get("metrics", {})
        except Exception as e:
            logger.debug(f"_fetch_dashboard_data percentile error: {e}")

    except Exception as e:
        logger.warning(f"_fetch_dashboard_data DM error: {e}")

    # ── Cluster data from K-Means registry ────────────────────────────────
    result["cluster_id"]       = None
    result["cluster_label"]    = None
    result["cluster_size_pct"] = None
    result["cluster_centroid"] = None
    result["player_scaled_vec"] = None
    try:
        from ai_models.model_registry import ModelRegistry
        from ai_models.clustering import label_archetypes, apply_quality_filters
        from sklearn.preprocessing import StandardScaler
        from data.processors.ml_preprocessor import MLPreprocessor

        dm_c = get_hong_kong_data_manager()
        df_c = dm_c.processed_data
        if df_c is not None and not df_c.empty:
            # ── CAREER-WIDE PROFILE AGGREGATION ───────────────────────────
            # Instead of just the latest season, we build a career aggregate
            # to avoid noise in short leagues.
            from models.db_models import Player, PlayerSeasonStat
            from utils.db_engine import SessionFactory
            from sqlalchemy import select
            
            db_session = SessionFactory()
            career_metrics = {}
            total_minutes = 0
            
            try:
                stmt = (
                    select(PlayerSeasonStat)
                    .join(Player, PlayerSeasonStat.player_id == Player.id)
                    .where(Player.name.contains(player_name))
                )
                all_seasons = db_session.execute(stmt).scalars().all()
                
                if all_seasons:
                    # Minutes-weighted average of all advanced stats
                    # This provides a stable playstyle profile regardless of one good/bad season
                    for stat in all_seasons:
                        mins = stat.minutes_played or 0
                        if mins <= 0 or not stat.advanced_stats: continue
                        
                        total_minutes += mins
                        for k, v in stat.advanced_stats.items():
                            if isinstance(v, (int, float)):
                                career_metrics[k] = career_metrics.get(k, 0) + (v * mins)
                    
                    if total_minutes > 0:
                        for k in career_metrics:
                            career_metrics[k] /= total_minutes
                        
                        # Inject this stable career profile row
                        career_row = career_metrics.copy()
                        career_row["Player"] = player_name
                        career_row["Season"] = "Career"
                        career_row["Minutes played"] = total_minutes
                        # Ensure meta columns exist for preprocessor
                        career_row["Team"] = result.get("team_name") or "Historical"
                        career_row["Position"] = result.get("position_main") or "Unknown"
                        
                        df_c = pd.concat([df_c, pd.DataFrame([career_row])], ignore_index=True)
                        real_player_name = player_name
                    else:
                        # Fallback to latest season if aggregation fails
                        p_match = df_c[df_c["Player"].str.contains(player_name, case=False, na=False)]
                        if not p_match.empty:
                            real_player_name = p_match.iloc[0]["Player"]
                        else:
                            real_player_name = None
                else:
                    real_player_name = None
            except Exception as e:
                logger.warning(f"Career aggregation failed for {player_name}: {e}")
                real_player_name = None
            finally:
                db_session.close()

            if real_player_name:
                # Apply same feature engineering as training
                meta_cols_c = {"Player", "Season", "Team", "Position"}
                pp = MLPreprocessor()
                numeric_cols_raw = [c for c in df_c.columns if c not in meta_cols_c and pd.api.types.is_numeric_dtype(df_c[c])]
                df_c = pp.compute_temporal_features(df_c, numeric_cols_raw)
                df_c = pp.compute_positional_zscores(df_c, numeric_cols_raw)
                df_c = pp.compute_benchmark_deltas(df_c, numeric_cols_raw)
                df_c = pp.inject_composite_metrics(df_c)

                km = ModelRegistry().load("kmeans_overall_k5")
                if km is not None:
                    # LOAD metadata to sync features
                    registry = ModelRegistry()
                    reg_data = registry._load_registry()
                    expected_features = reg_data.get("kmeans_overall_k5", {}).get("latest", {}).get("features")
                    
                    if expected_features:
                        available_cols = [c for c in expected_features if c in df_c.columns]
                        X_input_df = df_c[available_cols].fillna(0).copy()
                        for mc in expected_features:
                            if mc not in X_input_df.columns: X_input_df[mc] = 0.0
                        X_input = X_input_df[expected_features].values
                        feature_cols_c = expected_features
                    else:
                        feature_cols_c = [c for c in df_c.columns if c not in meta_cols_c and pd.api.types.is_numeric_dtype(df_c[c])]
                        X_input = df_c[feature_cols_c].fillna(0).values
                    
                    # Transform based on current league context
                    df_train_set = apply_quality_filters(df_c, min_minutes=180, smooth_rates=True)
                    if df_train_set.empty: df_train_set = df_c
                    
                    scaler = StandardScaler()
                    scaler.fit(df_train_set[feature_cols_c].fillna(0))
                    X_all_scaled = scaler.transform(X_input)
                    
                    all_preds = km.predict(X_all_scaled)
                    
                    # Locate the "Career" row index
                    loc_idx = df_c[df_c["Player"] == real_player_name].index[-1]
                    loc = df_c.index.get_loc(loc_idx)
                    player_vector_scaled = X_all_scaled[loc : loc + 1]
                    cluster_id = int(all_preds[loc])
                    
                    archetype_labels_c = label_archetypes(km, feature_cols_c, cluster_df=df_c)
                    centroids = km.cluster_centers_
                    cluster_label = archetype_labels_c[cluster_id] if cluster_id < len(archetype_labels_c) else f"Cluster {cluster_id}"
                    
                    # ── DNA STRENGTH SELECTION ────────────────────────────────
                    # Only show traits where player is above average (Z > -0.2)
                    DERIVED_EXCLUDE = ("_roll_", "_delta_", "_benchmark", "_composite", "lag_", "roll_")
                    DISCIPLINE = {"red card", "yellow card", "foul", "conceded", "loss", "lost"}
                    PHYSICAL_ATTRS = {"height", "weight", "age", "market value", "contract"}
                    
                    ARCHETYPE_PRIORITY = {
                        "Physical": ["distance", "sprint", "hsr", "hi distance", "speed", "duel"],
                        "Defensive": ["interception", "tackle", "clearance", "block", "duel"],
                        "Distributor": ["pass", "accurate pass", "long pass", "forward pass"],
                        "Maestro": ["key pass", "smart pass", "through pass", "assist", "xa"],
                        "Finisher": ["goal", "xg", "shot", "conversion"],
                        "Winger": ["dribble", "cross", "progressive run", "acceleration"],
                    }
                    
                    priority_keywords = []
                    for kw, features in ARCHETYPE_PRIORITY.items():
                        if kw.lower() in cluster_label.lower():
                            priority_keywords.extend(features)

                    valid_idx = []
                    p_z_vec = player_vector_scaled[0]
                    
                    for i, name in enumerate(feature_cols_c):
                        name_l = name.lower()
                        if any(s in name for s in DERIVED_EXCLUDE): continue
                        if any(d in name_l for d in DISCIPLINE | PHYSICAL_ATTRS): continue
                        
                        # Use raw value from injected career row to check volume
                        raw_col = name.replace("_zscore_positional", "")
                        p_val_raw = 0.0
                        if raw_col in df_c.columns:
                            p_val_raw = float(df_c[df_c["Player"] == real_player_name].iloc[-1][raw_col] or 0)
                        
                        # Only show REAL strengths (avoid bottom percentiles)
                        if p_z_vec[i] < -0.2: continue
                        if "per 90" in name_l and p_val_raw < 0.15: continue
                        
                        valid_idx.append(i)

                    if not valid_idx:
                        valid_idx = [i for i, name in enumerate(feature_cols_c) if "_zscore_positional" in name and p_z_vec[i] >= 0]

                    # Final Identity traits selection with priority bonus
                    scores = []
                    for idx in valid_idx:
                        name_l = feature_cols_c[idx].lower()
                        score = p_z_vec[idx]
                        if any(pk in name_l for pk in priority_keywords):
                            score += 2.5 # Weight archetype-defining traits higher
                        scores.append(score)
                    
                    top5_local = np.argsort(scores)[::-1][:5]
                    final_top_idx = [valid_idx[i] for i in top5_local]
                    
                    result["cluster_id"]       = cluster_id
                    result["cluster_label"]    = cluster_label
                    result["cluster_size_pct"] = float((all_preds == cluster_id).mean() * 100)
                    result["cluster_centroid"] = {feature_cols_c[i]: float(centroids[cluster_id][i]) for i in final_top_idx}
                    result["player_scaled_vec"] = {feature_cols_c[i]: float(p_z_vec[i]) for i in final_top_idx}

    except Exception as e:
        logger.warning(f"_fetch_dashboard_data cluster error: {e}")
                
    # ── Multi-season history (separate session inside helper) ──────────────
    result["history_df"] = _fetch_player_season_history(player_name)

    # ── Similar players metadata (pre-fetched for Parallel Categories chart) ─
    # Gemini task 3.1 reads data["similar_players_meta"] to build the chart
    # without making additional DB / DM calls.
    result["similar_players_meta"] = {"similar_players": [], "query_player_embedding_idx": -1}
    try:
        from ai_models.similarity import build_embeddings, find_similar
        from ai_models.model_registry import ModelRegistry as _MReg

        _dm_s = get_hong_kong_data_manager()
        if _dm_s.processed_data is not None and not _dm_s.processed_data.empty:
            _corpus_emb = build_embeddings(_dm_s.processed_data)
            _meta_df    = _MReg().load("player_embeddings_meta")

            if _meta_df is not None:
                _name_col = "Player" if "Player" in _meta_df.columns else "player_name"
                _matches  = _meta_df.index[_meta_df[_name_col] == player_name].tolist()

                if _matches:
                    _qidx       = _matches[0]
                    _query_emb  = _corpus_emb[_qidx]
                    _sim_df     = find_similar(
                        _query_emb, _corpus_emb, _meta_df,
                        k=20, query_index=_qidx, position=None,
                    )
                    # Post-filter by position group
                    _pos_group = result.get("pos_group") or ""
                    if "Position" in _sim_df.columns and _pos_group:
                        _sim_df = _sim_df[
                            _sim_df["Position"].apply(_infer_position_group) == _pos_group
                        ]

                    _top5 = _sim_df.head(5)
                    _similar_list = []
                    for _, _row in _top5.iterrows():
                        _sname = str(_row.get(_name_col, _row.get("player_name", "")))
                        _steam = str(_row.get("Team", _row.get("team", "")))
                        _spos  = str(_row.get("Position", _row.get("position", "")))
                        _score = float(_row.get("similarity_score", 0.0))
                        _similar_list.append({
                            "name":            _sname,
                            "team_name":       _steam,
                            "team_logo_path":  _resolve_team_logo(_steam),
                            "position":        _spos,
                            "similarity_score": _score,
                        })

                    result["similar_players_meta"] = {
                        "similar_players":             _similar_list,
                        "query_player_embedding_idx":  _qidx,
                    }
    except Exception as _se:
        logger.debug(f"_fetch_dashboard_data similar players meta error: {_se}")

    # ── Hybrid AI: LSTM form trend + TabPFN transferability ───────────────
    result["form_trend"] = None
    result["transferability"] = None
    try:
        from sqlalchemy import select
        from models.db_models import MatchHistory as MH
        from utils.db_engine import SessionFactory
        from ai_models.time_series import get_form_trend
        from ai_models.predictor import get_transferability_score

        with SessionFactory() as sess:
            rows = sess.execute(
                select(MH)
                .where(MH.player_id == player_id)
                .order_by(MH.date.asc())
            ).scalars().all()
            match_records = [
                {
                    "minutes_played": r.minutes_played or 0,
                    "goals": r.goals or 0,
                    "assists": r.assists or 0,
                }
                for r in rows
            ]

        # 1. LSTM Form Trend
        lstm_metric = "goals" if result["pos_group"] in ("Forward", "Winger") else (
            "assists" if result["pos_group"] == "Midfielder" else "minutes_played"
        )
        if len(match_records) >= 5: # Lowered threshold slightly for form detection
            result["form_trend"] = get_form_trend(match_records, lstm_metric, window=5)

        # 2. TabPFN Transferability
        if not result["history_df"].empty:
            career_dict = (
                result["history_df"].drop(columns=["Season"], errors="ignore").mean().to_dict()
            )
            result["transferability"] = get_transferability_score(
                career_dict, result["pos_group"], player_id=player_id
            )

    except Exception as _hae:
        logger.debug(f"_fetch_dashboard_data hybrid ai error: {_hae}")

    return result


def _build_identity_hero(data: Dict) -> html.Div:
    """§1 Identity Hero: cutout photo, name, position, team, archetype badge, physical attrs."""
    pos_icons = {
        "Forward": "bi-lightning-charge-fill", "Winger": "bi-wind",
        "Midfielder": "bi-shuffle", "Defender": "bi-shield-fill",
        "Goalkeeper": "bi-bullseye",
    }
    pos_group     = data.get("pos_group") or ""
    position_main = data.get("position_main") or pos_group
    pos_label     = POSITION_FULL_NAMES.get(position_main.upper(), position_main) if position_main else pos_group
    archetype     = data.get("archetype") or pos_group or "Player"
    team_name     = data.get("team_name") or "—"
    season        = data.get("current_season") or "—"
    cutout_path   = data.get("cutout_path")

    age    = data.get("age")
    foot   = data.get("foot")
    height = data.get("height")

    # ── Photo ──────────────────────────────────────────────────────────────
    photo_col = html.Div(
        html.Img(
            src=cutout_path,
            style={
                "maxHeight": "120px",
                "objectFit": "contain",
                "filter": "drop-shadow(0 4px 12px rgba(0,0,0,0.4))",
                "borderRadius": "12px",
            },
        ) if cutout_path else html.Div(
            html.I(className=f"bi {pos_icons.get(pos_group, 'bi-person-fill')}",
                   style={"fontSize": "3rem", "color": HKFATheme.TEXT_SECONDARY}),
            style={"width": "80px", "height": "100px", "display": "flex",
                   "alignItems": "center", "justifyContent": "center"},
        ),
        style={"flexShrink": "0"},
    )

    # ── Archetype badge (legacy — shown only if cluster DNA section fails) ──
    arch_badge = html.Span()

    # ── Physical attrs ─────────────────────────────────────────────────────
    def _attr_chip(icon: str, label: str, value) -> html.Span:
        display = str(value) if value is not None else "–"
        return html.Span([
            html.I(className=f"bi {icon} me-1", style={"fontSize": "0.7rem"}),
            html.Span(label, style={"fontSize": "0.65rem", "color": HKFATheme.TEXT_SECONDARY}),
            html.Span(f" {display}", style={"fontSize": "0.72rem", "fontWeight": "600"}),
        ], style={"marginRight": "10px"})

    height_str = f"{height} cm" if height else None
    attrs_row = html.Div([
        _attr_chip("bi-calendar3",     "Age",    age),
        _attr_chip("bi-arrow-left-right", "Foot", foot),
        _attr_chip("bi-rulers",        "Height", height_str),
    ], style={"display": "flex", "alignItems": "center", "marginTop": "6px", "flexWrap": "wrap"})

    # ── Info column ────────────────────────────────────────────────────────
    info_col = html.Div([
        html.Div(data.get("player_name", ""), style={
            "fontSize": "1.25rem", "fontWeight": "800",
            "color": HKFATheme.TEXT_PRIMARY, "lineHeight": "1.2",
        }),
        html.Div(pos_label, style={"fontSize": "0.8rem", "color": HKFATheme.TEXT_SECONDARY, "marginTop": "2px"}),
        html.Div([
            *([html.Img(src=_resolve_team_logo(team_name),
                        style={"height": "16px", "objectFit": "contain", "marginRight": "5px", "verticalAlign": "middle"})]
              if _resolve_team_logo(team_name) else
              [html.I(className="bi bi-shield-fill me-1", style={"color": HKFATheme.ACCENT_BLUE, "fontSize": "0.72rem"})]),
            html.Span(team_name, style={"fontSize": "0.8rem", "color": HKFATheme.TEXT_SECONDARY}),
            html.Span(f"  ·  {season}", style={"fontSize": "0.72rem", "color": HKFATheme.TEXT_TERTIARY, "marginLeft": "6px"}),
        ], style={"marginTop": "4px", "display": "flex", "alignItems": "center"}),
        html.Div(arch_badge, style={"marginTop": "6px"}),
        attrs_row,
    ], style={"flex": "1", "minWidth": "0"})

    return html.Div([
        html.H6([
            html.I(className="bi bi-person-badge-fill me-2"),
            html.Span("Player Profile", className="animate-glass-draw"),
        ], className="mb-3 fw-semibold", style={"color": "var(--accent-cyan, #00d4ff)"}),
        html.Div([photo_col, info_col], style={"display": "flex", "gap": "14px", "alignItems": "flex-start"}),
    ])


def _build_season_pulse(data: Dict) -> html.Div:
    """§2 Season Pulse: KPI cards (MP/G/A/MIN), Rating placeholder."""

    def _kpi_card(icon: str, label: str, value: str) -> html.Div:
        return html.Div([
            html.I(className=f"bi {icon} d-block mb-1",
                   style={"color": HKFATheme.ACCENT_BLUE, "fontSize": "0.95rem"}),
            html.Div(value, style={"fontSize": "1.3rem", "fontWeight": "800",
                                   "color": HKFATheme.TEXT_PRIMARY, "lineHeight": "1"}),
            html.Div(label, style={"fontSize": "0.6rem", "color": HKFATheme.TEXT_SECONDARY,
                                   "textTransform": "uppercase", "letterSpacing": "0.08em", "marginTop": "4px"}),
        ], className="season-pulse-card")

    kpis_row = html.Div([
        _kpi_card("bi-calendar-check", "Matches", str(data.get("matches_played", 0))),
        _kpi_card("bi-bullseye",       "Goals",   str(data.get("goals", 0))),
        _kpi_card("bi-hand-index-thumb", "Assists", str(data.get("assists", 0))),
        _kpi_card("bi-stopwatch",      "Minutes", str(data.get("minutes_played", 0))),
        _kpi_card("bi-star-half",      "Rating",  "–"),  # TODO: implementar rating cuando esté disponible
    ], style={"display": "flex", "gap": "6px", "flexWrap": "wrap", "marginBottom": "24px"}) # Aumentado de 12px a 24px

    return html.Div([
        html.H6([
            html.I(className="bi bi-activity me-2"),
            html.Span("Season Pulse", className="animate-glass-draw"),
        ], className="mb-3 fw-semibold", style={"color": "var(--accent-cyan, #00d4ff)"}),
        kpis_row,
    ])


def _build_league_standing(data: Dict) -> html.Div:
    """§3 League Standing: positional percentile bars via PercentileRankingSystem."""
    from utils.chart_helpers import create_percentile_bars

    pos_group       = data.get("pos_group") or ""
    percentiles_all = data.get("percentiles_data") or {}

    header = html.H6([
        html.I(className="bi bi-bar-chart-line-fill me-2"),
        html.Span("League Standing", className="animate-glass-draw"),
    ], className="mb-3 fw-semibold", style={"color": "var(--accent-cyan, #00d4ff)"})

    if pos_group not in POSITION_METRICS or not percentiles_all:
        return html.Div([
            header,
            html.P("Positional data not available for this player.",
                   className="text-muted small"),
        ])

    # Base metrics for the position
    metrics = list(POSITION_METRICS[pos_group])
    
    # Add composite metric as a 5th extra bar if applicable
    if pos_group in COMPOSITE_METRICS:
        comp_m = COMPOSITE_METRICS[pos_group]
        if comp_m not in metrics:
            metrics.append(comp_m)

    filtered = {m: percentiles_all[m] for m in metrics if m in percentiles_all}

    if not filtered:
        return html.Div([
            header,
            html.P("No hay datos de percentiles para esta posición.",
                   className="text-muted small"),
        ])

    bars = create_percentile_bars(filtered)
    comparison_label = html.Div(
        f"vs. {pos_group}s in HKPL",
        style={"fontSize": "0.65rem", "color": HKFATheme.TEXT_SECONDARY,
               "textAlign": "right", "marginBottom": "8px", "letterSpacing": "0.03em"},
    )

    return html.Div([header, comparison_label, bars])


def _build_career_arc(data: Dict) -> html.Div:
    """§4 Career Arc: multi-season trend chart + positional radar + narrative insight."""
    from utils.chart_helpers import create_radar_chart

    history_df  = data.get("history_df", pd.DataFrame())
    pos_group   = data.get("pos_group") or ""
    player_name = data.get("player_name", "")
    
    # Use the first metric as primary for the title/default logic
    primary_metric = POSITION_METRICS.get(pos_group, ["Goals"])[0]

    header = html.H6([
        html.I(className="bi bi-graph-up-arrow me-2"),
        html.Span("Career Arc", className="animate-glass-draw"),
    ], className="mb-3 fw-semibold", style={"color": "var(--accent-cyan, #00d4ff)"})

    if history_df.empty:
        return html.Div([
            header,
            html.P("No hay datos de carrera disponibles.", className="text-muted small"),
        ])

    # ── Multi-metric Trend chart ───────────────────────────────────────────
    trend_fig = go.Figure()
    all_metrics = CAREER_ARC_ALL_METRICS.get(pos_group, [primary_metric])

    # Sort by season so X axis is always chronological
    history_df = history_df.sort_values("Season").reset_index(drop=True)
    seasons = history_df["Season"].tolist()

    has_minutes = "Minutes played" in history_df.columns and "Minutes played" in all_metrics
    colors = HKFATheme.DATA_SERIES

    for i, metric in enumerate(all_metrics):
        if metric not in history_df.columns:
            continue

        vals = history_df[metric].fillna(0).tolist()
        raw_label = metric.split(",")[0].strip()
        # Wrap long labels at a word boundary so they don't crowd the legend
        if len(raw_label) > 11 and " " in raw_label:
            words = raw_label.split()
            mid = max(1, len(words) // 2)
            raw_label = " ".join(words[:mid]) + "<br>" + " ".join(words[mid:])
        m_label = raw_label

        is_minutes = metric == "Minutes played"
        visibility = get_career_arc_visibility(metric, pos_group)

        trace_color = colors[i % len(colors)]
        group_key = f"metric_{i}"

        trace_kwargs = {
            "x": seasons,
            "y": vals,
            "mode": "lines+markers",
            "name": m_label,
            "visible": visibility,
            "line": dict(color=trace_color, width=2 if visibility is True else 1.5),
            "marker": dict(size=6),
            "cliponaxis": False,
            "hovertemplate": f"%{{x}}<br>{m_label}: %{{y:.1f}}<extra></extra>",
            "legendgroup": group_key,
        }

        if is_minutes:
            trace_kwargs["yaxis"] = "y2"
            trace_kwargs["line"]["dash"] = "dash"

        trend_fig.add_trace(go.Scatter(**trace_kwargs))

        # Add "best" star marker for every metric (visible or legendonly)
        # Shares legendgroup so clicking legend toggles both line and star together
        if vals:
            best_idx = vals.index(max(vals))
            star_kwargs = dict(
                x=[seasons[best_idx]], y=[vals[best_idx]],
                mode="markers+text", showlegend=False,
                legendgroup=group_key,
                marker=dict(size=11, color=HKFATheme.ACCENT_GOLD, symbol="star"),
                text=[f"Best: {vals[best_idx]:.0f}"],
                textposition="top center",
                textfont=dict(size=9, color=HKFATheme.ACCENT_GOLD),
                hovertemplate=f"Career best<br>{m_label}: %{{y:.1f}}<extra></extra>",
                visible=visibility,
                cliponaxis=False,
            )
            if is_minutes:
                star_kwargs["yaxis"] = "y2"
            trend_fig.add_trace(go.Scatter(**star_kwargs))

    # Layout updates for secondary Y-axis and legend
    # Pre-reserve right margin when minutes axis exists so the plot width stays
    # constant whether minutes played is visible or legendonly (prevents legend shrink).
    right_margin = 70 if has_minutes else 40

    layout_update = {
        "title": dict(text="Performance Evolution", x=0.01, xanchor="left", font=dict(size=13)),
        "xaxis_title": "Season",
        "xaxis": dict(ticklabelstandoff=8),
        "yaxis_title": "Metric Value",
        "yaxis": dict(rangemode="tozero"),
        "hovermode": "x unified",
        "showlegend": True,
        "legend": dict(
            orientation="h",
            yanchor="top",
            y=-0.18,
            xanchor="left",
            x=0,
            font=dict(size=9),
            tracegroupgap=0,
        ),
        "margin": dict(l=40, r=right_margin, t=40, b=100),
    }

    if has_minutes:
        layout_update["yaxis2"] = dict(
            title="Minutes Played",
            overlaying="y",
            side="right",
            showgrid=False,
            rangemode="tozero",
            title_font=dict(color=HKFATheme.TEXT_SECONDARY),
            tickfont=dict(color=HKFATheme.TEXT_SECONDARY),
        )
        layout_update["yaxis_title"] = "Technical Metrics"

    trend_fig.update_layout(**layout_update)
    trend_fig = glass_figure_layout(trend_fig)

    # Post-theme overrides — must run AFTER glass_figure_layout so apply_hkfa_theme
    # doesn't clobber them.  The right (y2) axis border is added here so it
    # matches the left y-axis styling.
    if has_minutes:
        trend_fig.update_layout(yaxis2=dict(
            showline=True,
            linewidth=1,
            linecolor="rgba(255,255,255,0.35)",
            layer="below traces",
        ))

    # ── Radar chart ────────────────────────────────────────────────────────
    percentiles_all = data.get("percentiles_data") or {}
    # Position-specific metrics + general supplements for a fuller player picture
    pos_radar      = [m for m in POSITION_METRICS.get(pos_group, []) if m in percentiles_all]
    supplemental   = [m for m in SUPPLEMENTAL_RADAR_METRICS.get(pos_group, [])
                      if m in percentiles_all and m not in pos_radar]
    radar_metrics  = pos_radar + supplemental
    radar_fig      = go.Figure()
    if len(radar_metrics) >= 3:
        # percentiles_all[m] is a dict: {value, percentile, group_avg_percentile, ...}
        pct_vals = [percentiles_all[m]["percentile"] for m in radar_metrics]
        ref_vals = [percentiles_all[m]["group_avg_percentile"] for m in radar_metrics]
        raw_labels = [m.split(",")[0].split(" per")[0].strip() for m in radar_metrics]
        labels = []
        for lbl in raw_labels:
            if len(lbl) > 10 and " " in lbl:
                words = lbl.split()
                mid = max(1, len(words) // 2)
                lbl = " ".join(words[:mid]) + "<br>" + " ".join(words[mid:])
            labels.append(lbl)
        radar_fig = glass_figure_layout(create_radar_chart(
            values=pct_vals, metrics=labels,
            title="Position Profile", name=player_name, height=340,
            reference_values=ref_vals, reference_name="Position Avg",
        ))
        radar_fig.update_layout(
            polar=dict(domain=dict(y=[0, 0.85])),
            legend=dict(
                orientation="h",
                yanchor="top",
                y=-0.15,
                xanchor="center",
                x=0.5,
                font=dict(size=9),
            ),
            margin=dict(l=20, r=20, t=55, b=70),
        )
    else:
        radar_fig.add_annotation(text="Insufficient data", showarrow=False,
                                 font=dict(color=HKFATheme.TEXT_SECONDARY))
        radar_fig = glass_figure_layout(radar_fig)

    # ── Rich insights ──────────────────────────────────────────────────────
    insight_rows: List[tuple] = []  # (icon_class, color, text)

    has_min_col = "Minutes played" in history_df.columns
    label_pm    = primary_metric.split(",")[0].split(" per")[0].strip()

    # 1. Position Profile cross-ref: standout metric vs group
    if radar_metrics and percentiles_all:
        best_m   = max(radar_metrics, key=lambda m: percentiles_all[m]["percentile"])
        worst_m  = min(radar_metrics, key=lambda m: percentiles_all[m]["percentile"])
        best_pct = percentiles_all[best_m]["percentile"]
        worst_pct= percentiles_all[worst_m]["percentile"]
        pos_avg  = percentiles_all[best_m]["group_avg_percentile"]
        short_b  = best_m.split(",")[0].split(" per")[0].strip()
        short_w  = worst_m.split(",")[0].split(" per")[0].strip()
        delta    = best_pct - pos_avg
        insight_rows.append((
            "bi bi-award",
            HKFATheme.ACCENT_GOLD,
            f"Position Profile · Strength: {short_b} ({best_pct:.0f}th pct, {delta:+.0f} vs group) "
            f"— Area to develop: {short_w} ({worst_pct:.0f}th pct)"
        ))

    # 2. Performance Evolution cross-ref: career trajectory + peak with minutes context
    if primary_metric in history_df.columns and len(history_df) >= 2:
        metric_vals    = history_df[primary_metric].fillna(0).tolist()
        metric_seasons = history_df["Season"].tolist()
        if metric_vals:
            peak_idx    = metric_vals.index(max(metric_vals))
            peak_val    = metric_vals[peak_idx]
            peak_season = metric_seasons[peak_idx]
            peak_mins   = int(history_df["Minutes played"].fillna(0).iloc[peak_idx]) if has_min_col else None
            mins_note   = f" ({peak_mins} mins that season)" if peak_mins else ""
            n = len(metric_vals)
            if n >= 3:
                first_avg = sum(metric_vals[:max(1, n // 2)]) / max(1, n // 2)
                last_avg  = sum(metric_vals[n // 2:]) / max(1, n - n // 2)
                pct_chg   = ((last_avg - first_avg) / max(0.001, abs(first_avg))) * 100
                if pct_chg > 10:
                    icon, color = "bi bi-graph-up-arrow", HKFATheme.POSITIVE
                    traj = f"Performance Evolution · Improving trajectory — career high {peak_val:.1f} {label_pm} in {peak_season}{mins_note}"
                elif pct_chg < -10:
                    icon, color = "bi bi-graph-down-arrow", HKFATheme.NEGATIVE
                    traj = f"Performance Evolution · Declining since {peak_season} peak ({peak_val:.1f} {label_pm}{mins_note})"
                else:
                    icon, color = "bi bi-activity", HKFATheme.ACCENT_BLUE
                    traj = f"Performance Evolution · Consistent output — career high {peak_val:.1f} {label_pm} in {peak_season}{mins_note}"
            else:
                icon, color = "bi bi-activity", HKFATheme.ACCENT_BLUE
                traj = f"Performance Evolution · Career high {peak_val:.1f} {label_pm} in {peak_season}"
            insight_rows.append((icon, color, traj))

    # 3. xG vs Goals efficiency (for attacking positions — non-obvious from charts at a glance)
    if pos_group in ("Forward", "Winger") and "xG" in history_df.columns and "Goals" in history_df.columns:
        xg_total    = history_df["xG"].fillna(0).sum()
        goals_total = history_df["Goals"].fillna(0).sum()
        if xg_total > 0.5:
            ratio = goals_total / xg_total
            if ratio < 0.75:
                insight_rows.append((
                    "bi bi-crosshair", HKFATheme.NEGATIVE,
                    f"Finishing gap: {goals_total:.0f} goals vs {xg_total:.1f} xG career total "
                    f"— converting at {ratio*100:.0f}% of expected (below average)"
                ))
            elif ratio > 1.2:
                insight_rows.append((
                    "bi bi-crosshair", HKFATheme.POSITIVE,
                    f"Clinical finisher: {goals_total:.0f} goals vs {xg_total:.1f} xG career total "
                    f"— {(ratio-1)*100:.0f}% above expected output"
                ))

    # 4. Minutes-performance correlation (non-obvious pattern)
    if has_min_col and primary_metric in history_df.columns and len(history_df) >= 3:
        import numpy as _np
        mins_arr = history_df["Minutes played"].fillna(0).values
        perf_arr = history_df[primary_metric].fillna(0).values
        if mins_arr.std() > 0 and perf_arr.std() > 0:
            corr = float(_np.corrcoef(mins_arr, perf_arr)[0, 1])
            if corr > 0.65:
                insight_rows.append((
                    "bi bi-clock-history", HKFATheme.ACCENT_BLUE,
                    f"Pattern: {label_pm} closely tracks playing time (r={corr:.2f}) "
                    f"— see Performance Evolution: peaks align with most minutes"
                ))
            elif corr < -0.5:
                insight_rows.append((
                    "bi bi-lightning-charge", HKFATheme.ACCENT_GOLD,
                    f"Impact player: {label_pm} highest when minutes are limited (r={corr:.2f}) "
                    f"— concentrated efficiency over full-season endurance"
                ))

    # 5. Playing time evolution
    if has_min_col and len(history_df) >= 2:
        mins_list = history_df["Minutes played"].fillna(0).tolist()
        first_min, last_min = mins_list[0], mins_list[-1]
        first_szn = history_df["Season"].iloc[0]
        last_szn  = history_df["Season"].iloc[-1]
        if first_min > 0:
            pct_chg = ((last_min - first_min) / first_min) * 100
            if pct_chg > 25:
                insight_rows.append((
                    "bi bi-person-check", HKFATheme.POSITIVE,
                    f"Playing time ↑{pct_chg:.0f}% from {first_szn} to {last_szn} "
                    f"({int(first_min)}→{int(last_min)} mins) — growing coach trust"
                ))
            elif pct_chg < -25:
                insight_rows.append((
                    "bi bi-person-dash", HKFATheme.NEGATIVE,
                    f"Playing time ↓{abs(pct_chg):.0f}% from {first_szn} peak "
                    f"({int(first_min)} mins) — role reduced by {last_szn}"
                ))

    # 6. Narrative from Gemini (when available) or enriched template
    narrative = _generate_career_insight(
        history_df, primary_metric, player_name,
        pos_group=pos_group,
        form_trend=data.get("form_trend"),
        transferability=data.get("transferability"),
    )
    if narrative:
        insight_rows.append(("bi bi-lightbulb", HKFATheme.ACCENT_GOLD, narrative))

    if insight_rows:
        insight_el = html.Div(
            [html.Div(
                [html.I(className=f"{icon} me-2", style={"color": color, "fontSize": "0.72rem", "flexShrink": "0"}),
                 html.Span(txt, style={"fontSize": "0.78rem", "color": HKFATheme.TEXT_SECONDARY, "lineHeight": "1.4"})],
                style={"display": "flex", "alignItems": "flex-start", "marginBottom": "4px"},
            ) for icon, color, txt in insight_rows],
            style={"padding": "8px 12px", "background": "rgba(255,255,255,0.03)",
                   "borderRadius": "6px", "marginTop": "8px"},
        )
    else:
        insight_el = html.Span()

    # ── Career cluster evolution ───────────────────────────────────────────
    try:
        evolution_el = _build_career_cluster_evolution(data)
    except Exception as e:
        logger.debug(f"_build_career_cluster_evolution failed: {e}")
        evolution_el = html.Span()

    return html.Div([
        header,
        dbc.Row([
            dbc.Col(dcc.Graph(figure=trend_fig, config={"displayModeBar": False}, className="w-100"), width=12, lg=7),
            dbc.Col(dcc.Graph(figure=radar_fig, config={"displayModeBar": False}, className="w-100"), width=12, lg=5),
        ]),
        evolution_el,
        insight_el,
    ])


def _build_projection_section(data: Dict, player_id: str) -> html.Div:
    """§5 Projection: season-end projection chart with guard for matches_played < 10."""
    header = html.H6([
        html.I(className="bi bi-graph-up me-2"),
        html.Span("Season Projection", className="animate-glass-draw"),
    ], className="mb-3 fw-semibold", style={"color": "var(--accent-cyan, #00d4ff)"})

    matches_played = data.get("matches_played", 0)
    if matches_played < 10:
        return html.Div([
            header,
            html.P("Proyección disponible a partir de 10 partidos jugados.",
                   className="text-muted small"),
        ])

    current_season = data.get("current_season") or _get_current_season()
    proj_fig = get_projection_figure(player_id, current_season, current_season)
    return html.Div([
        header,
        dcc.Graph(figure=proj_fig, config={"displayModeBar": False}, className="w-100"),
    ])


_CYTO_STYLESHEET = [
    {"selector": "node", "style": {
        "label": "data(label)",
        "color": "#ffffff",
        "font-size": "10px",
        "text-valign": "bottom",
        "text-margin-y": "4px",
        "border-width": "1px",
        "border-color": "rgba(255,255,255,0.2)",
    }},
    {"selector": ".central", "style": {
        "background-color": HKFATheme.ACCENT_RED,
        "width": 60, "height": 60,
        "border-width": "3px",
        "border-color": "#ffffff",
        "font-size": "11px",
        "font-weight": "bold",
    }},
    {"selector": ".similar", "style": {
        "width": 44, "height": 44,
    }},
    {"selector": "edge", "style": {
        "width": "data(weight)",
        "line-color": "rgba(255,255,255,0.25)",
        "label": "data(score_label)",
        "font-size": "9px",
        "color": "rgba(255,255,255,0.5)",
        "text-rotation": "autorotate",
    }},
]


def _build_similar_players(data: Dict) -> html.Div:
    """
    §6 Similar Players: Parallel Categories chart visualizing categorical similarity dimensions.
    Replaces legacy Cytoscape graph. Maps Player, Team, Similitud Range, and Position.
    """
    player_name = data.get("player_name", "Query Player")
    meta = data.get("similar_players_meta", {})
    similar_list = meta.get("similar_players", [])

    header = html.H6([
        html.I(className="bi bi-people-fill me-2"),
        html.Span("Categorical Similarity Mapping", className="animate-glass-draw"),
    ], className="mb-3 fw-semibold", style={"color": "var(--accent-cyan, #00d4ff)"})

    if not similar_list:
        return html.Div([header, html.P("Similar players not available.", className="text-muted small")])

    # ── Build Parallel Categories Chart ────────────────────────────────────
    try:
        # Construct DataFrame for dimensions
        rows = []
        # Include query player as first flow for reference
        rows.append({
            "Player": player_name,
            "Team": data.get("team_name") or "Your Team",
            "Similarity": "100% (Query)",
            "Position": data.get("position_main") or data.get("pos_group") or "Unknown"
        })

        for p in similar_list:
            score = p["similarity_score"]
            if score >= 0.95: s_range = "95-100% Elite"
            elif score >= 0.90: s_range = "90-95% High"
            elif score >= 0.85: s_range = "85-90% Strong"
            else: s_range = "80-85% Moderate"

            rows.append({
                "Player": p["name"],
                "Team": p["team_name"],
                "Similarity": s_range,
                "Position": p["position"]
            })

        df_sim = pd.DataFrame(rows)
        
        fig = px.parallel_categories(
            df_sim,
            dimensions=["Player", "Team", "Similarity", "Position"],
            color_continuous_scale=px.colors.sequential.Teal,
            labels={c: c.replace("_", " ") for c in df_sim.columns}
        )

        # Apply HKFA theme styling
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color=HKFATheme.TEXT_PRIMARY, size=10),
            margin=dict(l=60, r=60, t=20, b=20),
            height=300,
            dragmode=False, # Disable zooming/panning per spec
        )
        
        # Details Table
        table_header = [
            html.Thead(html.Tr([
                html.Th("Player", style={"fontSize": "0.7rem", "color": HKFATheme.TEXT_SECONDARY}),
                html.Th("Team", style={"fontSize": "0.7rem", "color": HKFATheme.TEXT_SECONDARY}),
                html.Th("Pos", style={"fontSize": "0.7rem", "color": HKFATheme.TEXT_SECONDARY}),
                html.Th("Sim %", style={"fontSize": "0.7rem", "color": HKFATheme.TEXT_SECONDARY, "textAlign": "right"}),
            ]))
        ]
        
        table_rows = []
        for p in similar_list:
            logo_path = p.get("team_logo_path")
            team_cell = html.Div([
                html.Img(src=logo_path, style={"height": "12px", "marginRight": "4px"}) if logo_path else None,
                html.Span(p["team_name"], style={"fontSize": "0.75rem"})
            ], style={"display": "flex", "alignItems": "center"})

            table_rows.append(html.Tr([
                html.Td(p["name"], style={"fontSize": "0.75rem", "fontWeight": "600"}),
                html.Td(team_cell),
                html.Td(p["position"], style={"fontSize": "0.75rem"}),
                html.Td(f"{p['similarity_score']*100:.1f}%", style={"fontSize": "0.75rem", "textAlign": "right", "color": HKFATheme.ACCENT_BLUE}),
            ]))

        table = dbc.Table(
            table_header + [html.Tbody(table_rows)],
            borderless=True, hover=True, responsive=True, size="sm",
            style={"marginTop": "15px", "background": "transparent"}
        )

        return html.Div([
            header,
            dcc.Graph(figure=fig, config={"displayModeBar": False, "staticPlot": True}),
            table
        ])

    except Exception as e:
        logger.warning(f"_build_similar_players Parallel Categories error: {e}")
        return html.Div([header, html.P("Mapping error. Reverting to basic view.", className="text-muted small")])


def render_player_dashboard(
    player_name: str,
    player_id: str,
    user_role: str = "player",
) -> html.Div:
    """
    Orchestrates the 6-section player dashboard for Estado A (no card open).
    Fetches data once and delegates to independent builders with per-section error isolation.
    """
    data = _fetch_dashboard_data(player_name, player_id)

    def _safe_build(builder_fn, *args, **kwargs) -> html.Div:
        try:
            return builder_fn(*args, **kwargs)
        except Exception as e:
            logger.warning(f"Dashboard section '{builder_fn.__name__}' failed: {e}")
            return html.P("Sección no disponible", className="text-muted small")

    sections = [
        _safe_build(_build_identity_hero,       data),
        html.Hr(style={"borderColor": HKFATheme.BORDER_COLOR, "margin": "12px 0"}),
        _safe_build(_build_cluster_dna,          data),
        html.Hr(style={"borderColor": HKFATheme.BORDER_COLOR, "margin": "12px 0"}),
        _safe_build(_build_season_pulse,         data),
        html.Hr(style={"borderColor": HKFATheme.BORDER_COLOR, "margin": "12px 0"}),
        _safe_build(_build_league_standing,      data),
        html.Hr(style={"borderColor": HKFATheme.BORDER_COLOR, "margin": "12px 0"}),
        _safe_build(_build_career_arc,           data),
        html.Hr(style={"borderColor": HKFATheme.BORDER_COLOR, "margin": "12px 0"}),
        _safe_build(_build_projection_section,   data, player_id),
        html.Hr(style={"borderColor": HKFATheme.BORDER_COLOR, "margin": "12px 0"}),
        _safe_build(_build_similar_players,      data),
    ]

    return html.Div(
        dbc.Card(html.Div(sections, className="pb-2"), className="glass-card glass-career"),
    )


def render_career_overview(
    player_name: str,
    player_id: str,
    user_role: str = "player",
) -> html.Div:
    """
    Default stage shown when NO card is open.
    # Shim — ver render_player_dashboard()
    Delegates entirely to render_player_dashboard() preserving the original signature
    for backward compatibility with any existing callers.
    """
    return render_player_dashboard(player_name, player_id, user_role)


def render_pre_match(
    payload: Dict[str, Any],
    player_pos_group: str = "",
    player_position_main: str = "",
    player_current_role: str = "",
) -> html.Div:
    """Renders the advanced pre-match stage inside the persistent stage shell."""
    opponent = payload.get("opponent", "Opponent")
    home = payload.get("home_team", "")
    away = payload.get("away_team", "")
    date_str = payload.get("kickoff_display") or str(payload.get("date", ""))[:16]
    stadium = payload.get("stadium", "")
    streaming_url = _clean_url(payload.get("streaming_url") or "")
    competition = payload.get("competition", "HK Premier League")
    competition_logo = payload.get("competition_logo") or get_competition_logo(competition)
    home_logo = payload.get("home_logo")
    away_logo = payload.get("away_logo")
    has_var = bool(payload.get("has_var"))
    is_tv = bool(payload.get("is_tv"))
    broadcast_type = str(payload.get("broadcast_type") or "").strip()
    role_label = POSITION_FULL_NAMES.get(str(player_current_role or player_position_main).upper(), player_current_role or player_position_main)
    opponent_team = opponent if opponent else (away if home else home)
    player_id = _get_logged_in_player_id()
    recent_form = _get_recent_form_summary(player_id)
    h2h_summary = _get_head_to_head_summary(player_id, opponent_team)
    cutoff_dt = _coerce_cutoff_datetime(payload)
    if cutoff_dt is not None and recent_form.get("results"):
        try:
            from models.db_models import MatchHistory, Player
            from utils.db_engine import SessionFactory

            with SessionFactory() as session:
                player = session.get(Player, player_id) if player_id else None
                player_team = ""
                if player is not None:
                    try:
                        player_team = str(player.current_team.name or "").strip()
                    except Exception:
                        player_team = ""
                matches = (
                    session.query(MatchHistory)
                    .filter(MatchHistory.player_id == player_id)
                    .filter(MatchHistory.date < cutoff_dt.to_pydatetime())
                    .order_by(MatchHistory.date.desc())
                    .limit(5)
                    .all()
                )

            filtered = {
                "results": [],
                "goals_total": 0,
                "assists_total": 0,
                "minutes_total": 0,
                "xg_total": 0.0,
                "xa_total": 0.0,
                "goals_per90": 0.0,
                "assists_per90": 0.0,
                "xg_per90": 0.0,
                "xa_per90": 0.0,
            }
            for match in matches:
                raw_result = getattr(match, "result", "") or ""
                filtered["results"].append({
                    "outcome": _extract_outcome_from_result(raw_result, getattr(match, "opponent", ""), player_team),
                    "score": _extract_score_text(raw_result),
                    "penalties": "pen" in str(raw_result).lower(),
                })
                filtered["goals_total"] += int(getattr(match, "goals", 0) or 0)
                filtered["assists_total"] += int(getattr(match, "assists", 0) or 0)
                filtered["minutes_total"] += int(getattr(match, "minutes_played", 0) or 0)
                raw_data = getattr(match, "raw_data", None)
                filtered["xg_total"] += _extract_numeric_metric(raw_data, "xg", "xG", "expected goals")
                filtered["xa_total"] += _extract_numeric_metric(raw_data, "xa", "xA", "expected assists")
            minutes = filtered["minutes_total"]
            if minutes > 0:
                factor = 90.0 / minutes
                filtered["goals_per90"] = filtered["goals_total"] * factor
                filtered["assists_per90"] = filtered["assists_total"] * factor
                filtered["xg_per90"] = filtered["xg_total"] * factor
                filtered["xa_per90"] = filtered["xa_total"] * factor
            recent_form = filtered
        except Exception as exc:
            logger.debug(f"render_pre_match cutoff recent form error: {exc}")

    time_label = date_str
    date_label = ""
    raw_kickoff = str(date_str or "").strip()
    if "·" in raw_kickoff:
        left, right = [part.strip() for part in raw_kickoff.split("·", 1)]
        date_label = left.replace(",", "").strip()
        time_label = right
    elif "," in raw_kickoff:
        left, right = [part.strip() for part in raw_kickoff.rsplit(",", 1)]
        date_label = left.replace(",", "").strip()
        time_label = right
    elif len(raw_kickoff) >= 16 and raw_kickoff[4] == "-" and raw_kickoff[7] == "-":
        date_label = raw_kickoff[:10]
        time_label = raw_kickoff[10:].strip()

    time_label = (
        str(time_label)
        .replace(" HKT", "")
        .replace("hkt", "")
        .replace(" HkT", "")
        .strip()
    )

    dm = None
    rivals: List[Dict[str, Any]] = []
    try:
        dm = get_hong_kong_data_manager()
        pos_group = player_pos_group or "Midfielder"
        rivals = _get_opponent_rivals(
            opponent_team,
            pos_group,
            player_current_role or player_position_main,
            dm,
        )
    except Exception as exc:
        logger.debug(f"Rival analysis error: {exc}")

    def _section_title(icon: str, title: str, subtitle: str = "") -> html.Div:
        return html.Div([
            html.Div([
                html.I(className=f"bi {icon} me-2", style={"color": HKFATheme.ACCENT_BLUE}),
                html.Span(title, style={"fontWeight": "700", "fontSize": "1.05rem", "color": HKFATheme.TEXT_PRIMARY}),
            ], className="mb-1"),
            html.Div(subtitle, style={"color": "#c5d1dd", "fontSize": "0.82rem"}) if subtitle else None,
        ], className="mb-3", style={"marginBottom": "36px"})

    def _glass_card(
        children: Any,
        accent: str = HKFATheme.ACCENT_BLUE,
        extra_style: Optional[Dict[str, Any]] = None,
        extra_class: str = "",
    ) -> dbc.Card:
        base_style = {
            "background": "linear-gradient(180deg, rgba(255,255,255,0.085) 0%, rgba(255,255,255,0.035) 18%, rgba(31,35,50,0.12) 100%)",
            "border": f"1px solid rgba({_hex_to_rgb(accent)}, 0.20)",
            "borderRadius": "22px",
            "boxShadow": "0 10px 18px rgba(0,0,0,0.07), 0 4px 10px rgba(0,0,0,0.04)",
            "backdropFilter": "blur(22px) saturate(120%)",
            "WebkitBackdropFilter": "blur(22px) saturate(120%)",
            "position": "relative",
            "overflow": "hidden",
        }
        if extra_style:
            base_style.update(extra_style)
        class_name = "border-0 mb-3 prematch-float-card"
        if extra_class:
            class_name = f"{class_name} {extra_class}"
        return dbc.Card(children, className=class_name, style=base_style)

    def _chip(icon: str, label: str, accent: str, href: str = "") -> Any:
        content = html.Span([
            html.I(className=f"bi {icon} me-1", style={"color": accent, "fontSize": "0.82rem"}),
            html.Span(label, style={"color": "#eef4fa", "fontWeight": "400"}),
        ], style={"display": "inline-flex", "alignItems": "center"})
        common_style = {
            "display": "inline-flex",
            "alignItems": "center",
            "padding": "6px 10px",
            "borderRadius": "999px",
            "background": f"rgba({_hex_to_rgb(accent)}, 0.12)",
            "border": f"1px solid rgba({_hex_to_rgb(accent)}, 0.28)",
            "textDecoration": "none",
            "whiteSpace": "nowrap",
            "fontSize": "0.78rem",
        }
        if href:
            return html.A(content, href=href, target="_blank", style=common_style)
        return html.Span(content, style=common_style)

    def _team_block(name: str, logo: str, align: str) -> html.Div:
        text_align = "left" if align == "left" else "right"
        justify = "flex-start" if align == "left" else "flex-end"
        return html.Div([
            html.Div([
                html.Img(src=logo, style={"width": "96px", "height": "96px", "objectFit": "contain"}) if logo else html.Div(
                    name[:2].upper(),
                    style={
                        "width": "96px", "height": "96px", "borderRadius": "50%",
                        "display": "flex", "alignItems": "center", "justifyContent": "center",
                        "background": "rgba(255,255,255,0.08)", "color": "#f3f7fb", "fontWeight": "800",
                    },
                ),
            ], style={"display": "flex", "justifyContent": justify, "marginBottom": "10px"}),
            html.Div(name or "TBC", style={"color": "#f4f8fc", "fontWeight": "700", "fontSize": "1.08rem", "textAlign": "center", "letterSpacing": "0.01em"}),
        ], style={"flex": "0 1 210px", "minWidth": "190px", "maxWidth": "220px", "textAlign": "center", "display": "flex", "flexDirection": "column", "alignItems": "center"})

    stream_href = streaming_url if streaming_url and "facebook.com" not in streaming_url.lower() else ""
    broadcast_chips: List[Any] = []
    if has_var:
        broadcast_chips.append(_chip("bi-camera-video-fill", "VAR", HKFATheme.ACCENT_GOLD))
    if is_tv:
        broadcast_chips.append(_chip("bi-broadcast-pin", "RTHK", HKFATheme.ACCENT_BLUE))
    if broadcast_type.lower() == "free":
        broadcast_chips.append(_chip("bi-play-circle", "on.cc Free", "#54d29a", href=stream_href))
    elif broadcast_type.lower() in {"ppv", "pay-per-view"}:
        broadcast_chips.append(_chip("bi-cash-coin", "on.cc PPV", "#ff8a4c", href=stream_href))
    elif broadcast_type.lower() == "delayed":
        broadcast_chips.append(_chip("bi-clock-history", "Delayed", "#b4b9c1"))
    elif stream_href:
        broadcast_chips.append(_chip("bi-play-circle", "Watch stream", "#54d29a", href=stream_href))

    fixture_card = _glass_card(
        dbc.CardBody([
            html.Div([
                html.Img(src=competition_logo, style={"width": "46px", "height": "46px", "objectFit": "contain", "marginBottom": "8px"}) if competition_logo else None,
                html.Div(competition, style={"color": "#f6f8fb", "fontWeight": "700", "fontSize": "1.05rem"}),
            ], style={"display": "flex", "flexDirection": "column", "alignItems": "center", "marginBottom": "24px"}),
            html.Div([
                _team_block(home, home_logo, "right"),
                html.Div([
                    html.Div("VS", style={"color": "#d7dee8", "fontSize": "2rem", "fontWeight": "800", "letterSpacing": "0.06em"}),
                    html.Div(
                        time_label,
                        style={
                            "color": "#f4f8fc",
                            "fontSize": "1.28rem",
                            "fontWeight": "800",
                            "marginTop": "8px",
                            "display": "block",
                            "lineHeight": "1.15",
                        },
                    ),
                    html.Div(
                        date_label,
                        style={
                            "color": HKFATheme.ACCENT_GOLD,
                            "fontWeight": "500",
                            "fontSize": "0.8rem",
                            "marginTop": "10px",
                            "letterSpacing": "0.03em",
                            "display": "block",
                            "lineHeight": "1.1",
                        },
                    ) if date_label else None,
                ], style={"flex": "0 0 250px", "display": "flex", "flexDirection": "column", "alignItems": "center", "justifyContent": "center", "textAlign": "center", "padding": "0 12px"}),
                _team_block(away, away_logo, "left"),
            ], style={"display": "flex", "alignItems": "center", "justifyContent": "center", "gap": "28px", "flexWrap": "wrap"}),
            html.Hr(style={"borderColor": "rgba(255,255,255,0.14)", "margin": "20px 0 18px"}),
            html.Div([
                _chip("bi-geo-alt", stadium or "Stadium TBC", HKFATheme.ACCENT_BLUE),
                html.Div(broadcast_chips, style={"display": "flex", "gap": "10px", "flexWrap": "wrap", "justifyContent": "flex-end"}),
            ], style={"display": "flex", "justifyContent": "space-between", "alignItems": "center", "gap": "12px", "flexWrap": "wrap"}),
        ]),
        accent=HKFATheme.ACCENT_GOLD,
        extra_class="prematch-fixture-card",
        extra_style={
            "background": "linear-gradient(180deg, rgba(29,31,44,0.68) 0%, rgba(23,26,36,0.48) 100%)",
            "boxShadow": "0 12px 24px rgba(0,0,0,0.10), 0 6px 16px rgba(0,0,0,0.08)",
        },
    )

    def _result_chip(result: Dict[str, Any]) -> html.Div:
        outcome = str(result.get("outcome", "EMPTY") or "EMPTY").upper()
        color_map = {
            "W": "#76d289",
            "D": "#f4c351",
            "L": "#ef6b6b",
        }
        accent = color_map.get(outcome, "#8893a2")
        chip_lines = [html.Div(outcome, style={"fontWeight": "800", "fontSize": "1rem", "lineHeight": "1"})]
        chip_lines.append(html.Div(result.get("score", "—"), style={"fontWeight": "700", "fontSize": "0.82rem", "marginTop": "4px", "lineHeight": "1"}))
        if result.get("penalties"):
            chip_lines.append(html.Div("PEN", style={"fontSize": "0.58rem", "fontWeight": "700", "letterSpacing": "0.06em", "marginTop": "3px", "lineHeight": "1"}))
        return html.Div(chip_lines, style={
            "width": "48px",
            "minWidth": "48px",
            "height": "48px",
            "padding": "5px 4px",
            "borderRadius": "8px",
            "background": f"rgba({_hex_to_rgb(accent)}, 0.14)",
            "border": f"1px solid rgba({_hex_to_rgb(accent)}, 0.42)",
            "color": accent,
            "display": "flex",
            "flexDirection": "column",
            "alignItems": "center",
            "justifyContent": "center",
            "boxShadow": "0 10px 18px rgba(0,0,0,0.08)",
        })

    def _stat_card(label: str, value: str, accent: str, subtext: str = "", icon: str = "bi-dot") -> dbc.Card:
        return _glass_card(
            dbc.CardBody([
                html.Div([
                    html.I(className=f"bi {icon} me-2", style={"color": accent}),
                    html.Span(label, style={"color": "#c9d2de", "fontSize": "0.8rem", "fontWeight": "400"}),
                ], className="mb-2"),
                html.Div(value, style={"color": "#f4f8fc", "fontSize": "1.55rem", "fontWeight": "800", "lineHeight": "1.05"}),
                html.Div(subtext, style={"color": "#d6dde6", "fontSize": "0.86rem", "fontWeight": "400", "marginTop": "8px"}) if subtext else None,
            ]),
            accent=accent,
            extra_style={"height": "100%"},
        )

    minutes_total = int(recent_form.get("minutes_total", 0) or 0)
    recent_form_section = html.Div([
        html.Div(
            _section_title("bi-activity", "Recent Form", f"Your latest five matches before facing {opponent_team}" if opponent_team else ""),
            style={"marginBottom": "36px"},
        ),
        html.Div([
            html.Div([
                html.Div([_result_chip(item) for item in recent_form.get("results", [])], style={"display": "flex", "gap": "6px", "flexWrap": "wrap"}),
                html.Span(
                    f"Recent role: {role_label}",
                    style={
                        "padding": "5px 8px",
                        "borderRadius": "999px",
                        "background": f"rgba({_hex_to_rgb(HKFATheme.ACCENT_BLUE)}, 0.10)",
                        "border": f"1px solid rgba({_hex_to_rgb(HKFATheme.ACCENT_BLUE)}, 0.22)",
                        "color": HKFATheme.ACCENT_BLUE,
                        "fontSize": "0.72rem",
                        "fontWeight": "400",
                        "whiteSpace": "nowrap",
                        "marginLeft": "20px",
                    },
                ) if role_label else None,
            ], style={"display": "flex", "gap": "6px", "alignItems": "center", "flexWrap": "wrap"}),
        ], className="mb-3", style={"marginTop": "20px", "marginBottom": "20px", "display": "flex", "gap": "6px", "alignItems": "center", "justifyContent": "flex-start", "flexWrap": "wrap"}),
        html.Div(
            html.Div([
                html.Div(_stat_card("Minutes", f"{minutes_total}", "#b7c2d1", icon="bi-stopwatch"), style={"flex": "1 1 150px"}),
                html.Div(_stat_card("Goals", f"{int(recent_form.get('goals_total', 0) or 0)}", HKFATheme.ACCENT_RED, f"{recent_form.get('goals_per90', 0):.2f} per 90" if minutes_total else "", "bi-bullseye"), style={"flex": "1 1 150px"}),
                html.Div(_stat_card("Assists", f"{int(recent_form.get('assists_total', 0) or 0)}", HKFATheme.ACCENT_BLUE, f"{recent_form.get('assists_per90', 0):.2f} per 90" if minutes_total else "", "bi-stars"), style={"flex": "1 1 150px"}),
                html.Div(_stat_card("xG", f"{recent_form.get('xg_total', 0):.2f}", "#4ed0a6", f"{recent_form.get('xg_per90', 0):.2f} per 90" if minutes_total else "", "bi-graph-up-arrow"), style={"flex": "1 1 150px"}),
                html.Div(_stat_card("xA", f"{recent_form.get('xa_total', 0):.2f}", "#a28dff", f"{recent_form.get('xa_per90', 0):.2f} per 90" if minutes_total else "", "bi-bezier2"), style={"flex": "1 1 150px"}),
                html.Div(_stat_card("Rating", "—", HKFATheme.ACCENT_GOLD, "", "bi-star"), style={"flex": "1 1 150px"}),
            ], style={"display": "flex", "gap": "12px", "flexWrap": "wrap", "marginTop": "40px"}),
            style={"marginBottom": "36px"},
        ),
    ], className="mb-4", style={"marginBottom": "54px"})

    rival_cards: List[Any] = []
    for rival in rivals:
        accent = HKFATheme.ACCENT_RED if rival.get("matchup_tier") == "Primary Matchup" else HKFATheme.ACCENT_BLUE
        rival_cards.append(
            html.Div(_glass_card(
                dbc.CardBody([
                    html.Div([
                        html.Div(rival.get("name", "Unknown"), style={"color": "#f4f8fc", "fontSize": "1.02rem", "fontWeight": "700"}),
                        html.Span(rival.get("matchup_tier", "Support Matchup"), style={
                            "padding": "6px 10px",
                            "borderRadius": "999px",
                            "background": f"rgba({_hex_to_rgb(accent)}, 0.15)",
                            "border": f"1px solid rgba({_hex_to_rgb(accent)}, 0.28)",
                            "color": "#eef4fa",
                            "fontSize": "0.72rem",
                            "fontWeight": "600",
                        }),
                    ], style={"display": "flex", "justifyContent": "space-between", "gap": "8px", "alignItems": "flex-start", "marginBottom": "12px"}),
                    html.Div([
                        html.Span(rival.get("role_label", rival.get("position_group", "Unknown")), style={
                            "padding": "5px 10px",
                            "borderRadius": "999px",
                            "background": "rgba(255,255,255,0.06)",
                            "border": "1px solid rgba(255,255,255,0.10)",
                            "color": "#dce5ee",
                            "fontSize": "0.74rem",
                            "fontWeight": "500",
                        }),
                        html.Span(rival.get("form_label", "Stable"), style={
                            "padding": "5px 10px",
                            "borderRadius": "999px",
                            "background": "rgba(84,210,154,0.12)" if rival.get("form_label") == "In Form" else "rgba(244,195,81,0.12)",
                            "border": "1px solid rgba(255,255,255,0.10)",
                            "color": "#eaf2f8",
                            "fontSize": "0.74rem",
                            "fontWeight": "600",
                        }),
                    ], style={"display": "flex", "gap": "8px", "flexWrap": "wrap", "marginBottom": "12px"}),
                    html.Div([
                        html.Span([
                            html.I(className="bi bi-stopwatch me-1", style={"opacity": "0.78"}),
                            html.Span(str(rival.get("recent_minutes", 0))),
                        ], style={"display": "inline-flex", "alignItems": "center", "gap": "2px"}),
                        html.Span([
                            html.I(className="bi bi-bullseye me-1", style={"opacity": "0.78"}),
                            html.Span(str(rival.get("recent_goals", 0))),
                        ], style={"display": "inline-flex", "alignItems": "center", "gap": "2px"}),
                        html.Span([
                            html.I(className="bi bi-stars me-1", style={"opacity": "0.78"}),
                            html.Span(str(rival.get("recent_assists", 0))),
                        ], style={"display": "inline-flex", "alignItems": "center", "gap": "2px"}),
                        html.Span([
                            html.I(className="bi bi-square-fill me-1", style={"opacity": "0.92", "color": "#f4c351"}),
                            html.Span(str(rival.get("recent_yellow_cards", 0))),
                        ], style={"display": "inline-flex", "alignItems": "center", "gap": "2px"}),
                        html.Span([
                            html.I(className="bi bi-square-fill me-1", style={"opacity": "0.92", "color": "#ef6b6b"}),
                            html.Span(str(rival.get("recent_red_cards", 0))),
                        ], style={"display": "inline-flex", "alignItems": "center", "gap": "2px"}),
                    ], style={
                        "display": "flex",
                        "gap": "12px",
                        "flexWrap": "wrap",
                        "alignItems": "center",
                        "color": "#c7d0dc",
                        "fontSize": "0.76rem",
                        "fontWeight": "500",
                        "marginBottom": "16px",
                    }),
                    html.Div([
                        html.Div("Strength", style={"color": accent, "fontSize": "0.72rem", "textTransform": "uppercase", "letterSpacing": "0.08em", "fontWeight": "700"}),
                        html.Div(rival.get("strength_text", ""), style={"color": "#eff4fa", "fontWeight": "500", "marginTop": "4px", "fontSize": "0.9rem"}),
                    ], className="mb-3"),
                    html.Div([
                        html.Div("Weakness", style={"color": "#ffb3b3", "fontSize": "0.72rem", "textTransform": "uppercase", "letterSpacing": "0.08em", "fontWeight": "700"}),
                        html.Div(rival.get("weakness_text", ""), style={"color": "#eff4fa", "fontWeight": "500", "marginTop": "4px", "fontSize": "0.9rem"}),
                    ], className="mb-3"),
                    html.Div([
                        html.Div([
                            html.Div(f"{rival.get('key_val', 0):.1f}", style={"color": "#f4f8fc", "fontSize": "1.2rem", "fontWeight": "800"}),
                            html.Div(rival.get("key_label", ""), style={"color": "#c7d0dc", "fontSize": "0.78rem", "marginTop": "2px"}),
                        ], style={"flex": "1"}),
                        html.Div([
                            html.Div(f"{rival.get('sec_val', 0):.1f}", style={"color": "#f4f8fc", "fontSize": "1.2rem", "fontWeight": "800"}),
                            html.Div(rival.get("sec_label", ""), style={"color": "#c7d0dc", "fontSize": "0.78rem", "marginTop": "2px"}),
                        ], style={"flex": "1"}),
                    ], style={"display": "flex", "gap": "12px", "marginBottom": "12px"}),
                    html.Div([
                        html.Div("Physical", style={"color": "#b9c3cf", "fontSize": "0.72rem", "textTransform": "uppercase", "letterSpacing": "0.08em", "fontWeight": "700"}),
                        html.Div(f"{rival.get('physical_val', 0):.1f} {rival.get('physical_label', '')}", style={"color": "#eef4fa", "fontWeight": "600", "fontSize": "0.86rem", "marginTop": "4px"}),
                    ]) if rival.get("physical_label") else None,
                ]),
                accent=accent,
                extra_style={"height": "100%"},
            ), style={"flex": "1 1 260px", "minWidth": "240px"})
        )

    rivals_section = html.Div([
        html.Div(
            _section_title("bi-shield-exclamation", "Rivals to Watch", f"Likely direct matchups from {opponent_team}" if opponent_team else ""),
            style={"marginBottom": "36px"},
        ),
        html.Div(rival_cards, style={"display": "flex", "gap": "12px", "flexWrap": "wrap"}) if rival_cards else html.Div(
            "No direct rival profiles available yet.",
            style={"color": "#c5d1dd", "fontSize": "0.92rem"},
        ),
    ], className="mb-4", style={"marginBottom": "54px"})

    h2h_cards = []
    for match in h2h_summary:
        accent = {"W": "#76d289", "D": "#f4c351", "L": "#ef6b6b"}.get(match.get("outcome"), "#a1adbb")
        h2h_cards.append(
            html.Div(_glass_card(
                dbc.CardBody([
                    html.Div(match.get("outcome", "—"), style={"color": accent, "fontSize": "1.4rem", "fontWeight": "800", "textAlign": "center"}),
                    html.Div(match.get("score", "—"), style={"color": "#eef4fa", "fontWeight": "700", "textAlign": "center", "marginTop": "6px"}),
                    html.Div(f"{int(match.get('goals', 0) or 0)}G {int(match.get('assists', 0) or 0)}A", style={"color": "#cfd8e3", "fontSize": "0.82rem", "fontWeight": "700", "textAlign": "center", "marginTop": "8px"}),
                    html.Div("PEN", style={"color": accent, "fontSize": "0.72rem", "textAlign": "center", "marginTop": "6px", "fontWeight": "700"}) if match.get("penalties") else None,
                ]),
                accent=accent,
                extra_style={"height": "100%"},
            ), style={"flex": "0 1 130px"})
        )

    h2h_section = html.Div([
        html.Div(
            _section_title("bi-clock-history", "Your record vs this opponent", f"Last {max(len(h2h_summary), 1)} meetings against {opponent_team}" if opponent_team else ""),
            style={"marginBottom": "36px"},
        ),
        html.Div(h2h_cards, style={"display": "flex", "gap": "12px", "flexWrap": "wrap"}) if h2h_cards else html.Div(
            "No head-to-head data available yet.",
            style={"color": "#c5d1dd", "fontSize": "0.92rem"},
        ),
    ], className="mb-4", style={"marginBottom": "54px"})

    top_scorer_name = ""
    top_scorer_goals = 0
    try:
        team_stats = dm.get_team_statistics(opponent_team) if dm and opponent_team else {}
        top_scorers = (team_stats.get("top_players", {}) or {}).get("top_scorers", [])
        if top_scorers:
            top_scorer_name = top_scorers[0].get("name", "")
            top_scorer_goals = top_scorers[0].get("goals", 0)
    except Exception:
        pass

    game_plan_parts = []
    if top_scorer_name:
        game_plan_parts.append(f"{opponent_team}'s main scoring threat is {top_scorer_name} ({top_scorer_goals} goals), so be ready for their first movement around the box.")
    if rivals:
        main_rival = rivals[0]
        game_plan_parts.append(
            f"Your primary matchup is likely {main_rival.get('name', 'their main defender')} at {main_rival.get('role_label', main_rival.get('position_group', ''))}. "
            f"They are strong because they are {main_rival.get('strength_text', '').lower()}, but you can exploit them because they {main_rival.get('weakness_text', '').lower()}."
        )
    if int(recent_form.get("assists_total", 0) or 0) > int(recent_form.get("goals_total", 0) or 0):
        game_plan_parts.append("Lean into combination play early and attack the space behind their first line after your release pass.")
    else:
        game_plan_parts.append("Attack the box aggressively when the move reaches the final third, especially after quick wide combinations.")
    game_plan_text = " ".join(part for part in game_plan_parts if part).strip()
    if not game_plan_text:
        game_plan_text = f"Prepare for the match against {opponent_team}. Focus on quick transitions and aggressive first actions after the regain."

    game_plan_card = _glass_card(
        dbc.CardBody([
            _section_title("bi-robot", "AI Game-Plan"),
            html.P(game_plan_text, className="mb-0", style={"color": "#edf3f9", "fontSize": "0.98rem", "lineHeight": "1.65"}),
        ]),
        accent=HKFATheme.ACCENT_GOLD,
    )

    return html.Div([
        html.Div(fixture_card, style={"marginBottom": "36px"}),
        html.Div(recent_form_section, style={"marginBottom": "36px"}),
        html.Div(rivals_section, style={"marginBottom": "36px"}),
        html.Div(h2h_section, style={"marginBottom": "36px"}),
        game_plan_card,
    ], className="stage-inner")


def render_career_insights(payload: Dict[str, Any], user_role: str = "player") -> html.Div:
    """
    Renders the Career Insights stage with contextual projection, UMAP clustering,
    archetype badge, season-over-season delta KPIs, AI insight line,
    and a role-conditional Dossier export button.
    """
    season = payload.get("season", "")
    player_id = payload.get("player_id", "")
    player_name = payload.get("player_name", "Player")
    current_season = _get_current_season()

    # ── Fetch multi-season history (real data, no random) ──────────────────
    history_df = _fetch_player_season_history(player_name)

    # ── Archetype badge ────────────────────────────────────────────────────
    archetype_section = None
    try:
        dm = get_hong_kong_data_manager()
        pos_group = _get_position_group(player_name, dm)
        archetype = _get_archetype_label(player_name, pos_group, dm)
        if archetype:
            pos_icons = {
                "Forward": "bi-lightning-charge-fill",
                "Winger": "bi-wind",
                "Midfielder": "bi-shuffle",
                "Defender": "bi-shield-fill",
                "Goalkeeper": "bi-bullseye",
            }
            pos_icon = pos_icons.get(pos_group, "bi-person-fill")
            archetype_section = html.Div(
                [
                    html.I(
                        className=f"bi {pos_icon} me-2",
                        style={"color": HKFATheme.ACCENT_GOLD},
                    ),
                    html.Span(
                        archetype,
                        style={
                            "color": HKFATheme.ACCENT_GOLD,
                            "fontWeight": "700",
                            "fontSize": "0.9rem",
                        },
                    ),
                    html.Span(
                        f"  ·  {pos_group}",
                        style={
                            "color": HKFATheme.TEXT_SECONDARY,
                            "fontSize": "0.8rem",
                            "marginLeft": "4px",
                        },
                    ),
                ],
                style={
                    "display": "inline-flex",
                    "alignItems": "center",
                    "padding": "5px 14px",
                    "borderRadius": "20px",
                    "background": f"rgba({_hex_to_rgb(HKFATheme.ACCENT_GOLD)}, 0.1)",
                    "border": f"1px solid rgba({_hex_to_rgb(HKFATheme.ACCENT_GOLD)}, 0.35)",
                    "marginBottom": "12px",
                },
            )
    except Exception as e:
        logger.debug(f"Archetype badge error: {e}")

    # ── Season-over-season delta KPIs ──────────────────────────────────────
    delta_section = None
    try:
        dm = get_hong_kong_data_manager()
        pos_group = _get_position_group(player_name, dm)
        kpi_metrics = POSITION_METRICS.get(pos_group, ["Goals", "Assists"])[:3]
        # Filter to metrics available in history_df
        kpi_metrics = [m for m in kpi_metrics if m in (history_df.columns if not history_df.empty else [])]

        if not history_df.empty and len(history_df) >= 2 and kpi_metrics:
            current_row = history_df.iloc[-1]
            prev_row = history_df.iloc[-2]
            prev_season = history_df.iloc[-2]["Season"]
            delta_section = html.Div([
                html.Small(
                    [
                        html.I(className="bi bi-arrow-left-right me-1"),
                        f"vs {prev_season}",
                    ],
                    style={"color": HKFATheme.TEXT_SECONDARY, "display": "block", "marginBottom": "8px"},
                ),
                _build_delta_kpis(current_row, prev_row, kpi_metrics),
            ])
    except Exception as e:
        logger.debug(f"Delta KPIs error: {e}")

    # ── AI career insight (template-based) ────────────────────────────────
    insight_section = None
    try:
        dm = get_hong_kong_data_manager()
        pos_group = _get_position_group(player_name, dm)
        primary_metric = POSITION_METRICS.get(pos_group, ["Goals"])[0]
        insight_text = _generate_career_insight(history_df, primary_metric, player_name)
        if insight_text:
            insight_section = html.Div(
                [
                    html.I(
                        className="bi bi-lightbulb-fill me-2",
                        style={"color": HKFATheme.ACCENT_GOLD, "fontSize": "0.85rem"},
                    ),
                    html.Span(insight_text, style={"fontSize": "0.85rem", "color": HKFATheme.TEXT_SECONDARY}),
                ],
                style={
                    "padding": "8px 12px",
                    "borderRadius": "8px",
                    "background": "rgba(255,184,28,0.06)",
                    "border": f"1px solid rgba({_hex_to_rgb(HKFATheme.ACCENT_GOLD)}, 0.2)",
                    "marginBottom": "14px",
                    "display": "flex",
                    "alignItems": "center",
                },
            )
    except Exception as e:
        logger.debug(f"Career insight error: {e}")

    # ── Projection figure (context-aware: wrap_up vs projection mode) ──────
    projection_fig = get_projection_figure(player_id, season, current_season=current_season)
    projection_section = html.Div(
        dcc.Graph(figure=projection_fig, config={"displayModeBar": False}, className="w-100"),
        className="mb-3",
    )

    # ── UMAP clustering figure ─────────────────────────────────────────────
    umap_fig = get_umap_figure(player_id)
    umap_section = html.Div(
        dcc.Graph(figure=umap_fig, config={"displayModeBar": False}, className="w-100"),
        className="mb-3",
    )

    # ── Agent role: Dossier export button ──────────────────────────────────
    dossier_button = html.Div()
    if user_role == "agent":
        dossier_button = html.Div([
            dbc.Button(
                [html.I(className="bi bi-file-earmark-pdf me-2"), "Export PDF Dossier"],
                id="export-dossier-btn",
                color="danger",
                outline=True,
                className="mt-2",
                n_clicks=0,
            ),
            dcc.Download(id="dossier-download"),
        ])

    return html.Div(
        html.Div([
            html.H6([
                html.I(className="bi bi-calendar3 me-2"),
                html.Span(
                    f"Career Perspective — Season {season}",
                    className="animate-glass-draw",
                ),
            ], className="mb-3 fw-semibold", style={"color": "var(--accent-cyan, #00d4ff)"}),
            archetype_section,
            insight_section,
            delta_section,
            dbc.Row([
                dbc.Col(projection_section, width=12, lg=6),
                dbc.Col(umap_section, width=12, lg=6),
            ]),
            dossier_button,
        ], className="pb-2"),
        className="glass-card glass-career",
    )

def get_umap_figure(player_id: str) -> go.Figure:
    """
    Wraps clustering_engine output into a Plotly figure.
    Highlights the selected player's point.
    """
    try:
        from ai_models.clustering import fit_umap
        from utils.player_index import get_player_index

        dm = get_hong_kong_data_manager()
        df = dm.processed_data
        if df is None or df.empty:
            fig = go.Figure()
            fig.add_annotation(text="No data available for clustering", showarrow=False)
            return apply_hkfa_theme(fig)

        # 1. Resolve player name
        pi = get_player_index()
        player_info = pi.get_player_info(player_id)
        player_name = player_info.get("canonical_name") if player_info else None

        # 2. Prepare features
        meta_cols = {"Player", "Season", "Team", "Position"}
        feature_cols = [c for c in df.columns if c not in meta_cols and pd.api.types.is_numeric_dtype(df[c])]

        # Sample for performance if needed, but ensure player is included
        if len(df) > 1000:
            df_plot = df.sample(1000)
            if player_name and player_name not in df_plot["Player"].values:
                player_row = df[df["Player"] == player_name]
                if not player_row.empty:
                    df_plot = pd.concat([df_plot, player_row.head(1)])
        else:
            df_plot = df

        X = df_plot[feature_cols].fillna(0).values
        # Standardize
        X_scaled = (X - X.mean(axis=0)) / (X.std(axis=0) + 1e-6)

        names = df_plot["Player"].tolist()
        # Serialize Numba/UMAP calls — workqueue layer is not thread-safe
        with _umap_lock:
            umap_df, _ = fit_umap(X_scaled, player_names=names)

        # Add metadata for hover
        if "Team" in df_plot.columns: umap_df["team"] = df_plot["Team"].values
        if "Season" in df_plot.columns: umap_df["season"] = df_plot["Season"].values

        # Build K-Means cluster labels for constellation
        cluster_labels_umap = None
        archetype_labels_umap = None
        try:
            from ai_models.model_registry import ModelRegistry
            from ai_models.clustering import label_archetypes
            km_u = ModelRegistry().load("kmeans_overall_k5")
            if km_u is not None:
                cluster_labels_umap = km_u.predict(X_scaled)
                archetype_labels_umap = label_archetypes(km_u, feature_cols)
        except Exception:
            pass

        knn_edges = _build_knn_edges(umap_df, k=4)
        fig = constellation_chart(
            umap_df,
            cluster_labels=cluster_labels_umap,
            archetype_labels=archetype_labels_umap,
            highlight_player=player_name,
            knn_edges=knn_edges,
        )
        fig.update_layout(title="Playstyle Constellation (UMAP)")
        return glass_figure_layout(fig)
    except Exception as e:
        logger.error(f"Error generating UMAP figure: {e}")
        fig = go.Figure()
        fig.add_annotation(text=f"Error: {str(e)}", showarrow=False)
        return glass_figure_layout(fig)

def get_projection_figure(
    player_id: str,
    selected_season: Optional[str] = None,
    current_season: Optional[str] = None,
) -> go.Figure:
    """
    Returns a Plotly figure for the performance projector.

    Mode selection:
    - If selected_season != current_season → wrap_up mode (season summary vs league avg).
    - If selected_season == current_season → projection mode (forward-looking trend).

    Args:
        player_id: Internal player identifier (Wyscout ID).
        selected_season: The season the user is viewing (e.g. "2022-23").
        current_season: The active season (e.g. "2025-26"). Defaults to data manager value.
    """
    if current_season is None:
        current_season = _get_current_season()
    if not selected_season:
        selected_season = current_season

    # Determine mode: Only current season gets projection; others get wrap-up summary
    mode = "wrap_up" if selected_season != current_season else "projection"

    try:
        from utils.player_index import get_player_index

        pi = get_player_index()
        player_info = pi.get_player_info(player_id)
        if not player_info:
            fig = go.Figure()
            fig.add_annotation(text="Player not found", showarrow=False)
            return apply_hkfa_theme(fig)

        player_name = player_info.get("canonical_name", "Player")
        seasons = sorted(player_info.get("seasons", []))

        if not seasons:
            fig = go.Figure()
            fig.add_annotation(text="Insufficient data", showarrow=False)
            return apply_hkfa_theme(fig)

        if mode == "wrap_up":
            return _build_wrapup_chart(player_name, selected_season, current_season)
        else:
            return _build_projection_chart(player_name, seasons, current_season)

    except Exception as e:
        logger.error(f"Error generating projection figure: {e}")
        fig = go.Figure()
        fig.add_annotation(text=f"Error: {str(e)}", showarrow=False)
        return apply_hkfa_theme(fig)


def _get_position_group(player_name: str, dm: "HongKongDataManager") -> str:
    """Derives the Position_Group for a player from the processed DataFrame (current or last active)."""
    try:
        df = dm.processed_data
        if df is not None and not df.empty:
            row = df[df["Player"] == player_name]
            if not row.empty:
                pos_group = row.iloc[0].get("Position_Group")
                if pos_group and str(pos_group) in POSITION_METRICS:
                    return str(pos_group)

        # Fallback to DB if not in current season
        from sqlalchemy import select
        from models.db_models import Player
        from utils.db_engine import SessionFactory
        with SessionFactory() as session:
            player = session.execute(select(Player).where(Player.name == player_name)).scalars().first()
            if player and player.position_main:
                # Map position_main to group
                pos = player.position_main.split(",")[0].strip().upper()
                if pos in ("GK", "GOALKEEPER"): return "Goalkeeper"
                if pos in ("CB", "RCB", "LCB", "LB", "RB", "LWB", "RWB"): return "Defender"
                if pos in ("RW", "LW", "RWF", "LWF", "RAMF", "LAMF"): return "Winger"
                if pos in ("CF", "ST"): return "Forward"
                return "Midfielder"

        return "Midfielder"
    except Exception as e:
        logger.debug(f"_get_position_group error: {e}")
        return "Midfielder"


def _get_archetype_label(player_name: str, pos_group: str, dm: "HongKongDataManager") -> str:
    """Returns a human-readable archetype label for a player."""
    try:
        df = dm.processed_data
        if df is not None and not df.empty:
            row = df[df["Player"] == player_name]
            if not row.empty:
                archetype = row.iloc[0].get("archetype")
                if archetype: return str(archetype).title()

        return f"{pos_group} Specialist"
    except:
        return "Standard Player"


def _build_wrapup_chart(
    player_name: str,
    selected_season: str,
    current_season: str,
) -> go.Figure:
    """
    Builds a Season Wrap-up bar chart comparing the player's metrics to the
    league average for their position group.
    """
    try:
        dm = get_hong_kong_data_manager()
        df = dm.processed_data
        pos_group = _get_position_group(player_name, dm)
        metrics = [m for m in POSITION_METRICS.get(pos_group, POSITION_METRICS["Midfielder"])
                   if m in (df.columns if df is not None else [])]

        if df is None or df.empty or not metrics:
            raise ValueError("No data available for wrap-up chart")

        # Player row (current season data — proxy for selected season)
        player_row = df[df["Player"] == player_name]
        player_vals = [
            float(player_row.iloc[0][m]) if not player_row.empty else 0.0
            for m in metrics
        ]

        # League average for the same position group
        league_df = df[df["Position_Group"] == pos_group] if "Position_Group" in df.columns else df
        league_vals = [
            float(league_df[m].mean()) if m in league_df.columns else 0.0
            for m in metrics
        ]

        fig = go.Figure()
        fig.add_trace(go.Bar(
            name=player_name,
            x=metrics,
            y=player_vals,
            marker_color=HKFATheme.ACCENT_BLUE,
        ))
        fig.add_trace(go.Bar(
            name="League Average",
            x=metrics,
            y=league_vals,
            marker_color=HKFATheme.ACCENT_RED,
            opacity=0.7,
        ))

        note = "" if selected_season == current_season else f" (proxy data: {current_season})"
        fig.update_layout(
            title=f"Season Summary {selected_season} — {player_name}{note}",
            barmode="group",
            xaxis_title="Metric",
            yaxis_title="Value",
            hovermode="x unified",
        )
        return glass_figure_layout(fig)

    except Exception as e:
        logger.warning(f"Wrap-up chart fallback: {e}")
        fig = go.Figure()
        fig.add_annotation(
            text=f"Season summary {selected_season} — league data not available",
            showarrow=False,
        )
        return glass_figure_layout(fig)


def _build_projection_chart(
    player_name: str,
    seasons: List[str],
    current_season: str,
    player_id: Optional[str] = None,
) -> go.Figure:
    """
    Builds a forward-looking performance projection line chart using REAL season data.

    Integrates:
    - Position-specific primary metric (via get_position_projection_metrics).
    - LSTM form trend overlay when ≥10 match records exist.
    - TabPFN Transferability Score badge annotation.
    - Baseline linear projection line preserved for reference.
    """
    try:
        dm = get_hong_kong_data_manager()
        pos_group = _get_position_group(player_name, dm)

        # Fetch real multi-season data
        history_df = _fetch_player_season_history(player_name)

        # ── Fetch match history for LSTM + position metrics ────────────────
        match_records: List[Dict] = []
        try:
            from sqlalchemy import select
            from models.db_models import Player, MatchHistory as MH
            from utils.db_engine import SessionFactory
            with SessionFactory() as sess:
                p_id = player_id
                if not p_id:
                    p_obj = sess.execute(
                        select(Player).where(Player.name == player_name)
                    ).scalars().first()
                    p_id = p_obj.id if p_obj else None
                if p_id:
                    rows = sess.execute(
                        select(MH)
                        .where(MH.player_id == p_id)
                        .order_by(MH.date.asc())
                    ).scalars().all()
                    match_records = [
                        {
                            "minutes_played": r.minutes_played or 0,
                            "goals": r.goals or 0,
                            "assists": r.assists or 0,
                        }
                        for r in rows
                    ]
        except Exception as me:
            logger.debug(f"_build_projection_chart: match history fetch failed: {me}")

        # ── Position-specific primary metric ──────────────────────────────
        from utils.performance_helpers import get_position_projection_metrics
        proj_meta = get_position_projection_metrics(pos_group, history_df, match_records)
        primary_metric = proj_meta.get("primary_metric") or POSITION_METRICS.get(pos_group, ["Goals"])[0]

        # Fall back to first available numeric column if primary_metric missing
        if not history_df.empty and primary_metric not in history_df.columns:
            fallback_cols = [c for c in history_df.columns if c != "Season" and history_df[c].dtype in (float, int, "float64", "int64")]
            if fallback_cols:
                primary_metric = fallback_cols[0]

        metric_label = primary_metric.split(",")[0].strip()

        if history_df.empty or primary_metric not in history_df.columns:
            fig = go.Figure()
            fig.add_annotation(
                text=f"No multi-season data available for {player_name}",
                showarrow=False,
                font=dict(color=HKFATheme.TEXT_SECONDARY),
            )
            fig.update_layout(title=f"Performance Trend: {player_name}")
            return glass_figure_layout(fig)

        real_seasons = history_df["Season"].tolist()
        real_vals = history_df[primary_metric].fillna(0).tolist()

        fig = go.Figure()

        # Historical line (real data)
        fig.add_trace(go.Scatter(
            x=real_seasons,
            y=real_vals,
            mode="lines+markers",
            name=metric_label,
            line=dict(color=HKFATheme.ACCENT_BLUE, width=3),
            marker=dict(size=8),
            hovertemplate=f"Season %{{x}}<br>{metric_label}: %{{y:.1f}}<extra></extra>",
        ))

        # ── LSTM form trend overlay ────────────────────────────────────────
        form_info: Dict = {}
        lstm_metric = "goals" if pos_group in ("Forward", "Winger") else (
            "assists" if pos_group == "Midfielder" else "minutes_played"
        )
        if len(match_records) >= 10:
            try:
                from ai_models.time_series import get_form_trend
                form_info = get_form_trend(match_records, lstm_metric, window=5)
            except Exception as fe:
                logger.debug(f"LSTM form trend error: {fe}")

        # ── Baseline linear projection ────────────────────────────────────
        if len(real_vals) >= 2:
            deltas = [b - a for a, b in zip(real_vals[:-1], real_vals[1:])]
            avg_delta = sum(deltas) / len(deltas)

            # Adjust by LSTM slope if available (blend: 70% linear + 30% LSTM)
            slope = form_info.get("slope", 0.0)
            blended_delta = avg_delta * 0.7 + slope * 0.3
            projected_val = max(0.0, real_vals[-1] + blended_delta)

            try:
                parts = current_season.split("-")
                next_season = f"{int(parts[0]) + 1}-{str(int(parts[1]) + 1).zfill(2)}"
            except Exception:
                next_season = "Next"

            trend_name = "Trend Projection"
            if form_info.get("trend") == "improving":
                trend_name = "Trend Projection ▲"
            elif form_info.get("trend") == "declining":
                trend_name = "Trend Projection ▼"

            fig.add_trace(go.Scatter(
                x=[real_seasons[-1], next_season],
                y=[real_vals[-1], projected_val],
                mode="lines+markers",
                name=trend_name,
                line=dict(color=HKFATheme.ACCENT_RED, width=2, dash="dash"),
                marker=dict(size=10, symbol="star", color=HKFATheme.ACCENT_GOLD),
                hovertemplate=f"{next_season}<br>Projected: %{{y:.1f}}<extra></extra>",
            ))

        # ── TabPFN Transferability Score badge ────────────────────────────
        transferability_label = ""
        try:
            from ai_models.predictor import get_transferability_score
            career_dict = (
                history_df.drop(columns=["Season"], errors="ignore").mean().to_dict()
                if not history_df.empty else {}
            )
            t_result = get_transferability_score(career_dict, pos_group, player_id=player_id)
            score_pct = round(t_result.get("score", 0) * 100)
            t_label = t_result.get("label", "")
            transferability_label = f"Transferability: {score_pct}% ({t_label})"
        except Exception as te:
            logger.debug(f"Transferability score error: {te}")

        if transferability_label:
            fig.add_annotation(
                text=transferability_label,
                xref="paper", yref="paper",
                x=0.99, y=0.99,
                xanchor="right", yanchor="top",
                showarrow=False,
                bgcolor="rgba(0,212,255,0.12)",
                bordercolor=HKFATheme.ACCENT_BLUE,
                borderwidth=1,
                font=dict(color=HKFATheme.ACCENT_BLUE, size=11),
            )

        fig.update_layout(
            title=f"Performance Trend: {player_name}",
            xaxis_title="Season",
            yaxis_title=metric_label,
            hovermode="x unified",
        )
        return glass_figure_layout(fig)

    except Exception as e:
        logger.error(f"Projection chart error: {e}")
        fig = go.Figure()
        fig.add_annotation(text=f"Error: {str(e)}", showarrow=False)
        return glass_figure_layout(fig)
