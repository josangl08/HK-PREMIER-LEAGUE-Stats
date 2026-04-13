# ABOUTME: Helper functions for rendering Stage scenarios, AI widgets, and image gallery (Feature G).
# ABOUTME: Renders player dashboard (default), post-match (Doble Capa: High-Fidelity/Fallback), pre-match, career-insights, and Action Node gallery views.

import hashlib
import json
import logging
import os
import threading
import time
import copy
import html as _html_lib
import re
from datetime import timezone, timedelta
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
from utils.ai_services.evidence_router import (
    get_evidence_destination_meta,
    normalize_evidence_key,
    resolve_career_surface_evidence_key,
)
from utils.ai_services.llm_client import generate_gemini_content
from utils.ai_services.orchestration import parse_structured_json
from utils.ai_services.prompt_builders import build_career_narrative_prompt
from utils.ai_helpers import umap_scatter_chart, constellation_chart, _build_knn_edges
from data.processors.hong_kong_processor import POSITION_FULL_NAMES
from data.competition_registry import (
    get_competition_display_name,
    get_competition_logo,
    normalize_competition,
)
from utils.cache import cache
from utils.runtime_storage import PLAYER_CARDS_RUNTIME_ROOT, iter_player_cards_roots

# Numba/UMAP is not thread-safe with the default workqueue layer.
# This lock serializes concurrent calls to fit_umap across Flask threads.
_umap_lock = threading.Lock()
_dashboard_data_fetch_lock = threading.Lock()

logger = logging.getLogger(__name__)

_DASHBOARD_DATA_CACHE_VERSION = "v1"
_DASHBOARD_DATA_CACHE_TTL_SECONDS = 30
_CAREER_EVIDENCE_PREP_CACHE_VERSION = "v1"
_CAREER_EVIDENCE_PREP_CACHE_TTL_SECONDS = 60


def _build_dashboard_data_cache_key(player_name: str, player_id: str) -> str:
    return f"player-dashboard-data:{_DASHBOARD_DATA_CACHE_VERSION}:{player_id or 'unknown'}:{player_name or 'unknown'}"


def _get_cached_dashboard_data(player_name: str, player_id: str) -> Optional[Dict[str, Any]]:
    try:
        cached_payload = cache.get(_build_dashboard_data_cache_key(player_name, player_id))
        if isinstance(cached_payload, dict):
            return copy.deepcopy(cached_payload)
    except Exception:
        pass
    return None


def _set_cached_dashboard_data(player_name: str, player_id: str, payload: Dict[str, Any]) -> None:
    try:
        cache.set(
            _build_dashboard_data_cache_key(player_name, player_id),
            copy.deepcopy(payload),
            timeout=_DASHBOARD_DATA_CACHE_TTL_SECONDS,
        )
    except Exception:
        pass


def _build_career_evidence_prep_cache_key(player_name: str, player_id: str) -> str:
    return (
        f"career-evidence-prep:{_CAREER_EVIDENCE_PREP_CACHE_VERSION}:"
        f"{player_id or 'unknown'}:{player_name or 'unknown'}"
    )


def _get_cached_career_evidence_prep(player_name: str, player_id: str) -> Optional[Dict[str, Any]]:
    try:
        cached_payload = cache.get(_build_career_evidence_prep_cache_key(player_name, player_id))
        if isinstance(cached_payload, dict):
            return copy.deepcopy(cached_payload)
    except Exception:
        pass
    return None


def _set_cached_career_evidence_prep(player_name: str, player_id: str, payload: Dict[str, Any]) -> None:
    try:
        cache.set(
            _build_career_evidence_prep_cache_key(player_name, player_id),
            copy.deepcopy(payload),
            timeout=_CAREER_EVIDENCE_PREP_CACHE_TTL_SECONDS,
        )
    except Exception:
        pass


def _prepare_career_evidence_bundle(player_name: str, player_id: str) -> Dict[str, Any]:
    cached_bundle = _get_cached_career_evidence_prep(player_name, player_id)
    if cached_bundle is not None:
        return cached_bundle

    from utils.career_intelligence import (
        get_career_phase_data,
        get_career_signals,
        get_development_priorities,
    )
    from utils.domain_ai import build_career_intelligence_facts

    data = _fetch_dashboard_data(player_name, player_id)
    career_phase_data = get_career_phase_data(data, data.get("history_df", pd.DataFrame()))
    career_signals = get_career_signals(data, data.get("history_df", pd.DataFrame()), career_phase_data or {})
    development_priorities = get_development_priorities(data.get("percentiles_data") or {})
    career_facts = build_career_intelligence_facts(
        data,
        career_phase_data or {},
        career_signals,
        development_priorities,
    )
    bundle = {
        "data": data,
        "career_phase_data": career_phase_data or {},
        "career_signals": career_signals,
        "development_priorities": development_priorities,
        "career_facts": career_facts,
    }
    _set_cached_career_evidence_prep(player_name, player_id, bundle)
    return copy.deepcopy(bundle)

# In-process cache for Gemini career-insight calls.
# Key: (player_name, primary_metric) — reused across timeline navigation within the same session.
_career_insight_cache: dict[tuple, Optional[str]] = {}

# Disk cache for career insights — survives server restarts, TTL 2 weeks.
_INSIGHT_CACHE_DIR = Path("cache/career_insights")
_INSIGHT_CACHE_TTL = 60 * 60 * 24 * 14  # 14 days in seconds


def _insight_cache_path(player_name: str, primary_metric: str) -> Path:
    slug = hashlib.md5(f"{player_name}:{primary_metric}".encode()).hexdigest()[:12]
    return _INSIGHT_CACHE_DIR / f"{slug}.json"


def _read_insight_disk_cache(path: Path) -> Optional[str]:
    try:
        if not path.exists():
            return None
        data = json.loads(path.read_text("utf-8"))
        if time.time() - data.get("ts", 0) > _INSIGHT_CACHE_TTL:
            return None  # expired
        return data.get("insight")
    except Exception:
        return None


def _write_insight_disk_cache(path: Path, insight: str) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"ts": time.time(), "insight": insight}), "utf-8")
    except Exception:
        pass  # write failure is non-fatal


_COUNTRY_TO_ISO2 = {
    "argentina": "AR",
    "australia": "AU",
    "brazil": "BR",
    "brasil": "BR",
    "chile": "CL",
    "china": "CN",
    "colombia": "CO",
    "croatia": "HR",
    "england": "GB",
    "france": "FR",
    "germany": "DE",
    "ghana": "GH",
    "hong kong": "HK",
    "hong kong, china": "HK",
    "india": "IN",
    "indonesia": "ID",
    "iran": "IR",
    "italy": "IT",
    "japan": "JP",
    "korea republic": "KR",
    "south korea": "KR",
    "north korea": "KP",
    "macau": "MO",
    "malaysia": "MY",
    "mexico": "MX",
    "morocco": "MA",
    "netherlands": "NL",
    "nigeria": "NG",
    "norway": "NO",
    "paraguay": "PY",
    "philippines": "PH",
    "poland": "PL",
    "portugal": "PT",
    "russia": "RU",
    "scotland": "GB",
    "serbia": "RS",
    "singapore": "SG",
    "spain": "ES",
    "sweden": "SE",
    "switzerland": "CH",
    "taiwan": "TW",
    "thailand": "TH",
    "turkey": "TR",
    "ukraine": "UA",
    "united states": "US",
    "usa": "US",
    "uruguay": "UY",
    "venezuela": "VE",
    "vietnam": "VN",
    "wales": "GB",
}


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


def _normalize_season_label(season_value: Any) -> str:
    """Normalizes season identifiers to the canonical YYYY-YY display format when possible."""
    raw = str(season_value or "").strip()
    if not raw:
        return ""
    match = re.fullmatch(r"(\d{4})[-/](\d{2,4})", raw)
    if not match:
        return raw
    start_year = int(match.group(1))
    end_token = match.group(2)
    expected_short = f"{(start_year + 1) % 100:02d}"
    if len(end_token) == 4:
        end_year = int(end_token)
        if end_year not in {start_year, start_year + 1}:
            end_year = start_year + 1
        return f"{start_year}-{end_year % 100:02d}"
    if len(end_token) == 2:
        if end_token != expected_short:
            return f"{start_year}-{expected_short}"
        return f"{start_year}-{end_token}"
    return raw


def _season_sort_key(season_value: Any) -> tuple[int, int, str]:
    """Returns a stable sort key for season labels."""
    normalized = _normalize_season_label(season_value)
    match = re.fullmatch(r"(\d{4})-(\d{2})", normalized)
    if not match:
        return (-1, -1, normalized)
    return (int(match.group(1)), int(match.group(2)), normalized)


def _country_to_flag(country_name: Any) -> str:
    """Returns an emoji flag for a known country name; empty string if unknown."""
    value = str(country_name or "").strip().lower()
    if not value:
        return ""
    iso2 = _COUNTRY_TO_ISO2.get(value)
    if not iso2 or len(iso2) != 2:
        return ""
    return chr(ord(iso2[0]) + 127397) + chr(ord(iso2[1]) + 127397)


def _normalize_team_jersey_key(team_name: str) -> str:
    value = str(team_name or "").strip().lower()
    aliases = {
        "north dt.": "northdt",
        "north district": "northdt",
        "eastern district": "easterndt",
        "eastern dist.": "easterndt",
        "eastern": "eastern",
        "eastern aa": "eastern",
        "eastern sc": "eastern",
        "eastern long lions": "eastern",
        "eastern long lions fc": "eastern",
        "hkfc": "hkfc",
        "hong kong fc": "hkfc",
        "hong kong football club": "hkfc",
        "kitchee": "kitchee",
        "lee man": "leeman",
        "leeman": "leeman",
        "warriors": "leeman",
        "rangers": "rangers",
        "bc rangers": "rangers",
        "southern district": "southern",
        "southern": "southern",
        "tai po": "taipo",
        "tai po fc": "taipo",
        "wofoo tai po": "taipo",
        "wofoo tai po fc": "taipo",
        "resources capital": "rcfc",
        "resources capital fc": "rcfc",
        "rcfc": "rcfc",
        "r&f": "r_f",
        "cahn fc": "cahn_fc",
        "cahn": "cahn_fc",
        "công an hà nội": "cahn_fc",
        "cong an ha noi": "cahn_fc",
        "happy valley": "happy_valley",
        "happy valley aa": "happy_valley",
        "sham shui po": "sham_shui_po",
        "sham shui po aa": "sham_shui_po",
        "yuen long": "yuen_long",
        "yuen long fc": "yuen_long",
        "yueng long": "yuen_long",
        "taipei hang yuen": "hang_yuan_fc",
        "hang yuan": "hang_yuan_fc",
        "hang yuen fc": "hang_yuan_fc",
        "hang yuen": "hang_yuan_fc",
        "kaya iloilo": "kaya_fc",
        "kaya-iloilo": "kaya_fc",
        "kaya–iloilo": "kaya_fc",
        "kaya fc-iloilo": "kaya_fc",
        "kaya fc": "kaya_fc",
    }
    if value in aliases:
        return aliases[value]
    return re.sub(r"[^a-z0-9]+", "", value)


def _canonical_team_display_name(team_name: str) -> str:
    """Normalizes legacy/raw team names to the preferred display label."""
    value = str(team_name or "").strip()
    if not value:
        return value
    normalized_key = _normalize_team_jersey_key(value)
    display_aliases = {
        "leeman": "Lee Man",
        "northdt": "North District",
        "easterndt": "Eastern",
        "hkfc": "HKFC",
        "taipo": "Tai Po",
        "rcfc": "RCFC",
        "cahn_fc": "CAHN FC",
        "happy_valley": "Happy Valley",
        "sham_shui_po": "Sham Shui Po",
        "yuen_long": "Yuen Long",
        "hang_yuan_fc": "Taipei Hang Yuen",
        "kaya_fc": "Kaya–Iloilo",
    }
    return display_aliases.get(normalized_key, value)


def _resolve_team_jersey(team_name: str, variant: str = "home") -> str:
    key = _normalize_team_jersey_key(team_name)
    candidate = Path(f"assets/team_jersey/{key}_{variant}.png")
    return f"/{candidate.as_posix()}" if candidate.exists() else ""


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


def get_kpi_tooltip_text(metric: str, value: float, history_df: "pd.DataFrame") -> str:
    """
    Returns a one-sentence career-context tooltip for a KPI badge.

    Parameters
    ----------
    metric     : Column name (e.g. "Goals", "Key passes").
    value      : Current season value for the metric.
    history_df : DataFrame with season history (one row per season).

    Returns
    -------
    Human-readable string indicating career-high, career-low, or mid-range status.
    """
    try:
        if history_df is None or history_df.empty or metric not in history_df.columns:
            return f"{metric}: {value}"

        col = history_df[metric].dropna()
        if col.empty:
            return f"{metric}: {value}"

        career_max = col.max()
        career_min = col.min()
        n_seasons = len(col)

        if value >= career_max:
            return (
                f"{metric} más alto en {n_seasons} temporada{'s' if n_seasons != 1 else ''}. "
                "Estás en tu mejor nivel histórico."
            )
        elif value <= career_min:
            return (
                f"{metric} en su punto más bajo histórico. "
                "Área prioritaria de mejora esta temporada."
            )
        else:
            pct_rank = (value - career_min) / (career_max - career_min) * 100 if career_max != career_min else 50
            if pct_rank >= 66:
                return f"{metric} en rango alto de tu carrera ({value:.1f}). Mantén este nivel."
            elif pct_rank >= 33:
                return f"{metric} en rango medio de tu carrera ({value:.1f}). Margen de mejora disponible."
            else:
                return f"{metric} en rango bajo-medio de tu carrera ({value:.1f}). Oportunidad de crecimiento."
    except Exception:
        return f"{metric}: {value}"


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


_PLAYER_CARDS_ROOT = PLAYER_CARDS_RUNTIME_ROOT


def _resolve_team_logo(team_name: str) -> Optional[str]:
    """Resolve a team logo from local assets first, then from Team.logo_url in DB."""
    if not team_name:
        return None
    normalized_key = _normalize_team_jersey_key(team_name)
    candidate_keys = [normalized_key.lower().replace(" ", "_").replace("-", "_")]
    asset_aliases = {
        "leeman": ["lee_man"],
        "hkfc": ["hong_kong_football_club"],
        "northdt": ["north_district"],
        "easterndt": ["eastern_district"],
        "rcfc": ["resources_capital"],
        "cahn_fc": ["cahn_fc"],
        "southern": ["southern_district"],
        "taipo": ["tai_po"],
    }
    candidate_keys.extend(asset_aliases.get(normalized_key, []))
    for asset_key in candidate_keys:
        for ext in ("png", "svg"):
            candidate = Path(f"assets/team_logos/{asset_key}.{ext}")
            if candidate.exists():
                return f"/{candidate.as_posix()}"
    try:
        from models.db_models import Team
        from utils.db_engine import SessionFactory

        with SessionFactory() as session:
            team = session.execute(select(Team).where(Team.name == team_name)).scalars().first()
            alias_names = {
                "leeman": ["Lee Man"],
                "rangers": ["Rangers", "BC Rangers"],
                "hkfc": ["Hong Kong FC", "Hong Kong Football Club", "HKFC"],
                "eastern": ["Eastern", "Eastern AA", "Eastern SC", "Eastern Long Lions"],
                "easterndt": ["Eastern District", "Eastern Dist."],
                "northdt": ["North District", "North Dt."],
                "southern": ["Southern", "Southern District"],
                "taipo": ["Tai Po", "Tai Po FC"],
                "rcfc": ["Resources Capital", "Resources Capital FC", "RCFC"],
                "cahn_fc": ["CAHN FC", "CAHN", "Công An Hà Nội", "Cong An Ha Noi"],
                "happy_valley": ["Happy Valley", "Happy Valley AA"],
                "sham_shui_po": ["Sham Shui Po", "Sham Shui Po AA"],
                "yuen_long": ["Yuen Long", "Yuen Long FC", "Yueng Long"],
                "hang_yuan_fc": ["Taipei Hang Yuen", "Hang Yuan", "Hang Yuen FC", "Hang Yuen"],
                "kaya_fc": ["Kaya–Iloilo", "Kaya-Iloilo", "Kaya FC-Iloilo", "Kaya FC", "Kaya"],
            }.get(normalized_key, [])
            if (not team or not getattr(team, "logo_url", None)) and alias_names:
                alias_team = session.execute(select(Team).where(Team.name.in_(alias_names))).scalars().first()
                if alias_team and getattr(alias_team, "logo_url", None):
                    team = alias_team
            if team and getattr(team, "logo_url", None):
                return str(team.logo_url)
    except Exception:
        return None
    return None


def get_cached_image_path(milestone_id: str, player_id: str = "") -> Optional[str]:
    """
    Returns the path to a generated card for the given milestone ID.
    Prioritizes final_card from metadata.json, then looks for standard filenames.
    """
    if not milestone_id:
        return None
    try:
        cards_roots = iter_player_cards_roots()

        # 1. Try to find player_id if not provided
        if not player_id:
            try:
                from flask_login import current_user
                player_id = str(current_user.id) if current_user and current_user.is_authenticated else ""
            except Exception:
                player_id = ""

        if player_id:
            for cards_root in cards_roots:
                # 1. Try exact match
                milestone_dir = cards_root / player_id / milestone_id
                
                # 2. Try prefix match if no exact match (handles long slugified IDs vs simple folder names)
                if not milestone_dir.exists() and "-" in milestone_id:
                    # Try matching by date prefix: e.g. "pre-match-2026-04-12"
                    parts = milestone_id.split("-")
                    if len(parts) >= 3:
                        # type-YYYY-MM-DD (e.g. pre-match-2026-04-12)
                        prefix = "-".join(parts[:5])
                        parent_dir = cards_root / player_id
                        if parent_dir.exists():
                            for folder in parent_dir.glob(f"{prefix}*"):
                                if folder.is_dir():
                                    milestone_dir = folder
                                    break

                meta_path = milestone_dir / "metadata.json"
                if meta_path.exists():
                    with open(meta_path, "r") as f:
                        meta = json.load(f)
                        final = meta.get("final_card")
                        if final:
                            # 1. Check as absolute or relative to project root
                            p_root = Path(final)
                            if p_root.exists():
                                return str(p_root)
                            # 2. Check as relative to milestone folder
                            p_rel = milestone_dir / final
                            if p_rel.exists():
                                return str(p_rel)
                for candidate in sorted(milestone_dir.glob("card_*.*")):
                    if candidate.exists():
                        return str(candidate)

        # 2. Legacy/Global search
        for cards_root in cards_roots:
            for candidate in cards_root.glob(f"*/{milestone_id}/card_*.*"):
                if candidate.exists():
                    return str(candidate)

        # 3. Cache fallback
        for ext in (".png", ".jpg", ".jpeg", ".webp"):
            candidate = _CARD_CACHE_DIR / f"{milestone_id}{ext}"
            if candidate.exists():
                return str(candidate)
    except Exception as e:
        logger.debug(f"get_cached_image_path error for '{milestone_id}': {e}")
    return None


def render_image_gallery(image_path: Optional[str]) -> html.Div:
    """
    Returns a glassmorphic image gallery view for the Stage panel.
    Shows the image if path is valid, otherwise a graceful placeholder.
    Converts disk paths to base64 data URIs for browser display.
    """
    if image_path and os.path.isfile(image_path):
        try:
            import base64
            with open(image_path, "rb") as f:
                ext = Path(image_path).suffix.lower().replace(".", "")
                mime = f"image/{ext}" if ext != "jpg" else "image/jpeg"
                encoded = base64.b64encode(f.read()).decode()
                src = f"data:{mime};base64,{encoded}"
            
            content = html.Div(
                [
                    html.Div(
                        html.Img(
                            src=src,
                            className="img-fluid rounded",
                            style={"maxHeight": "500px", "objectFit": "contain", "boxShadow": "0 20px 40px rgba(0,0,0,0.4)"},
                        ),
                        className="text-center",
                    ),
                    html.Small(
                        "Matchday Card Finalized",
                        className="portal-text-muted d-block text-center mt-3 fw-bold",
                        style={"letterSpacing": "0.05em"}
                    ),
                ]
            )
        except Exception as e:
            logger.error(f"Error encoding image for gallery: {e}")
            content = html.Div(
                [
                    html.I(className="bi bi-exclamation-triangle text-warning", style={"fontSize": "3rem"}),
                    html.P("Error al cargar la imagen", className="text-muted mt-2 mb-0"),
                ],
                className="text-center py-4",
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
        className="stage-gallery-view p-3",
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
                    "Season": _normalize_season_label(stat_obj.season_id),
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
            # Sort by normalized season ascending.
            if not df.empty and "Season" in df.columns:
                df["Season"] = df["Season"].apply(_normalize_season_label)
                df = (
                    df.assign(_season_sort=df["Season"].apply(_season_sort_key))
                    .sort_values("_season_sort")
                    .drop(columns="_season_sort")
                    .reset_index(drop=True)
                )
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

        registry = ModelRegistry()
        km = registry.load("kmeans_overall_k5")
        if km is None:
            return html.Span()

        # LOAD metadata to sync features and avoid warnings
        reg_data = registry._load_registry()
        feature_cols_e = reg_data.get("kmeans_overall_k5", {}).get("latest", {}).get("features")

        dm_e = get_hong_kong_data_manager()
        df_e = dm_e.processed_data
        if df_e is None or df_e.empty:
            return html.Span()

        if not feature_cols_e:
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

    Results are cached in-process by (player_name, primary_metric) so repeated
    timeline navigation does not trigger redundant API calls.

    Args:
        history_df:       Multi-season history DataFrame.
        primary_metric:   Key metric to highlight (position-specific).
        player_name:      Player display name.
        pos_group:        Position group for contextual prompting.
        form_trend:       Output of ``get_form_trend`` (optional).
        transferability:  Output of ``get_transferability_score`` (optional).
    """
    cache_key = (player_name, primary_metric)

    # 1. In-memory cache (fastest, per-session)
    if cache_key in _career_insight_cache:
        return _career_insight_cache[cache_key]

    # 2. Disk cache (survives restarts, 2-week TTL)
    disk_path = _insight_cache_path(player_name, primary_metric)
    cached_on_disk = _read_insight_disk_cache(disk_path)
    if cached_on_disk is not None:
        _career_insight_cache[cache_key] = cached_on_disk
        return cached_on_disk

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
        # ── Build brief stats string ───────────────────────────────────────
        brief_stats = ""
        if not history_df.empty and primary_metric in history_df.columns:
            last3 = history_df.tail(3)
            parts = []
            for _, r in last3.iterrows():
                val = r.get(primary_metric, 0)
                parts.append(f"{r['Season']}: {val:.1f}")
            brief_stats = ", ".join(parts)

        prompt = build_career_narrative_prompt(
            player_name=player_name,
            position_group=pos_group,
            primary_metric=primary_metric,
            brief_stats=brief_stats,
            form_trend=form_trend,
            transferability=transferability,
        )
        raw_text = generate_gemini_content(
            prompt,
            temperature=0.6,
            max_output_tokens=300,
            response_mime_type="application/json",
        )
        if raw_text:
            structured = parse_structured_json(raw_text)
            if isinstance(structured, dict):
                result = structured.get("body", raw_text)
            else:
                logger.debug("_generate_career_insight: JSON parse failed, using raw text")
                result = raw_text
            _career_insight_cache[cache_key] = result
            _write_insight_disk_cache(disk_path, result)
            return result

    except Exception as e:
        logger.debug(f"_generate_career_insight Gemini error: {e}")

    fallback = _template_fallback()
    _career_insight_cache[cache_key] = fallback  # cache fallback too to avoid retry on every open
    if fallback:
        _write_insight_disk_cache(disk_path, fallback)
    return fallback


def _build_delta_kpis(
    current_row: pd.Series,
    prev_row: pd.Series,
    metrics: List[str],
    history_df: Optional["pd.DataFrame"] = None,
) -> html.Div:
    """
    Renders a row of compact KPI badges showing season-over-season deltas.
    Green arrow = improvement, red arrow = decline, neutral = no change.
    T3 tooltips are added when history_df is provided.
    """
    kpis = []
    for i, m in enumerate(metrics):
        curr = float(current_row.get(m) or 0)
        prev = float(prev_row.get(m) or 0)
        delta = curr - prev
        label = m.split(",")[0].split(" per")[0].strip()
        badge_id = f"kpi-badge-{i}-{label.lower().replace(' ', '-')}"

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

        badge = html.Div(
            id=badge_id,
            children=[
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
                "cursor": "default",
            },
        )
        kpis.append(badge)

        # T3 Tooltip — static text generated at render time, no callback required
        if history_df is not None and not history_df.empty:
            tooltip_text = get_kpi_tooltip_text(m, curr, history_df)
            kpis.append(
                dbc.Tooltip(
                    tooltip_text,
                    target=badge_id,
                    placement="top",
                    className="ai-tooltip-dark",
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


def _render_rating_sparkline(
    ratings: List[float],
    *,
    width: int = 80,
    height: int = 24,
    color: str = HKFATheme.POSITIVE,
    show_label: bool = True,
) -> html.Div:
    """Renders a small sparkline of ratings (0-10) using CSS/HTML for maximum speed."""
    if not ratings:
        return html.Div("—", className="text-muted small")
    
    return html.Div([
        html.Div([
            html.Small("Recent Trend", className="postmatch-sparkline-label", title="Rating trend from the last 5 matches") if show_label else None,
            html.Img(
                src=f"data:image/svg+xml;base64,{_build_sparkline_svg(ratings, width=width, height=height, color=color)}",
                className="postmatch-sparkline-img",
                style={"width": f"{width}px", "height": f"{height}px", "display": "block"},
            )
        ])
    ], className="postmatch-trend-sparkline d-inline-block")

def _build_sparkline_svg(ratings: List[float], *, width: int = 80, height: int = 24, color: str = HKFATheme.POSITIVE) -> str:
    import base64
    max_r = 10.0
    if len(ratings) < 2:
        return ""
    
    points = []
    for i, r in enumerate(ratings):
        x = (i / (len(ratings) - 1)) * width
        y = height - (r / max_r) * height
        points.append(f"{x},{y}")
    
    path = " ".join(points)
    svg = f'<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg"><polyline points="{path}" fill="none" stroke="{color}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/></svg>'
    return base64.b64encode(svg.encode('utf-8')).decode('utf-8')

def _render_pre_match_cta(pre_match_id: str, pre_match_card_path: Optional[str]) -> Optional[html.Div]:
    """Renders a call-to-action button to view the pre-game card if it exists."""
    if not pre_match_card_path:
        return None
    return html.Div(
        [
            html.Div(
                [
                    html.I(className="bi bi-eye me-2", style={"fontSize": "1rem"}),
                    html.Span("Ver Card de Pre-Partido", style={"fontWeight": "600"}),
                ],
                id={"type": "action-node-pill", "index": pre_match_id},
                className="action-node-pill action-node-pill--prematch",
                style={
                    "display": "inline-flex",
                    "alignItems": "center",
                    "padding": "8px 16px",
                    "borderRadius": "30px",
                    "background": "rgba(0, 212, 255, 0.15)",
                    "border": "1px solid var(--accent-cyan)",
                    "color": "var(--accent-cyan)",
                    "cursor": "pointer",
                    "marginBottom": "20px",
                    "transition": "all 0.2s ease-in-out",
                },
            )
        ],
        className="d-flex justify-content-center w-100"
    )

def render_post_match(payload: Dict[str, Any], milestone_id: str = "") -> html.Div:
    """
    Renders the Post-Match analysis stage.
    Implements Double Layer logic: High-Fidelity (A) or Fallback (B) layout.
    """
    opponent = payload.get("opponent", "Opponent")

    date_str = payload.get("kickoff_display") or str(payload.get("date", ""))[:10]
    home = payload.get("home_team", "")
    away = payload.get("away_team", "")
    result = payload.get("result", "—")
    stadium = payload.get("stadium", "")
    competition = payload.get("competition", "HK Premier League")
    competition_display = get_competition_display_name(competition, long_form=True)
    competition_logo = payload.get("competition_logo") or get_competition_logo(competition)
    
    home_logo = payload.get("home_logo") or _resolve_team_logo(home)
    away_logo = payload.get("away_logo") or _resolve_team_logo(away)
    
    player_stats = payload.get("player_stats") or {}
    intel_meta = payload.get("intelligence_meta", {})
    is_high_fidelity = intel_meta.get("is_high_fidelity", False)

    _MATCH_POSITION_MAP = {
        "CEN": "CB",
        "ED": "RW",
        "EI": "LW",
        "ID": "RM",
        "II": "LM",
        "MCO": "AMF",
        "CMF": "CM",
        "DMF": "DM",
    }

    def _format_trend_label(ratings: List[float]) -> str:
        if len(ratings) < 2:
            return "→"
        delta = ratings[-1] - ratings[0]
        if delta > 0.15:
            return "↑"
        if delta < -0.15:
            return "↓"
        return "→"

    def _trend_accent(ratings: List[float]) -> str:
        trend = _format_trend_label(ratings)
        if trend == "↑":
            return HKFATheme.POSITIVE
        if trend == "↓":
            return HKFATheme.NEGATIVE
        return HKFATheme.ACCENT_GOLD

    def _safe_float(value: Any) -> Optional[float]:
        try:
            if value in (None, ""):
                return None
            return float(value)
        except (TypeError, ValueError):
            return None

    # High-Fidelity rating colors (for internal badges)
    rating = payload.get("rating") or player_stats.get("performance_stats", {}).get("rating")
    try:
        rating_val = float(rating) if rating is not None else None
    except (ValueError, TypeError):
        rating_val = None
    
    player_id_logged = _get_logged_in_player_id()
    basic = player_stats.get("basic_info", {})
    player_name = basic.get("name", "Player")
    try:
        dm = get_hong_kong_data_manager()
        enriched_player_stats = dm.get_player_statistics(player_name) if player_name else {}
        if isinstance(enriched_player_stats, dict) and not enriched_player_stats.get("error"):
            merged_player_stats = copy.deepcopy(enriched_player_stats)
            merged_basic = merged_player_stats.get("basic_info") or {}
            merged_basic.update(player_stats.get("basic_info") or {})
            merged_player_stats["basic_info"] = merged_basic
            for key, value in (player_stats or {}).items():
                if key == "basic_info":
                    continue
                if value:
                    merged_player_stats[key] = value
            player_stats = merged_player_stats
            basic = player_stats.get("basic_info", {})
    except Exception as exc:
        logger.debug(f"render_post_match player_stats enrichment error: {exc}")

    raw_position = payload.get("position") or basic.get("position_primary", basic.get("position", ""))
    normalized_position = _MATCH_POSITION_MAP.get(str(raw_position or "").strip().upper(), str(raw_position or "").strip().upper())
    position = normalized_position or raw_position
    position_display = POSITION_FULL_NAMES.get(str(position or "").upper(), str(raw_position or "Unknown"))

    dashboard_data: Dict[str, Any] = {}
    try:
        if player_name and player_id_logged:
            dashboard_data = _fetch_dashboard_data(player_name, player_id_logged)
    except Exception as exc:
        logger.debug(f"render_post_match dashboard enrichment error: {exc}")

    # ── Sparkline: recent rating trend from raw_data ───────────────────────
    sparkline_el = None
    contribution_sparkline_el = None
    recent_ratings: List[float] = list(payload.get("recent_ratings") or [])[:5]
    recent_contributions: List[float] = []
    try:
        from models.db_models import MatchHistory as _MH
        from utils.db_engine import SessionFactory as _SF
        if player_id_logged:
            with _SF() as _sess:
                recent_matches = (
                    _sess.query(_MH)
                    .filter(_MH.player_id == player_id_logged, _MH.raw_data.isnot(None))
                    .order_by(_MH.date.desc())
                    .limit(12)
                    .all()
                )
            recent_ratings = []
            recent_contributions = []
            for _m in recent_matches:
                _raw = _m.raw_data or {}
                _r = _raw.get("besoccer_rating") or _raw.get("rating") or _raw.get("sofascore_rating")
                if _r is not None:
                    try:
                        recent_ratings.append(float(_r))
                    except (ValueError, TypeError):
                        pass
                try:
                    recent_contributions.append(float(_m.goals or 0) + float(_m.assists or 0))
                except (ValueError, TypeError):
                    recent_contributions.append(0.0)
                if len(recent_ratings) >= 5 and len(recent_contributions) >= 5:
                    break
            if recent_ratings:
                recent_ratings = list(reversed(recent_ratings[:5]))
                sparkline_el = _render_rating_sparkline(recent_ratings, width=136, height=40, color=_trend_accent(recent_ratings), show_label=False)
            if recent_contributions:
                recent_contributions = list(reversed(recent_contributions[:5]))
                contribution_sparkline_el = _render_rating_sparkline(
                    recent_contributions,
                    width=136,
                    height=40,
                    color=HKFATheme.ACCENT_BLUE,
                    show_label=False,
                )
    except Exception:
        pass

    # ── RICH HEADER (Common for both Scenarios) ──────────────────────
    home_jersey = _resolve_team_jersey(home, "home")
    away_jersey = _resolve_team_jersey(away, "home")

    def _team_block_post(name: str, logo: str, align: str, jersey: str = "") -> html.Div:
        justify = "flex-start" if align == "left" else "flex-end"
        crest_block = html.Div([
            html.Img(src=logo, style={"width": "96px", "height": "96px", "objectFit": "contain"}) if logo else html.Div(
                name[:2].upper(),
                style={
                    "width": "96px", "height": "96px", "borderRadius": "50%",
                    "display": "flex", "alignItems": "center", "justifyContent": "center",
                    "background": "rgba(255,255,255,0.08)", "color": "#f3f7fb", "fontWeight": "800",
                },
            ),
            html.Div(name or "TBC", style={"color": "#f4f8fc", "fontWeight": "700", "fontSize": "1.08rem", "textAlign": "center", "letterSpacing": "0.01em", "marginTop": "10px", "width": "96px"}),
        ], style={"display": "flex", "flexDirection": "column", "alignItems": "center", "justifyContent": "center"})
        return html.Div([
            html.Div([
                html.Img(src=jersey, style={"width": "90px", "height": "90px", "objectFit": "contain", "opacity": "0.98"}) if jersey and align == "right" else None,
                crest_block,
                html.Img(src=jersey, style={"width": "90px", "height": "90px", "objectFit": "contain", "opacity": "0.98"}) if jersey and align == "left" else None,
            ], style={"display": "flex", "justifyContent": justify, "alignItems": "flex-start", "gap": "16px"}),
        ], style={"flex": "0 1 240px", "minWidth": "210px", "maxWidth": "250px", "textAlign": "center", "display": "flex", "flexDirection": "column", "alignItems": "center"})

    # Extract broadcast metadata from payload (Copied from Pre-Match logic)
    streaming_url = _clean_url(payload.get("streaming_url") or "")
    stream_href = streaming_url if streaming_url and "facebook.com" not in streaming_url.lower() else ""
    has_var = bool(payload.get("has_var"))
    is_tv = bool(payload.get("is_tv"))
    broadcast_type = str(payload.get("broadcast_type") or "").strip()
    
    broadcast_chips: List[Any] = []
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

    def _lucide(name: str) -> html.I:
        return html.I(**{"data-lucide": name, "className": "lucide-inline-icon me-1"})

    def _card_icon(color: str, size: str = "18px", class_name: str = "") -> html.I:
        return html.I(
            **{"data-lucide": "rectangle-vertical"},
            className=class_name,
            style={"width": size, "height": size, "color": color, "opacity": "0.95", "lineHeight": "1"},
        )

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

    # Match date splitting logic (Mirrors Pre-Match format)
    time_display = date_str
    date_display = ""
    raw_kickoff = str(date_str or "").strip()
    if "·" in raw_kickoff:
        left, right = [part.strip() for part in raw_kickoff.split("·", 1)]
        date_display = left.replace(",", "").strip()
        time_display = right
    elif "," in raw_kickoff:
        left, right = [part.strip() for part in raw_kickoff.rsplit(",", 1)]
        date_display = left.replace(",", "").strip()
        time_display = right
    elif len(raw_kickoff) >= 16 and raw_kickoff[4] == "-" and raw_kickoff[7] == "-":
        date_display = raw_kickoff[:10]
        time_display = raw_kickoff[10:].strip()

    time_display = (
        str(time_display)
        .replace(" HKT", "")
        .replace("hkt", "")
        .replace(" HkT", "")
        .strip()
    )

    def _glass_card(
        children: Any,
        extra_style: Optional[Dict[str, Any]] = None,
        extra_class: str = "",
        clean_variant: bool = True,
    ) -> dbc.Card:
        base_style = {"position": "relative"}
        if extra_style:
            base_style.update(extra_style)
        class_name = "border-0 prematch-float-card"
        if clean_variant:
            class_name = f"{class_name} prematch-clean-card"
        if extra_class:
            class_name = f"{class_name} {extra_class}"
        return dbc.Card(children, className=class_name, style=base_style)

    header_right_chips: List[Any] = []
    started = payload.get("started")
    if started is True:
        header_right_chips.append(_chip("bi-play-fill", "Starter", HKFATheme.POSITIVE))
    elif started is False:
        header_right_chips.append(_chip("bi-arrow-repeat", "Substitute", HKFATheme.ACCENT_BLUE))
    if sub_in := payload.get("subbed_in"):
        header_right_chips.append(_chip("bi-box-arrow-in-right", f"In {sub_in}'", HKFATheme.POSITIVE))
    if sub_out := payload.get("subbed_out"):
        header_right_chips.append(_chip("bi-box-arrow-right", f"Out {sub_out}'", HKFATheme.ACCENT_GOLD))
    if (payload.get("yellow_cards") or 0) > 0:
        header_right_chips.append(_chip("bi-square-fill", f"{int(payload.get('yellow_cards') or 0)} Yellow", HKFATheme.ACCENT_GOLD))
    if (payload.get("red_cards") or 0) > 0:
        header_right_chips.append(_chip("bi-square-fill", f"{int(payload.get('red_cards') or 0)} Red", HKFATheme.NEGATIVE))

    header = _glass_card(dbc.CardBody([
        # Competition row
        html.Div([
            html.Img(src=competition_logo, style={"width": "54px", "height": "54px", "objectFit": "contain", "marginBottom": "8px"}) if competition_logo else None,
            html.Div(competition_display, style={"color": "#f6f8fb", "fontWeight": "700", "fontSize": "1.05rem"}),
        ], style={"display": "flex", "flexDirection": "column", "alignItems": "center", "marginBottom": "24px"}),
        
        # Scorers/Teams row
        html.Div([
            _team_block_post(home, home_logo, "right", home_jersey),
            html.Div([
                html.Div(result, style={"color": "#d7dee8", "fontSize": "2rem", "fontWeight": "800", "letterSpacing": "0.06em"}),
                html.Div("FINAL", style={"color": HKFATheme.POSITIVE, "fontWeight": "700", "fontSize": "0.82rem", "letterSpacing": "0.12em", "marginTop": "10px"}),
                html.Div(
                    date_display or raw_kickoff[:10],
                    style={
                        "color": _trend_accent(recent_ratings),
                        "fontWeight": "500",
                        "fontSize": "0.8rem",
                        "marginTop": "10px",
                        "letterSpacing": "0.03em",
                        "display": "block",
                        "lineHeight": "1.1",
                    },
                ),
            ], style={"flex": "0 0 250px", "display": "flex", "flexDirection": "column", "alignItems": "center", "justifyContent": "center", "textAlign": "center", "padding": "0 12px"}),
            _team_block_post(away, away_logo, "left", away_jersey),
        ], style={"display": "flex", "alignItems": "center", "justifyContent": "center", "gap": "28px", "flexWrap": "wrap"}),
        
        # Meta footer (Exact copy of Pre-Match footer layout)
        html.Hr(style={"borderColor": "rgba(255,255,255,0.14)", "margin": "20px 0 18px"}),
        html.Div([
            _chip("bi-geo-alt", stadium or "Stadium TBC", HKFATheme.POSITIVE),
            html.Div(
                [*broadcast_chips, *header_right_chips],
                style={"display": "flex", "gap": "10px", "flexWrap": "wrap", "justifyContent": "flex-end"},
            ),
        ], style={"display": "flex", "justifyContent": "space-between", "alignItems": "center", "gap": "12px", "flexWrap": "wrap"}),
    ]), extra_class="prematch-fixture-card", clean_variant=False)

    def _section_title(icon: str, title: str) -> html.Div:
        return html.Div(
            [
                html.I(className=f"bi {icon} me-2", style={"color": HKFATheme.POSITIVE}),
                html.Span(title, className="postmatch-section-title", style={"color": "#f4f8fc"}),
            ],
            className="postmatch-section-header mb-3",
        )

    def _build_kpi_card(
        label: str,
        value: str,
        accent: str,
        icon: Any = "bi-dot",
        secondary_lines: Optional[List[Any]] = None,
    ) -> dbc.Card:
        icon_node = (
            html.I(className=f"bi {icon} me-2", style={"color": accent})
            if isinstance(icon, str)
            else icon
        )
        return _glass_card(
            dbc.CardBody([
                html.Div([
                    icon_node,
                    html.Span(label, style={"color": "#c9d2de", "fontSize": "0.8rem", "fontWeight": "400"}),
                ], className="mb-2"),
                html.Div(value, style={"color": "#f4f8fc", "fontSize": "1.55rem", "fontWeight": "800", "lineHeight": "1.05"}),
                html.Div(
                    secondary_lines or [],
                    style={"display": "flex", "flexDirection": "column", "gap": "4px", "marginTop": "10px", "minHeight": "42px"},
                ) if secondary_lines else None,
            ]),
            extra_style={"height": "100%"},
        )

    def _build_recent_form_section(ratings: List[float]) -> Optional[html.Div]:
        if not ratings:
            return None
        seq = " -> ".join(f"{r:.1f}" for r in ratings)
        return html.Div(
            [
                _section_title("bi-graph-up-arrow", "Tendencia de Forma"),
                html.Div("Tus ultimos 5 ratings", className="portal-text-muted small mb-2"),
                html.Div(
                    [
                        sparkline_el if sparkline_el else None,
                        html.Div(
                            [
                                html.Div(seq, style={"color": "#f4f8fc", "fontWeight": "600", "fontSize": "0.9rem"}),
                                html.Div(f"Tendencia: {_format_trend_label(ratings)}", style={"color": HKFATheme.POSITIVE, "fontSize": "0.8rem", "marginTop": "6px"}),
                            ],
                            style={"display": "flex", "flexDirection": "column", "gap": "2px"},
                        ),
                    ],
                    style={"display": "flex", "alignItems": "center", "gap": "14px", "flexWrap": "wrap"},
                ),
            ],
            className="p-4 mt-0",
        )

    # ── Common match summary block ──────────────────────────────────────────
    mins = int(payload.get("minutes_played") or 0)
    goals = int(payload.get("goals") or 0)
    assists = int(payload.get("assists") or 0)
    match_stats = payload.get("match_stats", {}) or {}
    own_goals = int(payload.get("own_goals") or 0)
    yc = int(payload.get("yellow_cards") or 0)
    rc = int(payload.get("red_cards") or 0)
    sub_in = payload.get("subbed_in")
    sub_out = payload.get("subbed_out")
    absence_reason = payload.get("absence_reason")

    performance_badge = None
    avg_minutes = None
    avg_goals = None
    avg_assists = None
    badge_text = None
    badge_color = HKFATheme.ACCENT_GOLD
    if rating_val is not None:
        if rating_val >= 8.5:
            badge_text, badge_color = "Outstanding Performance", HKFATheme.ACCENT_GOLD
        elif rating_val >= 7.5:
            badge_text, badge_color = "Strong Performance", HKFATheme.POSITIVE
        elif rating_val >= 7.0:
            badge_text, badge_color = "Solid Performance", HKFATheme.ACCENT_BLUE
        elif rating_val < 6.0:
            badge_text, badge_color = "Below-Par Performance", HKFATheme.NEGATIVE

    if badge_text:
        performance_badge = html.Div(
            [
                html.I(className="bi bi-activity me-1", style={"fontSize": "0.82rem"}),
                html.Span(badge_text, style={"fontSize": "0.82rem", "fontWeight": "600"}),
            ],
            style={
                "display": "inline-flex",
                "alignItems": "center",
                "padding": "5px 11px",
                "borderRadius": "20px",
                "background": f"rgba({_hex_to_rgb(badge_color)}, 0.15)",
                "border": f"1px solid {badge_color}",
                "color": badge_color,
            },
        )
    try:
        dm = get_hong_kong_data_manager()
        df = dm.processed_data
        if df is not None and player_name in df["Player"].values:
            p_row = df[df["Player"] == player_name].iloc[0]
            matches = float(p_row.get("Matches played") or 1) or 1
            avg_minutes = float(p_row.get("Minutes played") or 0) / matches
            season_goals = float(p_row.get("Goals") or 0)
            season_assists = float(p_row.get("Assists") or 0)
            avg_goals = season_goals / matches
            avg_assists = season_assists / matches
    except Exception as e:
        logger.debug(f"render_post_match enrichment error: {e}")

    summary_children: List[Any] = [_section_title("bi-activity", "Match Performance")]
    if mins > 0:
        summary_meta_nodes: List[Any] = []
        if performance_badge:
            summary_meta_nodes.append(performance_badge)
        summary_meta_nodes.append(
            html.Span(
                position_display,
                style={
                    "display": "inline-flex",
                    "alignItems": "center",
                    "padding": "6px 10px",
                    "borderRadius": "999px",
                    "background": f"rgba({_hex_to_rgb(HKFATheme.POSITIVE)}, 0.12)",
                    "border": f"1px solid rgba({_hex_to_rgb(HKFATheme.POSITIVE)}, 0.28)",
                    "color": "#eef4fa",
                    "fontSize": "0.78rem",
                    "fontWeight": "500",
                },
            )
        )
        summary_children.append(
            html.Div(
                summary_meta_nodes,
                style={"display": "flex", "alignItems": "center", "gap": "14px", "flexWrap": "wrap", "marginBottom": "20px"},
            )
        )
        pass_accuracy = None
        total_pass = _safe_float(match_stats.get("totalPass"))
        accurate_pass = _safe_float(match_stats.get("accuratePass"))
        if accurate_pass is not None and total_pass not in (None, 0):
            pass_accuracy = (accurate_pass / total_pass) * 100.0
        possession_lost = _safe_float(match_stats.get("possessionLostCtrl"))
        duel_won = _safe_float(match_stats.get("duelWon"))
        duel_lost = _safe_float(match_stats.get("duelLost"))
        trend_ratings = list(recent_ratings[:5])
        trend_color = _trend_accent(trend_ratings) if trend_ratings else HKFATheme.TEXT_SECONDARY

        def _vs_avg_line(current: Optional[float], average: Optional[float], suffix: str = "") -> Optional[html.Div]:
            if current is None or average is None:
                return None
            delta = current - average
            if delta > 0.05:
                clr = HKFATheme.POSITIVE
                arr = "↑"
            elif delta < -0.05:
                clr = HKFATheme.NEGATIVE
                arr = "↓"
            else:
                clr = HKFATheme.ACCENT_GOLD
                arr = "→"
            return html.Div(
                [
                    html.Span("Vs Avg. ", style={"color": HKFATheme.TEXT_SECONDARY}),
                    html.Span(f"{average:.1f}{suffix} {arr}", style={"color": clr}),
                ],
                style={"fontSize": "0.82rem", "fontWeight": "600"},
            )

        kpi_cards = [
            html.Div(_build_kpi_card("Minutes", f"{mins}'", "#b7c2d1", icon="bi-stopwatch", secondary_lines=[_vs_avg_line(float(mins), avg_minutes)]), style={"flex": "1 1 150px"}),
            html.Div(_build_kpi_card("Goals", str(goals), HKFATheme.ACCENT_RED, html.Img(src="/assets/icons/soccer-ball.svg", style={"width": "20px", "height": "20px", "objectFit": "contain", "marginRight": "8px"}), secondary_lines=[_vs_avg_line(float(goals), avg_goals)]), style={"flex": "1 1 150px"}),
            html.Div(_build_kpi_card("Assists", str(assists), HKFATheme.ACCENT_BLUE, html.I(**{"data-lucide": "sport-shoe", "className": "lucide-inline-icon rival-assist-icon me-2", "style": {"color": HKFATheme.ACCENT_BLUE, "width": "20px", "height": "20px"}}), secondary_lines=[_vs_avg_line(float(assists), avg_assists)]), style={"flex": "1 1 150px"}),
            html.Div(_build_kpi_card("Rating", f"{rating_val:.1f}" if rating_val is not None else "—", HKFATheme.ACCENT_GOLD, "bi-star-fill", secondary_lines=[
                html.Div(f"Trend {_format_trend_label(trend_ratings)}", style={"color": trend_color, "fontSize": "0.82rem", "fontWeight": "700"}) if trend_ratings else None,
                html.Div(" / ".join(f"{r:.1f}" for r in trend_ratings), style={"color": HKFATheme.TEXT_SECONDARY, "fontSize": "0.78rem", "fontWeight": "600"}) if trend_ratings else None,
            ]), style={"flex": "1 1 170px"}),
        ]
        if is_high_fidelity:
            kpi_cards.extend([
                html.Div(_build_kpi_card("Pass Accuracy", f"{pass_accuracy:.0f}%" if pass_accuracy is not None else "—", HKFATheme.ACCENT_BLUE, "bi-arrow-left-right", secondary_lines=[html.Div(f"Possession Lost {possession_lost:.0f}" if possession_lost is not None else "Possession Lost —", style={"color": HKFATheme.TEXT_SECONDARY, "fontSize": "0.82rem", "fontWeight": "600"})]), style={"flex": "1 1 150px"}),
                html.Div(_build_kpi_card("Duels Won", f"{duel_won:.0f}" if duel_won is not None else "—", HKFATheme.POSITIVE, "bi-shield-check", secondary_lines=[html.Div(f"Duels Lost {duel_lost:.0f}" if duel_lost is not None else "Duels Lost —", style={"color": HKFATheme.TEXT_SECONDARY, "fontSize": "0.82rem", "fontWeight": "600"})]), style={"flex": "1 1 150px"}),
            ])
        if own_goals > 0:
            kpi_cards.append(
                html.Div(
                    _build_kpi_card("Own Goals", str(own_goals), HKFATheme.NEGATIVE, "bi-exclamation-triangle"),
                    style={"flex": "1 1 150px"},
                )
            )
        summary_children.append(
            html.Div(
                kpi_cards,
                style={"display": "flex", "gap": "12px", "flexWrap": "wrap", "marginBottom": "14px", "marginTop": "8px"},
            )
        )
    else:
        _absence_labels = {
            "No convocado": ("secondary", "Not Summoned"),
            "not_summoned": ("secondary", "Not Summoned"),
            "Lesionado": ("warning", "Injury"),
            "injured": ("warning", "Injury"),
            "Suspendido": ("danger", "Suspension"),
            "suspended": ("danger", "Suspension"),
            "Banquillo": ("info", "Bench (Unused)"),
            "bench": ("info", "Bench (Unused)"),
            "No jugado": ("danger", "Did Not Play"),
            "No jugo": ("danger", "Did Not Play"),
            "Not played": ("danger", "Did Not Play"),
            "not_played": ("danger", "Did Not Play"),
        }
        badge_color, badge_label = _absence_labels.get(absence_reason or "No jugado", ("danger", "Did Not Play"))
        summary_children.append(
            html.Div(
                [
                    html.I(className="bi bi-person-x me-2", style={"color": "#f4f8fc"}),
                    dbc.Badge(badge_label, color=badge_color, className="text-white"),
                ],
                className="d-flex align-items-center",
            )
        )
    summary_section = html.Div(summary_children, className="mb-3")

    # ── Season profile radar + percentiles (reuse dashboard logic) ──────────
    dm_f = get_hong_kong_data_manager()
    pos_group = dashboard_data.get("pos_group") or _get_position_group(player_name, dm_f)
    percentiles_all = dashboard_data.get("percentiles_data") or {}
    perf_stats = player_stats.get("performance_stats", {}) or {}
    if not percentiles_all:
        fallback_percentiles = {
            "Goals": {"percentile": 100 if goals >= 2 else 80 if goals == 1 else 35, "group_avg_percentile": 50},
            "Assists": {"percentile": 100 if assists >= 2 else 80 if assists == 1 else 35, "group_avg_percentile": 50},
            "Accurate passes, %": {"percentile": float(perf_stats.get("pass_accuracy") or perf_stats.get("accurate_passes_pct") or 50), "group_avg_percentile": 50},
            "Minutes played": {"percentile": min(100, round((mins / 90) * 100, 1)) if mins else 0, "group_avg_percentile": 50},
        }
        percentiles_all = fallback_percentiles

    pos_radar = [m for m in POSITION_METRICS.get(pos_group, []) if m in percentiles_all]
    supplemental = [m for m in SUPPLEMENTAL_RADAR_METRICS.get(pos_group, []) if m in percentiles_all and m not in pos_radar]
    radar_metrics = (pos_radar + supplemental)[:5]
    if len(radar_metrics) < 3:
        radar_metrics = list(percentiles_all.keys())[:4]

    radar_values = []
    reference_values = []
    radar_labels = []
    percentile_display = {}
    for metric in radar_metrics:
        metric_data = percentiles_all.get(metric) or {}
        if isinstance(metric_data, dict):
            pct = float(metric_data.get("percentile", 0) or 0)
            ref = float(metric_data.get("group_avg_percentile", 50) or 50)
        else:
            pct = float(metric_data or 0)
            ref = 50.0
        radar_values.append(pct)
        reference_values.append(ref)
        radar_labels.append(metric.split(",")[0].split(" per")[0].strip())
        percentile_display[metric] = metric_data

    from utils.chart_helpers import create_radar_chart, create_percentile_bars
    radar_fig = glass_figure_layout(create_radar_chart(
        values=radar_values,
        metrics=radar_labels,
        title="",
        name=player_name,
        reference_values=reference_values if len(reference_values) == len(radar_values) else None,
        reference_name="Position Avg",
    ))
    radar_fig.update_layout(
        polar=dict(domain=dict(x=[0.03, 0.97], y=[0.08, 0.98])),
        legend=dict(orientation="h", yanchor="top", y=-0.08, xanchor="center", x=0.5, font=dict(size=9)),
        margin=dict(l=8, r=8, t=28, b=38),
    )

    def _format_match_metric(metric_key: str, metric_value: Any) -> Optional[str]:
        value = _safe_float(metric_value)
        if value is None:
            return None
        if metric_key.endswith("_pct"):
            return f"{value:.0f}%"
        if metric_key in {"accurate_passes", "touches", "recoveries", "interceptions", "clearances", "tackles", "aerials_won", "ball_carries", "progressive_distance"}:
            return f"{value:.0f}"
        if value.is_integer():
            return f"{int(value)}"
        return f"{value:.1f}"

    def _derive_match_insights(stats: Dict[str, Any], group: str) -> List[Dict[str, str]]:
        accurate_passes = _safe_float(stats.get("accuratePass"))
        total_passes = _safe_float(stats.get("totalPass"))
        duel_won = _safe_float(stats.get("duelWon"))
        duel_lost = _safe_float(stats.get("duelLost"))
        total_duels = (duel_won or 0) + (duel_lost or 0)
        pass_pct = ((accurate_passes / total_passes) * 100.0) if accurate_passes is not None and total_passes not in (None, 0) else None
        duel_pct = ((duel_won / total_duels) * 100.0) if duel_won is not None and total_duels > 0 else None

        derived = {
            "pass_pct": pass_pct,
            "duel_pct": duel_pct,
            "accurate_passes": accurate_passes,
            "total_passes": total_passes,
            "duels_won": duel_won,
            "duels_lost": duel_lost,
            "touches": stats.get("touches"),
            "recoveries": stats.get("ballRecovery"),
            "interceptions": stats.get("interceptionWon"),
            "clearances": stats.get("totalClearance"),
            "tackles": stats.get("totalTackle"),
            "aerials_won": stats.get("aerialWon"),
            "long_balls": stats.get("accurateLongBalls"),
            "long_balls_total": stats.get("totalLongBalls"),
            "ball_carries": stats.get("ballCarriesCount"),
            "progressive_distance": stats.get("totalProgression"),
            "shots": stats.get("totalShots"),
            "fouls": stats.get("fouls"),
            "outfielder_blocks": stats.get("outfielderBlock"),
            "own_half_passes": stats.get("accurateOwnHalfPasses"),
            "opp_half_passes": stats.get("totalOppositionHalfPasses"),
            "own_half_passes_total": stats.get("totalOwnHalfPasses"),
            "carry_distance": stats.get("totalBallCarriesDistance"),
            "best_carry_progression": stats.get("bestBallCarryProgression"),
            "pass_value": stats.get("passValueNormalized"),
            "dribble_value": stats.get("dribbleValueNormalized"),
            "defensive_value": stats.get("defensiveValueNormalized"),
            "rating": stats.get("rating"),
            "possession_lost": stats.get("possessionLostCtrl"),
        }
        label_map = {
            "pass_pct": "Pass Accuracy",
            "duel_pct": "Duels Won %",
            "accurate_passes": "Accurate Passes",
            "total_passes": "Total Passes",
            "duels_won": "Duels Won",
            "duels_lost": "Duels Lost",
            "touches": "Touches",
            "recoveries": "Recoveries",
            "interceptions": "Interceptions",
            "clearances": "Clearances",
            "tackles": "Tackles",
            "aerials_won": "Aerials Won",
            "long_balls": "Accurate Long Balls",
            "long_balls_total": "Total Long Balls",
            "ball_carries": "Ball Carries",
            "progressive_distance": "Progressive Distance",
            "shots": "Shots",
            "fouls": "Fouls",
            "outfielder_blocks": "Blocks",
            "own_half_passes": "Own Half Passes",
            "opp_half_passes": "Opp. Half Passes",
            "own_half_passes_total": "Own Half Total Passes",
            "carry_distance": "Carry Distance",
            "best_carry_progression": "Best Carry Progression",
            "pass_value": "Pass Value",
            "dribble_value": "Dribble Value",
            "defensive_value": "Defensive Value",
            "rating": "Rating",
            "possession_lost": "Possession Lost",
        }
        insights: List[Dict[str, str]] = []
        for key, value in derived.items():
            formatted = _format_match_metric(key, value)
            if formatted is None:
                continue
            insights.append({"label": label_map.get(key, key.replace("_", " ").title()), "value": formatted})
        return insights

    match_insights = _derive_match_insights(match_stats, pos_group)

    def _normalize_to_100(value: Optional[float], cap: float) -> Optional[float]:
        if value is None or cap <= 0:
            return None
        return max(0.0, min(100.0, (value / cap) * 100.0))

    def _normalize_signed_value(value: Optional[float]) -> Optional[float]:
        if value is None:
            return None
        return max(0.0, min(100.0, (value + 1.0) * 50.0))

    def _build_advanced_metric_pool(stats: Dict[str, Any], group: str) -> Dict[str, Dict[str, Any]]:
        accurate_passes = _safe_float(stats.get("accuratePass"))
        total_passes = _safe_float(stats.get("totalPass"))
        duel_won = _safe_float(stats.get("duelWon"))
        duel_lost = _safe_float(stats.get("duelLost"))
        total_duels = (duel_won or 0) + (duel_lost or 0)
        pass_pct = ((accurate_passes / total_passes) * 100.0) if accurate_passes is not None and total_passes not in (None, 0) else None
        duel_pct = ((duel_won / total_duels) * 100.0) if duel_won is not None and total_duels > 0 else None

        raw_pool: Dict[str, Dict[str, Any]] = {
            "Defensive Value": {"value": _safe_float(stats.get("defensiveValueNormalized")), "normalized": _normalize_signed_value(_safe_float(stats.get("defensiveValueNormalized")))},
            "Dribble Value": {"value": _safe_float(stats.get("dribbleValueNormalized")), "normalized": _normalize_signed_value(_safe_float(stats.get("dribbleValueNormalized")))},
            "Pass Value": {"value": _safe_float(stats.get("passValueNormalized")), "normalized": _normalize_signed_value(_safe_float(stats.get("passValueNormalized")))},
            "Pass Accuracy": {"value": pass_pct, "normalized": pass_pct},
            "Duels Won %": {"value": duel_pct, "normalized": duel_pct},
            "Touches": {"value": _safe_float(stats.get("touches")), "normalized": _normalize_to_100(_safe_float(stats.get("touches")), 120)},
            "Recoveries": {"value": _safe_float(stats.get("ballRecovery")), "normalized": _normalize_to_100(_safe_float(stats.get("ballRecovery")), 16)},
            "Interceptions": {"value": _safe_float(stats.get("interceptionWon")), "normalized": _normalize_to_100(_safe_float(stats.get("interceptionWon")), 8)},
            "Clearances": {"value": _safe_float(stats.get("totalClearance")), "normalized": _normalize_to_100(_safe_float(stats.get("totalClearance")), 14)},
            "Tackles": {"value": _safe_float(stats.get("totalTackle")), "normalized": _normalize_to_100(_safe_float(stats.get("totalTackle")), 8)},
            "Aerials Won": {"value": _safe_float(stats.get("aerialWon")), "normalized": _normalize_to_100(_safe_float(stats.get("aerialWon")), 12)},
            "Accurate Long Balls": {"value": _safe_float(stats.get("accurateLongBalls")), "normalized": _normalize_to_100(_safe_float(stats.get("accurateLongBalls")), 14)},
            "Ball Carries": {"value": _safe_float(stats.get("ballCarriesCount")), "normalized": _normalize_to_100(_safe_float(stats.get("ballCarriesCount")), 20)},
            "Progressive Distance": {"value": _safe_float(stats.get("totalProgression")), "normalized": _normalize_to_100(_safe_float(stats.get("totalProgression")), 500)},
            "Shots": {"value": _safe_float(stats.get("totalShots")), "normalized": _normalize_to_100(_safe_float(stats.get("totalShots")), 8)},
            "Possession Lost": {"value": _safe_float(stats.get("possessionLostCtrl")), "normalized": _normalize_to_100(_safe_float(stats.get("possessionLostCtrl")), 30)},
            "Accurate Passes": {"value": accurate_passes, "normalized": _normalize_to_100(accurate_passes, 90)},
            "Total Passes": {"value": total_passes, "normalized": _normalize_to_100(total_passes, 110)},
            "Duels Won": {"value": duel_won, "normalized": _normalize_to_100(duel_won, 16)},
            "Duels Lost": {"value": duel_lost, "normalized": _normalize_to_100(duel_lost, 16)},
            "Total Long Balls": {"value": _safe_float(stats.get("totalLongBalls")), "normalized": _normalize_to_100(_safe_float(stats.get("totalLongBalls")), 18)},
            "Carry Distance": {"value": _safe_float(stats.get("totalBallCarriesDistance")), "normalized": _normalize_to_100(_safe_float(stats.get("totalBallCarriesDistance")), 900)},
            "Best Carry Progression": {"value": _safe_float(stats.get("bestBallCarryProgression")), "normalized": _normalize_to_100(_safe_float(stats.get("bestBallCarryProgression")), 120)},
            "Blocks": {"value": _safe_float(stats.get("outfielderBlock")), "normalized": _normalize_to_100(_safe_float(stats.get("outfielderBlock")), 6)},
            "Own Half Passes": {"value": _safe_float(stats.get("accurateOwnHalfPasses")), "normalized": _normalize_to_100(_safe_float(stats.get("accurateOwnHalfPasses")), 60)},
            "Opp. Half Passes": {"value": _safe_float(stats.get("totalOppositionHalfPasses")), "normalized": _normalize_to_100(_safe_float(stats.get("totalOppositionHalfPasses")), 45)},
            "Rating": {"value": _safe_float(stats.get("rating")), "normalized": _normalize_to_100(_safe_float(stats.get("rating")), 10)},
        }
        radar_pref = {
            "Defender": ["Defensive Value", "Dribble Value", "Pass Value", "Interceptions", "Clearances", "Tackles"],
            "Midfielder": ["Defensive Value", "Dribble Value", "Pass Value", "Touches", "Recoveries", "Progressive Distance"],
            "Winger": ["Defensive Value", "Dribble Value", "Pass Value", "Ball Carries", "Progressive Distance", "Shots"],
            "Forward": ["Defensive Value", "Dribble Value", "Pass Value", "Shots", "Ball Carries", "Aerials Won"],
        }
        bar_pref = {
            "Defender": ["Accurate Passes", "Total Passes", "Duels Won", "Duels Lost", "Aerials Won", "Accurate Long Balls", "Total Long Balls", "Blocks"],
            "Midfielder": ["Accurate Passes", "Total Passes", "Duels Won", "Duels Lost", "Accurate Long Balls", "Touches", "Recoveries", "Ball Carries"],
            "Winger": ["Accurate Passes", "Duels Won", "Duels Lost", "Touches", "Recoveries", "Ball Carries", "Shots", "Blocks"],
            "Forward": ["Accurate Passes", "Touches", "Duels Won", "Duels Lost", "Shots", "Ball Carries", "Aerials Won", "Blocks"],
        }
        return {
            "pool": raw_pool,
            "radar_labels": [label for label in radar_pref.get(group, radar_pref["Midfielder"]) if raw_pool.get(label, {}).get("normalized") is not None][:6],
            "bar_labels": [label for label in bar_pref.get(group, bar_pref["Midfielder"]) if raw_pool.get(label, {}).get("normalized") is not None],
        }

    advanced_metric_bundle = _build_advanced_metric_pool(match_stats, pos_group) if is_high_fidelity else {"pool": {}, "radar_labels": [], "bar_labels": []}
    advanced_pool = advanced_metric_bundle.get("pool", {})

    def _build_match_insights_card(insights: List[Dict[str, str]], heatmap_fig: Optional[go.Figure] = None) -> dbc.Card:
        if not insights:
            content: Any = html.Div("Advanced match stats not available.", style={"color": HKFATheme.TEXT_SECONDARY, "fontSize": "0.92rem"})
            arrow_row = None
        else:
            def _tile(item: Dict[str, str]) -> html.Div:
                return html.Div(
                    [
                        html.Span(item["label"], style={"color": HKFATheme.TEXT_SECONDARY, "fontSize": "0.76rem", "fontWeight": "600", "textTransform": "uppercase", "letterSpacing": "0.04em"}),
                        html.Span(item["value"], style={"color": "#f4f8fc", "fontSize": "1.08rem", "fontWeight": "800", "lineHeight": "1"}),
                    ],
                    style={
                        "display": "flex",
                        "flexDirection": "column",
                        "justifyContent": "space-between",
                        "alignItems": "flex-start",
                        "padding": "12px 12px 10px",
                        "border": "1px solid rgba(255,255,255,0.10)",
                        "borderRadius": "14px",
                        "background": "linear-gradient(180deg, rgba(110,212,126,0.10), rgba(255,255,255,0.03))",
                        "minHeight": "80px",
                        "gap": "8px",
                    },
                )

            arrow_row = html.Div(
                [
                    html.Div(
                        "→",
                        style={
                            "fontSize": "34px",
                            "fontWeight": "700",
                            "lineHeight": "1",
                            "color": "rgba(24, 33, 37, 0.95)",
                            "textAlign": "center",
                            "marginBottom": "6px",
                            "gridColumn": "span 2",
                        },
                        className="match-heatmap-arrow",
                    )
                ],
                style={"display": "grid", "gridTemplateColumns": "repeat(4, minmax(0, 1fr))", "gap": "14px"},
            )
            heatmap_panel = html.Div(
                [
                    dcc.Graph(
                        figure=heatmap_fig,
                        config={"displayModeBar": False, "responsive": True},
                        className="w-100",
                        responsive=True,
                        style={"width": "100%", "height": "230px"},
                    ) if heatmap_fig is not None else None,
                ],
                style={"gridColumn": "span 2", "gridRow": "span 2", "paddingTop": "0"},
            )

            content = html.Div(
                [heatmap_panel, *[_tile(item) for item in insights]],
                style={"display": "grid", "gridTemplateColumns": "repeat(4, minmax(0, 1fr))", "gap": "14px", "alignItems": "start", "paddingTop": "0"},
            )
        return _glass_card(
            dbc.CardBody([
                _section_title("bi-activity", "Match Heatmap & Insights"),
                arrow_row,
                content,
            ], className="p-4"),
            extra_style={"height": "100%", "width": "100%", "minHeight": "520px"},
        )
    recent_ratings = payload.get("recent_ratings") or []
    if not recent_ratings:
        recent_ratings = []
        try:
            from models.db_models import MatchHistory as _MH
            from utils.db_engine import SessionFactory as _SF
            player_id_logged = _get_logged_in_player_id()
            if player_id_logged:
                with _SF() as _sess:
                    recent_matches = (
                        _sess.query(_MH)
                        .filter(_MH.player_id == player_id_logged, _MH.raw_data.isnot(None))
                        .order_by(_MH.date.desc())
                        .limit(5)
                        .all()
                    )
                for _m in reversed(recent_matches):
                    _raw = _m.raw_data or {}
                    _r = _raw.get("besoccer_rating") or _raw.get("rating") or _raw.get("sofascore_rating")
                    if _r is not None:
                        try:
                            recent_ratings.append(float(_r))
                        except (ValueError, TypeError):
                            pass
        except Exception:
            recent_ratings = []

    analysis_cols: List[Any] = []
    if is_high_fidelity:
        from utils.chart_helpers import create_match_heatmap

        heatmap_data = payload.get("heatmap", [])
        heatmap_fig = create_match_heatmap(heatmap_data, height=240)
        advanced_radar_labels = advanced_metric_bundle.get("radar_labels", [])
        advanced_radar_values = [advanced_pool[label]["normalized"] for label in advanced_radar_labels if advanced_pool.get(label)]
        advanced_radar_raw = [advanced_pool[label]["value"] for label in advanced_radar_labels if advanced_pool.get(label)]
        radar_fig = glass_figure_layout(create_radar_chart(
            values=advanced_radar_values,
            metrics=advanced_radar_labels,
            title="",
            name="Match",
        ))
        radar_fig.update_layout(
            polar=dict(domain=dict(x=[0.03, 0.97], y=[0.08, 0.98])),
            legend=dict(orientation="h", yanchor="top", y=-0.08, xanchor="center", x=0.5, font=dict(size=9)),
            margin=dict(l=8, r=8, t=28, b=38),
        )

        kpi_labels = {"Minutes", "Goals", "Assists", "Pass Accuracy", "Duels Won", "Rating", "Duels Lost", "Possession Lost"}
        bar_dict: Dict[str, Any] = {}
        used_labels = set(advanced_radar_labels)
        for label in advanced_metric_bundle.get("bar_labels", []):
            if label in kpi_labels or label in used_labels:
                continue
            metric_entry = advanced_pool.get(label) or {}
            norm_val = metric_entry.get("normalized")
            raw_val = metric_entry.get("value")
            if norm_val is None or raw_val is None:
                continue
            bar_dict[label] = {"percentile": norm_val, "group_avg_percentile": 50}
            used_labels.add(label)

        remaining_insights = [item for item in match_insights if item["label"] not in used_labels and item["label"] not in kpi_labels]

        upper_analysis_cols = [
            dbc.Col(
                _glass_card(
                    dbc.CardBody([
                        _section_title("bi-broadcast", "Match Profile"),
                        dcc.Graph(figure=radar_fig, config={"displayModeBar": False, "responsive": True}, className="w-100", responsive=True, style={"width": "100%", "height": "340px"}),
                    ], className="p-4"),
                    extra_style={"height": "100%", "minHeight": "430px", "width": "100%"},
                ),
                width=12,
                md=6,
                className="d-flex",
            ),
            dbc.Col(
                _glass_card(
                    dbc.CardBody([
                        _section_title("bi-bar-chart-steps", "Match Metrics"),
                        create_percentile_bars(bar_dict),
                    ], className="p-4"),
                    extra_style={"height": "100%", "minHeight": "430px", "width": "100%"},
                ),
                width=12,
                md=6,
                className="d-flex",
            ),
        ]
        lower_analysis_cols = [
            dbc.Col(
                _build_match_insights_card(remaining_insights, heatmap_fig),
                width=12,
                className="d-flex",
            ),
        ]
    else:
        upper_analysis_cols = [
            dbc.Col(
                _glass_card(
                    dbc.CardBody([
                        _section_title("bi-broadcast", "Season Profile"),
                        dcc.Graph(
                            figure=radar_fig,
                            config={"displayModeBar": False, "responsive": True},
                            className="w-100",
                            responsive=True,
                            style={"width": "100%", "minWidth": "0", "height": "340px"},
                        ),
                    ], className="p-4"),
                    extra_style={"height": "100%", "minHeight": "430px", "width": "100%"},
                ),
                width=12,
                md=6,
                className="d-flex",
            ),
            dbc.Col(
                _glass_card(
                    dbc.CardBody([
                        _section_title("bi-bar-chart-steps", "Season Percentiles"),
                        create_percentile_bars(percentile_display),
                    ], className="p-4"),
                    extra_style={"height": "100%", "minHeight": "430px", "width": "100%"},
                ),
                width=12,
                md=6,
                className="d-flex",
            ),
        ]
        lower_analysis_cols = []

    return html.Div(
        [
            header,
            summary_section,
            dbc.Row(upper_analysis_cols, className="g-3 align-items-stretch"),
            dbc.Row(lower_analysis_cols, className="g-3 align-items-stretch mt-0") if lower_analysis_cols else None,
        ],
        className="stage-view stage-view--postmatch",
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


def _match_team_tokens(team_label: str, tokens: List[str]) -> bool:
    label_norm = _normalize_team_lookup(team_label)
    if not label_norm or not tokens:
        return False
    return any(token and token in label_norm for token in tokens)


def _parse_match_outcome(
    result_str: str,
    opponent_label: str,
    player_team: str,
    opponent_team_hint: str = "",
) -> str:
    score = str(result_str or "").strip().lower()
    if not score or ":" not in score:
        return "EMPTY"
    penalties = "pen" in score
    score_part = score.replace("pen.", "").replace("pen", "").strip()
    score_part = re.sub(r"\(\s*p\s*\)", "", score_part, flags=re.IGNORECASE).strip()
    score_part = re.sub(r"\(\s*pen(?:s|alties)?\s*\)", "", score_part, flags=re.IGNORECASE).strip()
    try:
        left, right = [int(x) for x in score_part.split(":", 1)]
    except Exception:
        return "EMPTY"

    parts = str(opponent_label or "").split(" vs ")
    if len(parts) != 2:
        return "EMPTY"
    home_team, away_team = parts[0].strip(), parts[1].strip()
    player_team_tokens = _team_lookup_tokens(player_team)
    opponent_team_tokens = _team_lookup_tokens(opponent_team_hint)

    is_home = _match_team_tokens(home_team, player_team_tokens)
    is_away = _match_team_tokens(away_team, player_team_tokens)

    if not is_home and not is_away and opponent_team_tokens:
        opponent_is_home = _match_team_tokens(home_team, opponent_team_tokens)
        opponent_is_away = _match_team_tokens(away_team, opponent_team_tokens)
        if opponent_is_home and not opponent_is_away:
            is_away = True
        elif opponent_is_away and not opponent_is_home:
            is_home = True

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


def _extract_outcome_from_result(
    result_str: Any,
    opponent_label: str = "",
    player_team: str = "",
    opponent_team_hint: str = "",
) -> str:
    raw = str(result_str or "").strip()
    if not raw:
        return "EMPTY"
    first = raw[:1].upper()
    if first in {"W", "D", "L"}:
        return first
    return _parse_match_outcome(raw, opponent_label, player_team, opponent_team_hint)


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


def _summarize_recent_match_window(matches: List[Any]) -> Dict[str, Any]:
    """Builds an aggregate recent-form summary from raw MatchHistory rows."""
    summary = {
        "matches": 0,
        "goals_total": 0,
        "assists_total": 0,
        "minutes_total": 0,
        "goal_contributions_total": 0,
    }
    if not matches:
        return summary

    for match in matches:
        goals = int(getattr(match, "goals", 0) or 0)
        assists = int(getattr(match, "assists", 0) or 0)
        minutes = int(getattr(match, "minutes_played", 0) or 0)
        summary["matches"] += 1
        summary["goals_total"] += goals
        summary["assists_total"] += assists
        summary["minutes_total"] += minutes
        summary["goal_contributions_total"] += goals + assists
    return summary


def _compute_window_delta_pct(current_total: float, previous_total: float) -> float:
    """Returns percentage delta between two rolling windows."""
    try:
        current_val = float(current_total)
        previous_val = float(previous_total)
    except (TypeError, ValueError):
        return 0.0
    if previous_val == 0:
        return 0.0
    return round(((current_val - previous_val) / abs(previous_val)) * 100.0, 2)


def _build_recent_form_windows(matches: List[Any]) -> Dict[str, Any]:
    """Builds recent form windows for last 5, previous 5, and last 10 comparisons."""
    latest_ten = list(matches[:10]) if matches else []
    latest_five = latest_ten[:5]
    previous_five = latest_ten[5:10]

    payload = {
        "last5": _summarize_recent_match_window(latest_five),
        "previous5": _summarize_recent_match_window(previous_five),
        "last10": _summarize_recent_match_window(latest_ten),
        "comparisons": {},
    }
    if len(latest_five) == 5 and len(previous_five) == 5:
        payload["comparisons"]["last5_vs_previous5"] = {
            "matches": 10,
            "minutes_trend_pct": _compute_window_delta_pct(
                payload["last5"]["minutes_total"],
                payload["previous5"]["minutes_total"],
            ),
            "goals_trend_pct": _compute_window_delta_pct(
                payload["last5"]["goals_total"],
                payload["previous5"]["goals_total"],
            ),
            "assists_trend_pct": _compute_window_delta_pct(
                payload["last5"]["assists_total"],
                payload["previous5"]["assists_total"],
            ),
            "goal_contributions_trend_pct": _compute_window_delta_pct(
                payload["last5"]["goal_contributions_total"],
                payload["previous5"]["goal_contributions_total"],
            ),
        }
    return payload


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


def _align_cluster_feature_frame(df: pd.DataFrame, feature_names: List[str]) -> pd.DataFrame:
    """Align cluster features to the model schema and coerce all values to numeric."""
    if not feature_names:
        return pd.DataFrame(index=df.index)

    aligned = df.copy()
    for feature_name in feature_names:
        if feature_name not in aligned.columns:
            aligned[feature_name] = 0.0

    return aligned[feature_names].apply(pd.to_numeric, errors="coerce").fillna(0.0)


_TEAM_NAME_ALIASES: Dict[str, List[str]] = {
    "north dt": ["north dt", "north district"],
    "north district": ["north district", "north dt"],
    "eastern dist": ["eastern dist", "eastern district"],
    "eastern district": ["eastern district", "eastern dist"],
    "hkfc": ["hkfc", "hong kong football club"],
    "hong kong football club": ["hong kong football club", "hkfc"],
}


def _normalize_team_lookup(value: str) -> str:
    cleaned = str(value or "").lower().strip()
    cleaned = cleaned.replace(".", "")
    cleaned = " ".join(cleaned.split())
    return cleaned


def _team_lookup_tokens(value: str) -> List[str]:
    normalized = _normalize_team_lookup(value)
    if not normalized:
        return []
    tokens = {normalized}
    for alias in _TEAM_NAME_ALIASES.get(normalized, []):
        alias_norm = _normalize_team_lookup(alias)
        if alias_norm:
            tokens.add(alias_norm)
    return list(tokens)


def _get_head_to_head_summary(player_id: str, opponent_team: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """Returns the player's matches against the current opponent."""
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

    opponent_tokens = _team_lookup_tokens(opponent_team)
    results: List[Dict[str, Any]] = []
    for match in matches:
        opponent_label = str(getattr(match, "opponent", "") or "")
        opponent_label_norm = _normalize_team_lookup(opponent_label)
        if opponent_tokens and not any(token in opponent_label_norm for token in opponent_tokens):
            continue
        raw_result = getattr(match, "result", "") or ""
        raw_data = getattr(match, "raw_data", None) or {}
        competition_name = getattr(match, "competition_name", None) or raw_data.get("competition") or ""
        competition_logo = getattr(match, "competition_logo", None) or raw_data.get("competition_logo") or ""
        subbed_in = raw_data.get("subbed_in")
        subbed_out = raw_data.get("subbed_out")
        substitution_text = ""
        if subbed_in:
            substitution_text = f"On {subbed_in}'"
        elif subbed_out:
            substitution_text = f"Off {subbed_out}'"
        results.append({
            "date": getattr(match, "date", None),
            "outcome": _extract_outcome_from_result(raw_result, opponent_label, player_team, opponent_team),
            "score": _extract_score_text(raw_result),
            "opponent_label": opponent_label,
            "goals": int(getattr(match, "goals", 0) or 0),
            "assists": int(getattr(match, "assists", 0) or 0),
            "minutes": int(getattr(match, "minutes_played", 0) or 0),
            "yellow_cards": int(getattr(match, "yellow_cards", 0) or 0),
            "red_cards": int(getattr(match, "red_cards", 0) or 0),
            "competition": competition_name,
            "competition_logo": competition_logo,
            "substitution": substitution_text,
            "stadium": raw_data.get("stadium") or raw_data.get("venue") or "",
            "penalties": "pen" in str(raw_result).lower(),
        })
        if limit and len(results) >= limit:
            break
    return results


def _get_rival_recent_form(player_name: str, team_name: str, limit: int = 5) -> Dict[str, Any]:
    """
    Returns a lightweight recent-form snapshot for a rival player.
    Based on minutes, team results, goals, assists and cards in the last 5 matches.
    """
    default = {
        "label": "Stable",
        "reason": "No recent match history available yet.",
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
        reason = f"{minutes} minutes in the last {limit}, {involvement} goal involvements, team collected {team_points} points."
    elif minutes < 90 or (team_points <= 2 and involvement == 0):
        label = "Out of Form"
        reason = f"Limited recent involvement: {minutes} minutes, {involvement} goal involvements, team collected {team_points} points."
    else:
        label = "Stable"
        reason = f"Steady recent profile: {minutes} minutes, {involvement} goal involvements, team collected {team_points} points."

    return {
        "label": label,
        "reason": reason,
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

        team_df = pd.DataFrame()
        if "Team" in df.columns:
            normalized_opponent = _normalize_team_jersey_key(opponent_team)
            normalized_team_col = df["Team"].fillna("").astype(str).map(_normalize_team_jersey_key)
            team_df = df[normalized_team_col == normalized_opponent]
            if team_df.empty:
                team_df = df[df["Team"].astype(str).str.lower() == str(opponent_team).lower()]
            if team_df.empty:
                # Try partial match
                team_df = df[df["Team"].astype(str).str.lower().str.contains(str(opponent_team).lower(), na=False)]
            if team_df.empty and "Team within selected timeframe" in df.columns:
                normalized_timeframe_col = df["Team within selected timeframe"].fillna("").astype(str).map(_normalize_team_jersey_key)
                team_df = df[normalized_timeframe_col == normalized_opponent]

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

        position_label_overrides = {
            "DMF": "Defensive Midfielder",
            "AMF": "Attacking Midfielder",
            "CMF": "Central Midfielder",
            "LMF": "Left Midfielder",
            "RMF": "Right Midfielder",
            "LWF": "Left Winger",
            "RWF": "Right Winger",
            "GK": "Goalkeeper",
        }

        def _format_role_token(token: str) -> str:
            token = str(token or "").upper().strip()
            if not token:
                return "Unknown"
            return POSITION_FULL_NAMES.get(token) or position_label_overrides.get(token) or token.replace("_", " ").title()

        def _display_role(row: pd.Series) -> str:
            tokens = _row_tokens(row)
            if not tokens:
                return str(row.get("Position_Group", "Unknown"))
            token = tokens[0]
            return _format_role_token(token)

        def _metric_value(row: pd.Series, columns: List[str]) -> tuple[str, float]:
            for column in columns:
                if column in row.index:
                    try:
                        return column, float(row.get(column) or 0)
                    except Exception:
                        continue
            return columns[0], 0.0

        def _metric_ratio(row: pd.Series, column: str) -> Optional[float]:
            if column not in row.index:
                return None
            try:
                value = float(row.get(column) or 0)
            except Exception:
                return None
            label = str(column or "").lower()
            if "%" in label:
                return max(0.0, min(1.0, value / 100.0))
            bounds = {
                "Goals": 8.0,
                "Assists": 6.0,
                "xG per 90": 0.55,
                "xA per 90": 0.35,
                "Shots per 90": 3.5,
                "Key passes per 90": 2.5,
                "Progressive passes per 90": 8.0,
                "Interceptions per 90": 3.0,
                "PAdj interceptions per 90": 10.0,
                "Defensive duels per 90": 9.0,
                "Aerial duels won, %": 100.0,
                "Defensive duels won, %": 100.0,
                "Successful dribbles, %": 100.0,
                "Dribbles per 90": 5.0,
                "Accurate passes, %": 100.0,
                "Shots blocked per 90": 2.5,
            }
            limit = bounds.get(column, 1.0)
            if limit <= 0:
                return None
            return max(0.0, min(1.0, value / limit))

        def _normalize_metric_label(label: str) -> str:
            return label.replace(" per 90", " /90").replace(", %", "%").strip()

        def _role_metric_profile(role_token: str, pos_group: str) -> tuple[List[str], List[str], List[str], List[str]]:
            role_token = str(role_token or "").upper()
            if role_token in {"LB", "LWB", "LB5", "RB", "RWB", "RB5"}:
                return (
                    ["Defensive duels won, %", "Interceptions per 90", "Defensive duels per 90"],
                    ["Interceptions per 90", "Defensive duels per 90", "Aerial duels won, %"],
                    ["Defensive duels won, %", "Interceptions per 90", "Aerial duels won, %", "Successful dribbles, %"],
                    physical_candidates,
                )
            if role_token in {"LCB", "RCB", "CB", "CB3", "LCB3", "RCB3"}:
                return (
                    ["Aerial duels won, %", "Defensive duels won, %", "Interceptions per 90"],
                    ["Defensive duels won, %", "Interceptions per 90", "Shots blocked per 90"],
                    ["Aerial duels won, %", "Defensive duels won, %", "Interceptions per 90"],
                    physical_candidates,
                )
            if role_token in {"DM", "DMF", "CM", "CMF"}:
                return (
                    ["Interceptions per 90", "Accurate passes, %", "Progressive passes per 90"],
                    ["Progressive passes per 90", "Accurate passes, %", "Defensive duels won, %"],
                    ["Defensive duels won, %", "Interceptions per 90", "Progressive passes per 90", "Accurate passes, %"],
                    physical_candidates,
                )
            if role_token in {"AM", "AMF", "RW", "RWF", "LW", "LWF", "RM", "LM"}:
                return (
                    ["Successful dribbles, %", "Dribbles per 90", "Key passes per 90", "Goals"],
                    ["Key passes per 90", "xA per 90", "Goals", "xG per 90"],
                    ["Defensive duels won, %", "Accurate passes, %", "Successful dribbles, %", "xA per 90"],
                    physical_candidates,
                )
            if role_token in {"ST", "CF"}:
                return (
                    ["Goals", "xG per 90", "Shots per 90"],
                    ["Shots per 90", "xG per 90", "Aerial duels won, %"],
                    ["Defensive duels won, %", "Shots per 90", "xG per 90", "Aerial duels won, %"],
                    physical_candidates,
                )
            if pos_group == "Defender":
                return (
                    ["Defensive duels won, %", "Interceptions per 90", "Aerial duels won, %"],
                    ["Interceptions per 90", "Aerial duels won, %", "Defensive duels per 90"],
                    ["Defensive duels won, %", "Interceptions per 90", "Aerial duels won, %"],
                    physical_candidates,
                )
            if pos_group == "Midfielder":
                return (
                    ["Accurate passes, %", "Key passes per 90", "Interceptions per 90"],
                    ["Interceptions per 90", "Progressive passes per 90", "Defensive duels won, %"],
                    ["Defensive duels won, %", "Interceptions per 90", "Progressive passes per 90"],
                    physical_candidates,
                )
            if pos_group in {"Forward", "Winger"}:
                return (
                    ["Goals", "Successful dribbles, %", "Key passes per 90"],
                    ["xG per 90", "Dribbles per 90", "xA per 90"],
                    ["Defensive duels won, %", "Successful dribbles, %", "xA per 90"],
                    physical_candidates,
                )
            return (["Goals"], ["Assists"], ["Goals"], physical_candidates)

        def _choose_weak_metric(row: pd.Series, columns: List[str]) -> tuple[str, float]:
            candidates: List[tuple[str, float, float]] = []
            for column in columns:
                ratio = _metric_ratio(row, column)
                if ratio is None:
                    continue
                try:
                    raw_value = float(row.get(column) or 0)
                except Exception:
                    raw_value = 0.0
                candidates.append((column, raw_value, ratio))
            if not candidates:
                fallback = columns[0] if columns else "Unknown"
                return fallback, 0.0
            weakest = min(candidates, key=lambda item: item[2])
            return weakest[0], weakest[1]

        def _strength_text(role_token: str, metric_label: str, metric_value: float) -> str:
            role_token = str(role_token or "").upper()
            label = str(metric_label or "").lower()
            display_value = _normalize_metric_label(metric_label)
            if "aerial" in label:
                return f"Dominant aerially with {metric_value:.1f} in {display_value}."
            if "defensive duels won" in label:
                flank_note = " on the flank" if role_token in {"LB", "LWB", "LB5", "RB", "RWB", "RB5"} else ""
                return f"Wins defensive duels{flank_note} at {metric_value:.1f} {display_value.split()[-1]}."
            if "interceptions" in label:
                return f"Reads passing lanes well with {metric_value:.1f} {display_value}."
            if "accurate passes" in label:
                return f"Secure in possession with {metric_value:.1f} {display_value}."
            if "progressive passes" in label:
                return f"Moves the team upfield through {metric_value:.1f} {display_value}."
            if "key passes" in label:
                return f"Creates chances consistently with {metric_value:.1f} {display_value}."
            if "dribbles" in label:
                return f"Carries threat 1v1 through {metric_value:.1f} {display_value}."
            if label == "goals":
                return f"Reliable scorer with {metric_value:.1f} goals this season."
            if "xg" in label:
                return f"Finds quality shooting positions at {metric_value:.1f} {display_value}."
            if "shots" in label:
                return f"Gets shots away regularly with {metric_value:.1f} {display_value}."
            return f"Strong output in {display_value.lower()}."

        def _weakness_text(role_token: str, metric_label: str, metric_value: float) -> str:
            role_token = str(role_token or "").upper()
            label = str(metric_label or "").lower()
            display_value = _normalize_metric_label(metric_label)
            if "defensive duels won" in label:
                return f"Can be beaten in direct defending with only {metric_value:.1f} {display_value.split()[-1]}."
            if "interceptions" in label:
                return f"Does not break up play often: {metric_value:.1f} {display_value}."
            if "aerial" in label:
                return f"Less convincing in the air with {metric_value:.1f} {display_value}."
            if "accurate passes" in label:
                return f"Passing can drop under pressure at {metric_value:.1f} {display_value}."
            if "progressive passes" in label:
                return f"Offers limited progression from deep: {metric_value:.1f} {display_value}."
            if "key passes" in label or "xa" in label:
                return f"Limited creative output recently and across the season in {display_value.lower()}."
            if "dribbles" in label:
                return f"Less efficient when isolated 1v1: {metric_value:.1f} {display_value}."
            if label == "goals" or "xg" in label or "shots" in label:
                return f"End product is modest in {display_value.lower()}."
            if role_token in {"LB", "LWB", "LB5", "RB", "RWB", "RB5"}:
                return "Can leave space behind when drawn high and wide."
            return f"Lower output in {display_value.lower()}."

        def _physical_text(metric_label: str, metric_value: float) -> str:
            label = _normalize_metric_label(metric_label)
            if "Sprinting Distance" in metric_label:
                return f"{metric_value:.1f} sprinting distance /90"
            if "Count Sprint" in metric_label:
                return f"{metric_value:.1f} sprints /90"
            if "HSR Distance" in metric_label:
                return f"{metric_value:.1f} HSR distance /90"
            if "Count HSR" in metric_label:
                return f"{metric_value:.1f} HSR actions /90"
            return f"{metric_value:.1f} {label}"

        physical_candidates = [
            "Sprinting Distance per 90 (+25 km/h)",
            "Count Sprint per 90 (+25 km/h)",
            "HSR Distance per 90 (20-25 km/h)",
            "Count HSR per 90 (20-25 km/h)",
        ]

        for _, row in rival_df.iterrows():
            tokens = _candidate_tokens(row)
            if not tokens:
                continue

        def _score_row(row: pd.Series) -> float:
            tokens = _candidate_tokens(row)
            if not tokens:
                return -1.0
            minutes = float(row.get("Minutes played", 0) or 0)
            if minutes < 120:
                return -1.0
            tactical_bonus = 18.0 if preferred_tokens and set(tokens) & set(preferred_tokens) else 0.0
            role_token = tokens[0]
            pos_group = str(row.get("Position_Group", rival_pos_groups[0] if rival_pos_groups else "Midfielder"))
            prim_cols, sec_cols, _, _ = _role_metric_profile(role_token, pos_group)
            _, key_val = _metric_value(row, prim_cols)
            _, sec_val = _metric_value(row, sec_cols)
            if key_val <= 0 and sec_val <= 0:
                return -1.0
            return tactical_bonus + key_val + (sec_val * 0.35) + (minutes / 300.0)

        rival_df = rival_df.assign(_rival_score=rival_df.apply(_score_row, axis=1))
        rival_df = rival_df[rival_df["_rival_score"] >= 0].sort_values("_rival_score", ascending=False)

        if len(rival_df) < 3 and "Position_Group" in team_df.columns:
            fallback_df = team_df[team_df["Position_Group"].isin(rival_pos_groups)].copy()
            fallback_df = fallback_df.assign(_rival_score=fallback_df.apply(_score_row, axis=1))
            fallback_df = fallback_df[fallback_df["_rival_score"] >= 0].sort_values("_rival_score", ascending=False)
            rival_df = pd.concat([rival_df, fallback_df], ignore_index=True).drop_duplicates(subset=["Player"], keep="first")

        results = []
        for idx, (_, row) in enumerate(rival_df.head(3).iterrows()):
            tokens = _candidate_tokens(row)
            if not tokens:
                continue
            role_token = tokens[0]
            pos_group = str(row.get("Position_Group", rival_pos_groups[0] if rival_pos_groups else "Midfielder"))
            prim_cols, sec_cols, weakness_cols, physical_cols = _role_metric_profile(role_token, pos_group)
            key_label, key_val = _metric_value(row, prim_cols)
            sec_label, sec_val = _metric_value(row, sec_cols)
            weak_label, weak_val = _choose_weak_metric(row, weakness_cols)
            physical_label, physical_val = _metric_value(row, physical_cols)
            strength_text = _strength_text(role_token, key_label, key_val)
            weakness_text = _weakness_text(role_token, weak_label, weak_val)
            recent_form = _get_rival_recent_form(
                str(row.get("Player", "Unknown")),
                opponent_team,
            )
            form_label = recent_form.get("label", "Stable")
            results.append({
                "name": str(row.get("Player", "Unknown")),
                "position_group": role_token,
                "role_label": _format_role_token(role_token),
                "matchup_tier": "Primary Matchup" if idx == 0 else "Support Matchup",
                "form_label": form_label,
                "form_reason": recent_form.get("reason", ""),
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
                "physical_text": _physical_text(physical_label, float(physical_val or 0)) if physical_label else "",
                "recent_data_available": bool(recent_form.get("minutes", 0) or recent_form.get("goals", 0) or recent_form.get("assists", 0) or recent_form.get("yellow_cards", 0) or recent_form.get("red_cards", 0)),
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
    cached_result = _get_cached_dashboard_data(player_name, player_id)
    if cached_result is not None:
        return cached_result

    with _dashboard_data_fetch_lock:
        cached_result = _get_cached_dashboard_data(player_name, player_id)
        if cached_result is not None:
            return cached_result

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
            "birth_date": None,
            "nationality": None,
            "birth_country": None,
            "foot": None,
            "height": None,
            "cutout_path": None,
            "matches_played": 0,
            "goals": 0,
            "assists": 0,
            "minutes_played": 0,
            "last5_results": [],
            "recent_form_windows": {},
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
                result["age"] = player_obj.age
                result["birth_date"] = player_obj.birth_date
                result["nationality"] = player_obj.nationality
                result["birth_country"] = player_obj.birth_country
                result["foot"] = player_obj.foot
                result["height"] = player_obj.height
                if player_obj.current_team:
                    result["team_name"] = _canonical_team_display_name(player_obj.current_team.name)

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
                result["goals"] = sum(s.goals or 0 for s in all_seasons_stats)
                result["assists"] = sum(s.assists or 0 for s in all_seasons_stats)
                result["minutes_played"] = sum(s.minutes_played or 0 for s in all_seasons_stats)

            # ── Last 5 match results ───────────────────────────────────────────
            stmt_mh = (
                select(MatchHistory)
                .where(MatchHistory.player_id == player_id)
                .order_by(MatchHistory.date.desc())
                .limit(10)
            )
            matches = session.execute(stmt_mh).scalars().all()

            # ── Process match outcomes (W/D/L) ─────────────────────────────────
            last5_data = []
            player_team = result.get("team_name")
            import re

            latest_five_matches = matches[:5]
            for m in reversed(latest_five_matches):
                res_str = m.result or ""
                if not res_str:
                    continue

                outcome = "EMPTY"
                score_display = res_str

                if res_str.upper() in ["W", "D", "L"]:
                    outcome = res_str.upper()
                    score_display = outcome
                elif ":" in res_str and player_team:
                    try:
                        score_part = res_str.split()[0]
                        h_score, a_score = map(int, score_part.split(":"))
                        opp = m.opponent or ""
                        parts = opp.split(" vs ")
                        if len(parts) == 2:
                            h_team_raw, a_team_raw = parts
                            h_team = re.sub(r"\(\d+\.\)", "", h_team_raw).strip()
                            a_team = re.sub(r"\(\d+\.\)", "", a_team_raw).strip()

                            is_home = player_team.lower() in h_team.lower()
                            is_away = player_team.lower() in a_team.lower()

                            if is_home:
                                if h_score > a_score:
                                    outcome = "W"
                                elif h_score < a_score:
                                    outcome = "L"
                                else:
                                    outcome = "D"
                            elif is_away:
                                if a_score > h_score:
                                    outcome = "W"
                                elif a_score < h_score:
                                    outcome = "L"
                                else:
                                    outcome = "D"
                    except Exception:
                        pass

                last5_data.append({"outcome": outcome, "score": score_display})

            result["last5_results"] = last5_data
            result["recent_form_windows"] = _build_recent_form_windows(matches)

        except Exception as e:
            logger.warning(f"_fetch_dashboard_data DB error for '{player_name}': {e}")
        finally:
            session.close()

        # ── Position group + archetype (uses DM, no extra session) ────────────
        try:
            dm = get_hong_kong_data_manager()
            result["pos_group"] = _get_position_group(player_name, dm)
            result["archetype"] = _get_archetype_label(player_name, result["pos_group"], dm)

            try:
                cohort_season = current_season
                if dm.processed_data is not None:
                    if player_name not in dm.processed_data["Player"].values:
                        cohort_season = latest_active_season

                if cohort_season != dm.current_season:
                    from utils.efficiency_metrics import PercentileRankingSystem

                    historical_df = dm._load_season_dataframe(cohort_season)
                    historical_df = dm.processor.process_season_data(historical_df, cohort_season)
                    ranker = PercentileRankingSystem(historical_df)
                else:
                    ranker = dm.aggregator.percentile_system

                if ranker:
                    raw = ranker.get_player_percentiles(player_name, by_position=True)
                    result["percentiles_data"] = raw.get("metrics", {})
            except Exception as e:
                logger.debug(f"_fetch_dashboard_data percentile error: {e}")

        except Exception as e:
            logger.warning(f"_fetch_dashboard_data DM error: {e}")

        # ── Cluster data from K-Means registry ────────────────────────────────
        result["cluster_id"] = None
        result["cluster_label"] = None
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
                        for stat in all_seasons:
                            mins = stat.minutes_played or 0
                            if mins <= 0 or not stat.advanced_stats:
                                continue

                            total_minutes += mins
                            for k, v in stat.advanced_stats.items():
                                if isinstance(v, (int, float)):
                                    career_metrics[k] = career_metrics.get(k, 0) + (v * mins)

                        if total_minutes > 0:
                            for k in career_metrics:
                                career_metrics[k] /= total_minutes

                            career_row = career_metrics.copy()
                            career_row["Player"] = player_name
                            career_row["Season"] = "Career"
                            career_row["Minutes played"] = total_minutes
                            career_row["Team"] = result.get("team_name") or "Historical"
                            career_row["Position"] = result.get("position_main") or "Unknown"

                            df_c = pd.concat([df_c, pd.DataFrame([career_row])], ignore_index=True)
                            real_player_name = player_name
                        else:
                            p_match = df_c[df_c["Player"].str.contains(player_name, case=False, na=False)]
                            real_player_name = p_match.iloc[0]["Player"] if not p_match.empty else None
                    else:
                        real_player_name = None
                except Exception as e:
                    logger.warning(f"Career aggregation failed for {player_name}: {e}")
                    real_player_name = None
                finally:
                    db_session.close()

                if real_player_name:
                    meta_cols_c = {"Player", "Season", "Team", "Position"}
                    pp = MLPreprocessor()
                    numeric_cols_raw = [
                        c for c in df_c.columns if c not in meta_cols_c and pd.api.types.is_numeric_dtype(df_c[c])
                    ]
                    df_c = pp.compute_temporal_features(df_c, numeric_cols_raw)
                    df_c = pp.compute_positional_zscores(df_c, numeric_cols_raw)
                    df_c = pp.compute_benchmark_deltas(df_c, numeric_cols_raw)
                    df_c = pp.inject_composite_metrics(df_c)

                    km = ModelRegistry().load("kmeans_overall_k5")
                    if km is not None:
                        registry = ModelRegistry()
                        reg_data = registry._load_registry()
                        expected_features = reg_data.get("kmeans_overall_k5", {}).get("latest", {}).get("features")

                        if expected_features:
                            available_cols = [c for c in expected_features if c in df_c.columns]
                            X_input_df = df_c[available_cols].fillna(0).copy()
                            for mc in expected_features:
                                if mc not in X_input_df.columns:
                                    X_input_df[mc] = 0.0
                            X_input = _align_cluster_feature_frame(X_input_df, expected_features)
                            feature_cols_c = expected_features
                        else:
                            feature_cols_c = [
                                c for c in df_c.columns if c not in meta_cols_c and pd.api.types.is_numeric_dtype(df_c[c])
                            ]
                            X_input = _align_cluster_feature_frame(df_c, feature_cols_c)

                        df_train_set = apply_quality_filters(df_c, min_minutes=180, smooth_rates=True)
                        if df_train_set.empty:
                            df_train_set = df_c

                        scaler = StandardScaler()
                        scaler.fit(_align_cluster_feature_frame(df_train_set, feature_cols_c))
                        X_all_scaled = scaler.transform(X_input)

                        all_preds = km.predict(X_all_scaled)
                        loc_idx = df_c[df_c["Player"] == real_player_name].index[-1]
                        loc = df_c.index.get_loc(loc_idx)
                        player_vector_scaled = X_all_scaled[loc : loc + 1]
                        cluster_id = int(all_preds[loc])

                        archetype_labels_c = label_archetypes(km, feature_cols_c, cluster_df=df_c)
                        centroids = km.cluster_centers_
                        cluster_label = (
                            archetype_labels_c[cluster_id]
                            if cluster_id < len(archetype_labels_c)
                            else f"Cluster {cluster_id}"
                        )

                        derived_exclude = ("_roll_", "_delta_", "_benchmark", "_composite", "lag_", "roll_")
                        discipline = {"red card", "yellow card", "foul", "conceded", "loss", "lost"}
                        physical_attrs = {"height", "weight", "age", "market value", "contract"}

                        archetype_priority = {
                            "Physical": ["distance", "sprint", "hsr", "hi distance", "speed", "duel"],
                            "Defensive": ["interception", "tackle", "clearance", "block", "duel"],
                            "Distributor": ["pass", "accurate pass", "long pass", "forward pass"],
                            "Maestro": ["key pass", "smart pass", "through pass", "assist", "xa"],
                            "Finisher": ["goal", "xg", "shot", "conversion"],
                            "Winger": ["dribble", "cross", "progressive run", "acceleration"],
                        }

                        priority_keywords = []
                        for kw, features in archetype_priority.items():
                            if kw.lower() in cluster_label.lower():
                                priority_keywords.extend(features)

                        valid_idx = []
                        p_z_vec = player_vector_scaled[0]

                        for i, name in enumerate(feature_cols_c):
                            name_l = name.lower()
                            if any(s in name for s in derived_exclude):
                                continue
                            if any(d in name_l for d in discipline | physical_attrs):
                                continue

                            raw_col = name.replace("_zscore_positional", "")
                            p_val_raw = 0.0
                            if raw_col in df_c.columns:
                                p_val_raw = float(df_c[df_c["Player"] == real_player_name].iloc[-1][raw_col] or 0)

                            if p_z_vec[i] < -0.2:
                                continue
                            if "per 90" in name_l and p_val_raw < 0.15:
                                continue

                            valid_idx.append(i)

                        if not valid_idx:
                            valid_idx = [
                                i for i, name in enumerate(feature_cols_c)
                                if "_zscore_positional" in name and p_z_vec[i] >= 0
                            ]

                        scores = []
                        for idx in valid_idx:
                            name_l = feature_cols_c[idx].lower()
                            score = p_z_vec[idx]
                            if any(pk in name_l for pk in priority_keywords):
                                score += 2.5
                            scores.append(score)

                        top5_local = np.argsort(scores)[::-1][:5]
                        final_top_idx = [valid_idx[i] for i in top5_local]

                        result["cluster_id"] = cluster_id
                        result["cluster_label"] = cluster_label
                        result["cluster_size_pct"] = float((all_preds == cluster_id).mean() * 100)
                        result["cluster_centroid"] = {
                            feature_cols_c[i]: float(centroids[cluster_id][i]) for i in final_top_idx
                        }
                        result["player_scaled_vec"] = {
                            feature_cols_c[i]: float(p_z_vec[i]) for i in final_top_idx
                        }

        except Exception as e:
            logger.warning(f"_fetch_dashboard_data cluster error: {e}")

        result["history_df"] = _fetch_player_season_history(player_name)
        if isinstance(result["history_df"], pd.DataFrame) and not result["history_df"].empty:
            for column in ("Birthday", "birth_date", "date_of_birth", "birthday"):
                if column in result["history_df"].columns:
                    series = result["history_df"][column].dropna()
                    if not series.empty:
                        try:
                            birth_dt = pd.to_datetime(series.iloc[0], errors="coerce")
                            if pd.notna(birth_dt):
                                today = pd.Timestamp.today()
                                result["age"] = int(
                                    today.year
                                    - birth_dt.year
                                    - ((today.month, today.day) < (birth_dt.month, birth_dt.day))
                                )
                        except Exception:
                            pass
                    break

        result["similar_players_meta"] = {"similar_players": [], "query_player_embedding_idx": -1}
        try:
            from ai_models.similarity import build_embeddings, find_similar
            from ai_models.model_registry import ModelRegistry as _MReg

            _dm_s = get_hong_kong_data_manager()
            if _dm_s.processed_data is not None and not _dm_s.processed_data.empty:
                _corpus_emb = build_embeddings(_dm_s.processed_data)
                _meta_df = _MReg().load("player_embeddings_meta")

                if _meta_df is not None:
                    _name_col = "Player" if "Player" in _meta_df.columns else "player_name"
                    _matches = _meta_df.index[_meta_df[_name_col] == player_name].tolist()

                    if _matches:
                        _qidx = _matches[0]
                        _query_emb = _corpus_emb[_qidx]
                        _sim_df = find_similar(
                            _query_emb,
                            _corpus_emb,
                            _meta_df,
                            k=20,
                            query_index=_qidx,
                            position=None,
                        )
                        _pos_group = result.get("pos_group") or ""
                        if "Position" in _sim_df.columns and _pos_group:
                            _sim_df = _sim_df[_sim_df["Position"].apply(_infer_position_group) == _pos_group]

                        _top5 = _sim_df.head(5)
                        _similar_list = []
                        for _, _row in _top5.iterrows():
                            _sname = str(_row.get(_name_col, _row.get("player_name", "")))
                            _steam = str(_row.get("Team", _row.get("team", "")))
                            _spos = str(_row.get("Position", _row.get("position", "")))
                            _score = float(_row.get("similarity_score", 0.0))
                            _similar_list.append(
                                {
                                    "name": _sname,
                                    "team_name": _steam,
                                    "team_logo_path": _resolve_team_logo(_steam),
                                    "position": _spos,
                                    "similarity_score": _score,
                                }
                            )

                        result["similar_players_meta"] = {
                            "similar_players": _similar_list,
                            "query_player_embedding_idx": _qidx,
                        }
        except Exception as _se:
            logger.debug(f"_fetch_dashboard_data similar players meta error: {_se}")

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

            lstm_metric = "goals" if result["pos_group"] in ("Forward", "Winger") else (
                "assists" if result["pos_group"] == "Midfielder" else "minutes_played"
            )
            if len(match_records) >= 5:
                result["form_trend"] = get_form_trend(match_records, lstm_metric, window=5)

            if not result["history_df"].empty:
                career_dict = result["history_df"].drop(columns=["Season"], errors="ignore").mean().to_dict()
                result["transferability"] = get_transferability_score(
                    career_dict, result["pos_group"], player_id=player_id
                )

        except Exception as _hae:
            logger.debug(f"_fetch_dashboard_data hybrid ai error: {_hae}")

        _set_cached_dashboard_data(player_name, player_id, result)
        return copy.deepcopy(result)


_PHASE_LABELS: Dict[str, str] = {
    "development": "★ DESARROLLO",
    "building":    "★ CRECIMIENTO",
    "peak":        "★ PEAK PHASE",
    "post-peak":   "★ VETERANO",
    "unknown":     "★ ACTIVO",
}


def _build_phase_momentum_row(career_phase_data: Dict) -> List:
    """Returns list of Dash elements for phase badge + 5-dot momentum tracker."""
    phase = career_phase_data.get("career_phase", "unknown")
    momentum = int(career_phase_data.get("momentum_score", 3))
    momentum = max(0, min(5, momentum))
    phase_label = _PHASE_LABELS.get(phase, "★ ACTIVO")

    return [
        html.Div([
            _build_phase_badge(phase_label, class_name="career-phase-badge me-2"),
            _build_momentum_dots(momentum),
        ], style={"display": "flex", "alignItems": "center", "marginTop": "6px", "flexWrap": "wrap"}),
    ]


def _format_career_phase_display(career_phase_data: Dict[str, Any]) -> str:
    """Returns a user-facing phase label without exposing raw unknown states."""
    phase = str((career_phase_data or {}).get("career_phase") or "").strip().lower()
    if not phase or phase == "unknown":
        return "Context Pending"
    return phase.title()


def _build_phase_badge(phase_label: str, class_name: str = "career-phase-badge") -> dbc.Badge:
    """Returns the styled phase badge for career progression surfaces."""
    return dbc.Badge(phase_label, className=class_name)


def _build_momentum_dots(momentum: int) -> html.Div:
    """Returns a 5-dot momentum tracker."""
    momentum = max(0, min(5, int(momentum or 0)))
    dots = [
        html.Span(className="momentum-dot momentum-dot--filled" if i < momentum else "momentum-dot")
        for i in range(5)
    ]
    return html.Div(dots, className="career-command-kpi__dots")


def _build_identity_hero(data: Dict, career_phase_data: Optional[Dict] = None) -> html.Div:
    """§1 Identity Hero: photo, identity snapshot, and compact metadata row."""
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
    cutout_path   = data.get("cutout_path")

    raw_birth = data.get("birth_date") or data.get("date_of_birth") or data.get("Birthday") or data.get("birthday")
    age = data.get("age")
    history_df = data.get("history_df", pd.DataFrame())
    if not raw_birth and isinstance(history_df, pd.DataFrame) and not history_df.empty:
        for column in ("Birthday", "birth_date", "date_of_birth", "birthday"):
            if column in history_df.columns:
                series = history_df[column].dropna()
                if not series.empty:
                    raw_birth = series.iloc[0]
                    break
    if raw_birth:
        try:
            birth_dt = pd.to_datetime(raw_birth, errors="coerce")
            if pd.notna(birth_dt):
                today = pd.Timestamp.today()
                age = int(today.year - birth_dt.year - ((today.month, today.day) < (birth_dt.month, birth_dt.day)))
        except Exception:
            pass
    nationality = data.get("nationality") or data.get("birth_country")
    foot   = data.get("foot")
    height = data.get("height")
    seasons_tracked = len(history_df) if isinstance(history_df, pd.DataFrame) and not history_df.empty else None
    latest_recorded_season = None
    if isinstance(history_df, pd.DataFrame) and not history_df.empty and "Season" in history_df.columns:
        season_values = [_normalize_season_label(season) for season in history_df["Season"].tolist() if str(season).strip()]
        latest_recorded_season = season_values[-1] if season_values else None

    # ── Photo ──────────────────────────────────────────────────────────────
    photo_col = html.Div(
        html.Img(
            src=cutout_path,
            style={
                "maxHeight": "152px",
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
        className="career-identity-photo",
    )

    # ── Metadata row ──────────────────────────────────────────────────────
    def _attr_chip(icon: str, label: str, value) -> html.Div:
        display = str(value) if value is not None else "–"
        return html.Div([
            html.Div([
                html.I(className=f"bi {icon}", style={"fontSize": "0.78rem"}),
                html.Span(label),
            ], className="career-identity-meta__label"),
            html.Div(display, className="career-identity-meta__value"),
        ], className="career-identity-meta__item")

    height_str = f"{height} cm" if height else None
    attrs_row = html.Div([
        _attr_chip("bi-calendar3", "Age", age),
        _attr_chip("bi-rulers", "Height", height_str),
        _attr_chip("bi-arrow-left-right", "Foot", foot),
        _attr_chip("bi-collection", "Seasons", seasons_tracked),
    ], className="career-identity-meta")

    nationality_flag = _country_to_flag(nationality)
    nationality_row = html.Div(
        [
            html.Span(nationality_flag, title=str(nationality), className="career-identity-nationality__flag")
            if nationality_flag else html.I(className="bi bi-flag-fill career-identity-nationality__icon"),
            html.Span(str(nationality) if nationality is not None else "–", className="career-identity-nationality__name"),
        ],
        className="career-identity-nationality",
    )
    latest_season_row = html.Div(
        [
            html.Span("Last Season:", className="career-identity-last-season__label"),
            html.Span(latest_recorded_season or "–", className="career-identity-last-season__value"),
        ],
        className="career-identity-last-season",
    )

    # ── Info column ────────────────────────────────────────────────────────
    info_col = html.Div([
        html.Div(data.get("player_name", ""), style={
            "fontSize": "1.25rem", "fontWeight": "800",
            "color": HKFATheme.TEXT_PRIMARY, "lineHeight": "1.2",
        }),
        html.Div(
            html.Span(pos_label or "Player", className="career-identity-position-badge"),
            style={"marginTop": "4px"},
        ),
        html.Div([
            *([html.Img(src=_resolve_team_logo(team_name),
                        className="career-identity-team__logo")]
              if _resolve_team_logo(team_name) else
              [html.I(className="bi bi-shield-fill career-identity-team__fallback")]),
            html.Span(team_name, className="career-identity-team__name"),
        ], className="career-identity-team"),
        nationality_row,
        latest_season_row,
    ], style={"flex": "1", "minWidth": "0"}, className="career-identity-info")

    return html.Div([
        html.Div(
            [
                html.Span(html.I(className="bi bi-person-badge-fill"), className="career-dashboard-section__icon"),
                html.H6("Player Profile", className="career-dashboard-section__title"),
            ],
            className="career-dashboard-section__title-row career-command-card__title-row",
        ),
        html.Div([photo_col, info_col, attrs_row], className="career-identity-layout"),
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


def _build_league_standing(data: Dict, focus_metric: str = "") -> html.Div:
    """§3 League Standing: positional percentile bars via PercentileRankingSystem."""
    from utils.chart_helpers import create_percentile_bars

    pos_group = data.get("pos_group") or ""
    percentiles_all = data.get("percentiles_data") or {}
    resolved_focus_metric = ""

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

    if focus_metric:
        metric_lookup = {str(metric).strip().lower(): metric for metric in percentiles_all.keys()}
        resolved_focus_metric = metric_lookup.get(str(focus_metric).strip().lower(), "")

    if resolved_focus_metric and resolved_focus_metric in percentiles_all:
        filtered = {resolved_focus_metric: percentiles_all[resolved_focus_metric]}
    else:
        filtered = {m: percentiles_all[m] for m in metrics if m in percentiles_all}

    if not filtered:
        return html.Div([
            header,
            html.P("No hay datos de percentiles para esta posición.",
                   className="text-muted small"),
        ])

    bars = create_percentile_bars(filtered)
    focus_summary = html.Div()
    if resolved_focus_metric:
        focus_data = percentiles_all.get(resolved_focus_metric) or {}
        percentile = int(float(focus_data.get("percentile", 0) or 0))
        group_avg = focus_data.get("group_avg_percentile")
        pos_avg = focus_data.get("pos_avg_percentile")
        summary_bits = [f"{resolved_focus_metric} is currently at the {percentile}th percentile."]
        if group_avg is not None:
            summary_bits.append(f"Group average is around {float(group_avg):.0f}.")
        if pos_avg is not None:
            summary_bits.append(f"Position average is around {float(pos_avg):.0f}.")
        focus_summary = html.Div(
            [
                html.Div("Focused Metric", className="career-dashboard-card__eyebrow"),
                html.P(" ".join(summary_bits), className="career-dashboard-card__body"),
            ],
            className="career-outlook-card mb-3",
        )
    comparison_label = html.Div(
        f"vs. {pos_group}s in HKPL" if not resolved_focus_metric else f"Focused on {resolved_focus_metric} vs. {pos_group}s in HKPL",
        style={"fontSize": "0.65rem", "color": HKFATheme.TEXT_SECONDARY,
               "textAlign": "right", "marginBottom": "8px", "letterSpacing": "0.03em"},
    )

    return html.Div([header, focus_summary, comparison_label, bars])


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
            dbc.Col(
                dcc.Graph(
                    figure=trend_fig,
                    config={"displayModeBar": False, "responsive": True},
                    className="w-100",
                    responsive=True,
                    style={"width": "100%", "minWidth": "0"},
                ),
                width=12,
                lg=7,
            ),
            dbc.Col(
                dcc.Graph(
                    figure=radar_fig,
                    config={"displayModeBar": False, "responsive": True},
                    className="w-100",
                    responsive=True,
                    style={"width": "100%", "minWidth": "0"},
                ),
                width=12,
                lg=5,
            ),
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
        dcc.Graph(
            figure=proj_fig,
            config={"displayModeBar": False, "responsive": True},
            className="w-100",
            responsive=True,
            style={"width": "100%", "minWidth": "0"},
        ),
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
            dcc.Graph(
                figure=fig,
                config={"displayModeBar": False, "staticPlot": True, "responsive": True},
                responsive=True,
                style={"width": "100%", "minWidth": "0"},
            ),
            table
        ])

    except Exception as e:
        logger.warning(f"_build_similar_players Parallel Categories error: {e}")
        return html.Div([header, html.P("Mapping error. Reverting to basic view.", className="text-muted small")])


_IMPACT_COLOR: Dict[str, str] = {
    "alto":  "#ff6b6b",
    "medio": "#ffd93d",
    "bajo":  "#6bcb77",
}


def render_strategic_intelligence(
    career_signals: Dict[str, Any],
    development_priorities: List[Dict[str, Any]],
    gemini_narrative: str,
) -> dbc.Card:
    """
    Strategic Intelligence Dashboard Block.
    Returns a dbc.Card with Priority Board (left) + Signal Panel (right) + IA Narrative row.
    """
    # ── Priority Board (left column) ─────────────────────────────────────────
    top3 = development_priorities[:3]

    def _priority_bar(item: Dict) -> html.Div:
        metric    = item.get("metric", "—")
        percentile = int(item.get("percentile", 50))
        impact    = item.get("impact", "medio")
        impact_color = _IMPACT_COLOR.get(impact, "#ffd93d")
        return html.Div([
            html.Div([
                html.Span(metric, style={"fontSize": "0.75rem", "fontWeight": "600",
                                         "color": HKFATheme.TEXT_PRIMARY}),
                html.Span(f"Impacto: {impact.upper()}", className="impact-bar-label ms-2",
                          style={"color": impact_color}),
            ], style={"display": "flex", "justifyContent": "space-between", "alignItems": "center",
                      "marginBottom": "4px"}),
            dbc.Progress(value=percentile, max=100, color="info",
                         style={"height": "6px", "marginBottom": "4px",
                                "background": "rgba(255,255,255,0.08)"}),
            dcc.Link(
                "Comparar →",
                href=f"/portal?stage=similarity&filter={metric}",
                className="comparar-cta",
                style={"fontSize": "0.7rem"},
            ),
        ], style={"marginBottom": "12px"})

    priority_board = html.Div([
        html.Div("Prioridades de Desarrollo", style={
            "fontSize": "0.7rem", "fontWeight": "700", "textTransform": "uppercase",
            "letterSpacing": "0.08em", "color": HKFATheme.ACCENT_BLUE, "marginBottom": "10px",
        }),
        *([_priority_bar(p) for p in top3] if top3 else
          [html.P("Sin datos de percentiles", className="text-muted small")]),
    ])

    # ── Signal Panel (right column) ──────────────────────────────────────────
    coach_conf   = career_signals.get("coach_confidence") or {}
    transfer_win = career_signals.get("transfer_window") or {}
    consistency  = career_signals.get("consistency_score") or {}

    _dir_icons = {"up": "bi-arrow-up-circle-fill", "down": "bi-arrow-down-circle-fill",
                  "stable": "bi-dash-circle-fill"}
    _dir_colors = {"up": "#6bcb77", "down": "#ff6b6b", "stable": HKFATheme.TEXT_SECONDARY}
    cc_dir = coach_conf.get("direction", "stable")

    def _signal_row(icon: str, label: str, value: str, color: str = HKFATheme.TEXT_PRIMARY) -> html.Div:
        return html.Div([
            html.I(className=f"bi {icon} me-2", style={"color": color, "fontSize": "0.8rem"}),
            html.Span(label, style={"fontSize": "0.72rem", "color": HKFATheme.TEXT_SECONDARY,
                                    "marginRight": "6px"}),
            html.Span(value, style={"fontSize": "0.75rem", "fontWeight": "600", "color": color}),
        ], style={"marginBottom": "8px", "display": "flex", "alignItems": "center"})

    signal_panel = html.Div([
        html.Div("Señales Clave", style={
            "fontSize": "0.7rem", "fontWeight": "700", "textTransform": "uppercase",
            "letterSpacing": "0.08em", "color": HKFATheme.ACCENT_BLUE, "marginBottom": "10px",
        }),
        _signal_row(_dir_icons.get(cc_dir, "bi-dash-circle-fill"),
                    "Confianza del entrenador:",
                    coach_conf.get("label", "—"),
                    _dir_colors.get(cc_dir, HKFATheme.TEXT_PRIMARY)),
        _signal_row("bi-arrow-left-right",
                    "Ventana de transferencia:",
                    transfer_win.get("quality", "—"),
                    HKFATheme.TEXT_PRIMARY),
        _signal_row("bi-activity",
                    "Consistencia:",
                    consistency.get("level", "—"),
                    HKFATheme.TEXT_PRIMARY),
    ])

    # ── IA Narrative row ─────────────────────────────────────────────────────
    narrative_row = html.Div(
        html.P(gemini_narrative or "Análisis estratégico no disponible.",
               style={"fontSize": "0.78rem", "color": HKFATheme.TEXT_SECONDARY,
                      "margin": "0", "lineHeight": "1.5"}),
        className="ai-insight-card mt-3 p-3",
        style={"borderRadius": "8px"},
    ) if True else html.Span()

    return dbc.Card(
        dbc.CardBody([
            html.H6([
                html.I(className="bi bi-cpu-fill me-2"),
                html.Span("Inteligencia Estratégica", className="animate-glass-draw"),
            ], className="mb-3 fw-semibold", style={"color": "var(--accent-cyan, #00d4ff)"}),
            dbc.Row([
                dbc.Col(priority_board, md=6, className="border-end border-secondary"),
                dbc.Col(signal_panel,   md=6),
            ]),
            narrative_row,
        ]),
        className="strategic-intel-card",
        style={"background": "rgba(255,255,255,0.03)", "border": "1px solid rgba(255,255,255,0.08)"},
    )


def _build_career_evidence_button(
    evidence_key: str,
    label: str = "See evidence",
    source: str = "dashboard",
    trigger_index: str = "",
    focus_metric: str = "",
) -> dbc.Button:
    resolved_key = resolve_career_surface_evidence_key(evidence_key)
    return dbc.Button(
        [label, html.I(className="bi bi-arrow-up-right ms-2")],
        id={
            "type": "career-evidence-trigger",
            "key": resolved_key,
            "source": source,
            "index": trigger_index or normalize_evidence_key(resolved_key),
            "focus_metric": str(focus_metric or ""),
        },
        color="link",
        size="sm",
        className="career-evidence-trigger-btn",
        n_clicks=0,
    )


def _get_career_surface_meta(item: Any, section_label: str) -> Dict[str, str]:
    evidence_key = str(getattr(item, "evidence_key", "") or "")
    emphasis = str(getattr(item, "emphasis", "neutral") or "neutral")

    if evidence_key in {
        "minutes_trend",
        "career_arc",
        "career_trend",
        "career_value_summary",
        "recent_form",
        "top_tier_gap",
        "consistency_profile",
        "team_context",
        "career_timing_context",
    }:
        icon_class = "bi bi-graph-up-arrow"
    elif evidence_key in {"career_phase_resolution", "team_positional_rank", "team_global_rank", "league_positional_standing", "league_global_standing"}:
        icon_class = "bi bi-signpost-split"
    elif evidence_key == "projection_outlook":
        icon_class = "bi bi-compass"
    elif evidence_key == "similarity_profiles":
        icon_class = "bi bi-people"
    elif evidence_key == "tactical_dna":
        icon_class = "bi bi-diagram-3"
    else:
        icon_class = "bi bi-stars"

    if section_label.lower() == "leverage":
        tone_label = "Career Lever"
    elif emphasis == "positive":
        tone_label = "Positive Signal"
    elif emphasis == "warning":
        tone_label = "Risk Signal"
    else:
        tone_label = "Career Signal"

    return {
        "icon_class": icon_class,
        "tone_label": tone_label,
    }


def _safe_float_or_none(value: Any) -> Optional[float]:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if pd.isna(result):
        return None
    return result


def _career_kpi_specs_for_position(pos_group: str) -> List[Dict[str, Any]]:
    common_specs = [
        {"key": "matches", "label": "Matches", "secondary_label": "Minutes/Match", "primary": {"kind": "sum", "columns": ["Matches played"], "decimals": 0}, "secondary": {"kind": "weighted_avg", "columns": ["Minutes_per_Match"], "decimals": 1}, "icon_name": "bi bi-calendar2-week", "accent_color": HKFATheme.ACCENT_GOLD},
        {"key": "goals", "label": "Goals", "secondary_label": "Goals/90", "primary": {"kind": "sum", "columns": ["Goals"], "decimals": 0}, "secondary": {"kind": "per90_sum", "columns": ["Goals"], "decimals": 2}, "icon_name": "soccer-ball", "accent_color": HKFATheme.ACCENT_RED},
        {"key": "assists", "label": "Assists", "secondary_label": "Assists/90", "primary": {"kind": "sum", "columns": ["Assists"], "decimals": 0}, "secondary": {"kind": "per90_sum", "columns": ["Assists"], "decimals": 2}, "icon_name": "sport-shoe", "accent_color": HKFATheme.ACCENT_BLUE},
    ]
    if pos_group == "Goalkeeper":
        return [
            {"key": "matches", "label": "Matches", "secondary_label": "Minutes/Match", "primary": {"kind": "sum", "columns": ["Matches played"], "decimals": 0}, "secondary": {"kind": "weighted_avg", "columns": ["Minutes_per_Match"], "decimals": 1}, "icon_name": "bi bi-calendar2-week", "accent_color": HKFATheme.ACCENT_GOLD},
            {"key": "conceded", "label": "Goals Conceded", "secondary_label": "Conceded/90", "primary": {"kind": "sum", "columns": ["Conceded goals", "Goals conceded"], "decimals": 0}, "secondary": {"kind": "weighted_avg", "columns": ["Conceded goals per 90"], "decimals": 2}, "icon_name": "bi bi-bullseye", "accent_color": HKFATheme.NEGATIVE},
            {"key": "xga", "label": "xG Against", "secondary_label": "xGA/90", "primary": {"kind": "sum", "columns": ["xG against"], "decimals": 2}, "secondary": {"kind": "weighted_avg", "columns": ["xG against per 90"], "decimals": 2}, "icon_name": "bi bi-grid-3x3-gap", "accent_color": "#f97316"},
            {"key": "prevented", "label": "Prevented/90", "secondary_label": "Shots Against", "primary": {"kind": "weighted_avg", "columns": ["Prevented goals per 90"], "decimals": 2}, "secondary": {"kind": "sum", "columns": ["Shots against"], "decimals": 0}, "icon_name": "bi bi-hand-index-thumb", "accent_color": HKFATheme.POSITIVE},
            {"key": "back_passes", "label": "Back Passes/90", "secondary_label": "Save Rate", "primary": {"kind": "weighted_avg", "columns": ["Back passes received as GK per 90"], "decimals": 1}, "secondary": {"kind": "weighted_avg", "columns": ["Save rate, %"], "decimals": 1, "pct": True}, "icon_name": "bi bi-arrow-counterclockwise", "accent_color": HKFATheme.ACCENT_BLUE},
            {"key": "gk_passing", "label": "Pass Accuracy", "secondary_label": "Long Pass Accuracy", "primary": {"kind": "weighted_avg", "columns": ["Accurate passes, %"], "decimals": 1, "pct": True}, "secondary": {"kind": "weighted_avg", "columns": ["Accurate long passes, %"], "decimals": 1, "pct": True}, "icon_name": "bi bi-send", "accent_color": "#60a5fa"},
        ]
    if pos_group in {"Forward", "Winger"}:
        return common_specs + [
            {"key": "xg", "label": "xG/90", "secondary_label": "Conversion", "primary": {"kind": "per90_sum", "columns": ["xG"], "decimals": 2}, "secondary": {"kind": "weighted_avg", "columns": ["Goal conversion, %"], "decimals": 1, "pct": True}, "icon_name": "bi bi-graph-up-arrow", "accent_color": "#ef4444"},
            {"key": "shot_accuracy", "label": "Shot Accuracy", "secondary_label": "Progressive Runs/90", "primary": {"kind": "weighted_avg", "columns": ["Shots on target, %"], "decimals": 1, "pct": True}, "secondary": {"kind": "weighted_avg", "columns": ["Progressive runs per 90"], "decimals": 1}, "icon_name": "bi bi-crosshair2", "accent_color": "#22c55e"},
            {"key": "dribbles", "label": "Dribbles/90", "secondary_label": "Dribble Success", "primary": {"kind": "weighted_avg", "columns": ["Dribbles per 90"], "decimals": 1}, "secondary": {"kind": "weighted_avg", "columns": ["Successful dribbles, %"], "decimals": 1, "pct": True}, "icon_name": "bi bi-lightning-charge", "accent_color": "#06b6d4"},
        ]
    if pos_group == "Midfielder":
        return common_specs + [
            {"key": "passing", "label": "Pass Accuracy", "secondary_label": "Prog. Passes/90", "primary": {"kind": "weighted_avg", "columns": ["Accurate passes, %"], "decimals": 1, "pct": True}, "secondary": {"kind": "weighted_avg", "columns": ["Progressive passes per 90"], "decimals": 1}, "icon_name": "bi bi-bezier2", "accent_color": "#60a5fa"},
            {"key": "duels", "label": "Duels Won", "secondary_label": "Interceptions/90", "primary": {"kind": "weighted_avg", "columns": ["Duels won, %"], "decimals": 1, "pct": True}, "secondary": {"kind": "weighted_avg", "columns": ["Interceptions per 90"], "decimals": 1}, "icon_name": "bi bi-shield-check", "accent_color": "#14b8a6"},
            {"key": "attacking_actions", "label": "Attacking Actions/90", "secondary_label": "Prog. Runs/90", "primary": {"kind": "weighted_avg", "columns": ["Successful attacking actions per 90"], "decimals": 1}, "secondary": {"kind": "weighted_avg", "columns": ["Progressive runs per 90"], "decimals": 1}, "icon_name": "bi bi-magic", "accent_color": "#a855f7"},
        ]
    return common_specs + [
        {"key": "def_duels", "label": "Duels Won", "secondary_label": "Aerial Won", "primary": {"kind": "weighted_avg", "columns": ["Duels won, %"], "decimals": 1, "pct": True}, "secondary": {"kind": "weighted_avg", "columns": ["Aerial duels won, %"], "decimals": 1, "pct": True}, "icon_name": "bi bi-shield", "accent_color": "#14b8a6"},
        {"key": "def_interceptions", "label": "Interceptions/90", "secondary_label": "Pass Accuracy", "primary": {"kind": "weighted_avg", "columns": ["Interceptions per 90"], "decimals": 1}, "secondary": {"kind": "weighted_avg", "columns": ["Accurate passes, %"], "decimals": 1, "pct": True}, "icon_name": "bi bi-signpost-split", "accent_color": "#f59e0b"},
        {"key": "forward_passing", "label": "Forward Passes/90", "secondary_label": "Accurate Fwd Passes", "primary": {"kind": "weighted_avg", "columns": ["Forward passes per 90"], "decimals": 1}, "secondary": {"kind": "weighted_avg", "columns": ["Accurate forward passes, %"], "decimals": 1, "pct": True}, "icon_name": "bi bi-arrow-up-right-circle", "accent_color": "#60a5fa"},
    ]


def _career_kpi_metric_series(history_df: pd.DataFrame, metric_spec: Dict[str, Any]) -> Optional[pd.Series]:
    if not isinstance(history_df, pd.DataFrame) or history_df.empty or "Season" not in history_df.columns:
        return None
    plot_df = history_df.copy()
    plot_df["Season"] = plot_df["Season"].apply(_normalize_season_label)
    plot_df = plot_df.assign(_season_sort=plot_df["Season"].apply(_season_sort_key)).sort_values("_season_sort")
    minutes = pd.to_numeric(plot_df.get("Minutes played"), errors="coerce") if "Minutes played" in plot_df.columns else None
    kind = metric_spec.get("kind")
    chosen_column = next((column for column in metric_spec.get("columns", []) if column in plot_df.columns), None)
    if kind == "per90_sum":
        if not chosen_column or minutes is None:
            return None
        numerator = pd.to_numeric(plot_df[chosen_column], errors="coerce")
        series = numerator * 90.0 / minutes.replace(0, np.nan)
    elif chosen_column:
        series = pd.to_numeric(plot_df[chosen_column], errors="coerce")
    else:
        return None
    return pd.Series(series.values, index=plot_df["Season"]).dropna()


def _career_kpi_metric_aggregate(history_df: pd.DataFrame, metric_spec: Dict[str, Any]) -> Optional[float]:
    series = _career_kpi_metric_series(history_df, metric_spec)
    if series is None or series.empty:
        return None
    kind = metric_spec.get("kind")
    if kind == "sum":
        value = float(series.sum())
    elif kind == "weighted_avg":
        if "Minutes played" not in history_df.columns:
            value = float(series.mean())
        else:
            plot_df = history_df.copy()
            plot_df["Season"] = plot_df["Season"].apply(_normalize_season_label)
            plot_df = plot_df.assign(_season_sort=plot_df["Season"].apply(_season_sort_key)).sort_values("_season_sort")
            minute_map = pd.Series(pd.to_numeric(plot_df.get("Minutes played"), errors="coerce").values, index=plot_df["Season"])
            common_index = series.index.intersection(minute_map.index)
            weights = minute_map.loc[common_index].astype(float)
            metric_values = series.loc[common_index].astype(float)
            valid_mask = weights > 0
            value = float(np.average(metric_values[valid_mask], weights=weights[valid_mask])) if valid_mask.any() else float(metric_values.mean())
    else:
        value = float(series.iloc[-1])
    return None if pd.isna(value) else value


def _format_kpi_metric_value(value: Optional[float], metric_spec: Dict[str, Any]) -> str:
    if value is None:
        return "—"
    decimals = int(metric_spec.get("decimals", 0))
    if metric_spec.get("pct"):
        return f"{value:.{decimals}f}%"
    if decimals == 0:
        return f"{int(round(value)):,}"
    return f"{value:.{decimals}f}"


def _metric_icon_node(icon_name: str, accent_color: str) -> Any:
    if icon_name == "soccer-ball":
        return html.Img(src="/assets/icons/soccer-ball.svg", style={"width": "18px", "height": "18px", "display": "block", "opacity": "0.95"})
    if icon_name == "sport-shoe":
        return html.I(**{"data-lucide": "sport-shoe", "style": {"width": "18px", "height": "18px", "display": "block", "color": accent_color, "opacity": "0.95"}})
    return html.I(className=icon_name)


def _metric_card(label: str, value: str, sub_label: str, sub_value: str, icon_name: str, accent_color: str) -> html.Div:
    return html.Div(
        [
            html.Div(
                [
                    html.Span(_metric_icon_node(icon_name, accent_color), className="career-command-metric__icon", style={"--metric-accent": accent_color}),
                    html.Span(label, className="career-command-metric__label"),
                ],
                className="career-command-metric__top",
            ),
            html.Span(value, className="career-command-metric__value"),
            html.Div(
                [
                    html.Span(sub_label, className="career-command-metric__sub-label"),
                    html.Span(sub_value, className="career-command-metric__sub-value"),
                ],
                className="career-command-metric__sub",
            ),
        ],
        className="career-command-metric",
    )


def _build_career_kpi_trend_summary(history_df: pd.DataFrame, spec: Dict[str, Any]) -> html.Div:
    return html.Div(
        [
            html.Div(
                [
                    html.Span(spec["label"], className="career-kpi-trend-summary__label"),
                    html.Span(
                        _format_kpi_metric_value(_career_kpi_metric_aggregate(history_df, spec["primary"]), spec["primary"]),
                        className="career-kpi-trend-summary__value",
                    ),
                ],
                className="career-kpi-trend-summary__item",
            ),
            html.Div(
                [
                    html.Span(spec["secondary_label"], className="career-kpi-trend-summary__label"),
                    html.Span(
                        _format_kpi_metric_value(_career_kpi_metric_aggregate(history_df, spec["secondary"]), spec["secondary"]),
                        className="career-kpi-trend-summary__value",
                    ),
                ],
                className="career-kpi-trend-summary__item",
            ),
        ],
        className="career-kpi-trend-summary",
    )


def _build_career_kpi_trend_view_2d(history_df: pd.DataFrame, spec: Dict[str, Any], primary_series: pd.Series, secondary_series: pd.Series) -> Dict[str, Any]:
    seasons = list(dict.fromkeys(list(primary_series.index) + list(secondary_series.index)))
    plot_df = pd.DataFrame({"Season": seasons})
    plot_df = plot_df.assign(_season_sort=plot_df["Season"].apply(_season_sort_key)).sort_values("_season_sort")
    plot_df[spec["label"]] = plot_df["Season"].map(primary_series)
    plot_df[spec["secondary_label"]] = plot_df["Season"].map(secondary_series)
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=plot_df["Season"],
            y=plot_df[spec["label"]],
            mode="lines+markers",
            name=spec["label"],
            line=dict(color=spec["accent_color"], width=3, shape="spline", smoothing=0.8),
            marker=dict(size=8, color=spec["accent_color"]),
            hovertemplate=spec["label"] + ": %{y:.2f}<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=plot_df["Season"],
            y=plot_df[spec["secondary_label"]],
            mode="lines+markers",
            name=spec["secondary_label"],
            line=dict(color="rgba(225, 236, 255, 0.78)", width=2.5, dash="dot", shape="spline", smoothing=0.8),
            marker=dict(size=7, color="rgba(225, 236, 255, 0.92)"),
            yaxis="y2",
            hovertemplate=spec["secondary_label"] + ": %{y:.2f}<extra></extra>",
        )
    )
    fig.update_layout(
        xaxis_title="Season",
        yaxis_title=spec["label"],
        height=360,
        margin=dict(t=20, r=56, b=42, l=190),
        showlegend=True,
        hovermode="closest",
    )
    fig.update_xaxes(showspikes=False)
    fig.update_yaxes(showspikes=False)
    fig.update_layout(
        yaxis2=dict(
            title=dict(text=spec["secondary_label"], font=dict(color="rgba(225, 236, 255, 0.76)")),
            overlaying="y",
            side="right",
            showgrid=False,
            tickfont=dict(color="rgba(225, 236, 255, 0.76)"),
            showspikes=False,
        )
    )
    fig = glass_figure_layout(fig)
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        hoverlabel=dict(
            bgcolor="rgba(44, 47, 58, 0.92)",
            bordercolor="rgba(255, 255, 255, 0.14)",
            font_size=13,
            font_family="Roboto, sans-serif",
            font_color="rgba(245, 250, 255, 0.96)",
        ),
        legend=dict(
            bgcolor="rgba(0,0,0,0)",
            bordercolor="rgba(255,255,255,0.08)",
            borderwidth=1,
            x=-0.24,
            y=0.78,
            xanchor="left",
            yanchor="top",
            orientation="v",
            font=dict(size=14, color="rgba(245, 250, 255, 0.94)"),
        ),
    )
    return {
        "title": f"{spec['label']} Trend",
        "content": html.Div(
            [
                _build_career_kpi_trend_summary(history_df, spec),
                dcc.Graph(figure=fig, config={"displayModeBar": False}, className="career-kpi-trend-panel"),
            ]
        ),
    }


def _build_career_kpi_trend_view(player_name: str, player_id: str, metric_key: str) -> Dict[str, Any]:
    data = _fetch_dashboard_data(player_name, player_id)
    history_df = data.get("history_df", pd.DataFrame())
    pos_group = str(data.get("pos_group") or "")
    spec = next((item for item in _career_kpi_specs_for_position(pos_group) if item["key"] == metric_key), None)
    if spec is None or not isinstance(history_df, pd.DataFrame) or history_df.empty:
        return {"title": "KPI Trend", "content": html.P("Career KPI history is not available.", className="text-muted small mb-0")}
    primary_series = _career_kpi_metric_series(history_df, spec["primary"])
    secondary_series = _career_kpi_metric_series(history_df, spec["secondary"])
    if primary_series is None or secondary_series is None or primary_series.empty or secondary_series.empty:
        return {"title": f"{spec['label']} Trend", "content": html.P("Trend detail is not available for this KPI.", className="text-muted small mb-0")}
    return _build_career_kpi_trend_view_2d(history_df, spec, primary_series, secondary_series)


def _build_command_metrics_strip(data: Dict) -> html.Div:
    history_df = data.get("history_df", pd.DataFrame())
    pos_group = str(data.get("pos_group") or "")
    items = []
    for spec in _career_kpi_specs_for_position(pos_group):
        items.append(
            (
                spec["key"],
                spec["label"],
                _format_kpi_metric_value(_career_kpi_metric_aggregate(history_df, spec["primary"]), spec["primary"]),
                spec["secondary_label"],
                _format_kpi_metric_value(_career_kpi_metric_aggregate(history_df, spec["secondary"]), spec["secondary"]),
                spec["icon_name"],
                spec["accent_color"],
            )
        )
    return html.Div(
        [
            html.Button(
                _metric_card(label, value, sub_label, sub_value, icon_name, accent_color),
                id={"type": "career-kpi-trigger", "metric_key": metric_key},
                className="career-command-metric-button",
                n_clicks=0,
                type="button",
            )
            for metric_key, label, value, sub_label, sub_value, icon_name, accent_color in items
        ],
        className="career-command-metrics",
    )


def _build_career_progression_summary(
    data: Dict[str, Any],
    career_phase_data: Dict[str, Any],
    thesis: Optional[Dict[str, Any]] = None,
) -> str:
    thesis_body = str((thesis or {}).get("body") or "").strip()
    if thesis_body:
        return thesis_body

    phase = str((career_phase_data or {}).get("career_phase") or "unknown").lower()
    momentum = int((career_phase_data or {}).get("momentum_score") or 3)
    goals = int(data.get("goals", 0) or 0)
    assists = int(data.get("assists", 0) or 0)
    minutes = int(data.get("minutes_played", 0) or 0)
    production = []
    if goals:
        production.append(f"{goals} career goals")
    if assists:
        production.append(f"{assists} assists")
    if minutes:
        production.append(f"{minutes:,} minutes")
    production_text = ", ".join(production[:2]) if production else "the long-term record"
    if phase == "post-peak" and momentum >= 4:
        return f"You are beyond the standard peak window, but {production_text} still give your career real weight."
    if phase == "peak" and momentum >= 4:
        return f"You are in your peak phase, and {production_text} are reinforcing that status."
    if phase == "peak" and momentum <= 2:
        return f"You are still in your peak phase, but {production_text} are no longer translating into strong momentum."
    if phase == "building" and momentum >= 4:
        return f"You are still building your career, and {production_text} are now pushing momentum upward."
    if phase == "building" and momentum <= 2:
        return f"You are still building your career, and {production_text} have not yet turned into stronger momentum."
    if phase == "building":
        return f"You are still building your career, with {production_text} giving you a stable base."
    if phase == "development":
        return f"You are in an early development phase, and {production_text} are still shaping the direction of your career."
    if phase == "post-peak":
        return f"You are past the standard peak window, and {production_text} are now being tested by mixed momentum."
    return f"Your career phase is still being defined, with {production_text} as the clearest current reference."


def _build_career_thesis_chip(item: Dict[str, Any]) -> html.Span:
    tone = str(item.get("tone") or "neutral")
    label = str(item.get("label") or "").strip()
    value = str(item.get("value") or "").strip()
    return html.Span(
        [html.Span(label, className="career-command-chip__label"), html.Span(value, className="career-command-chip__value")],
        className=f"career-command-chip career-command-chip--{tone}",
    )


def _build_support_chip(label: str, value: str, tone: str = "neutral") -> Dict[str, Any]:
    return {"label": label, "value": value, "tone": tone}


def _get_career_thesis_support_groups(
    data: Dict[str, Any],
    career_phase_data: Dict[str, Any],
    thesis: Dict[str, Any],
) -> Dict[str, List[Dict[str, Any]]]:
    items = [item for item in [*(thesis.get("drivers") or []), *(thesis.get("risks") or [])] if isinstance(item, dict)]
    features = (career_phase_data or {}).get("progression_features")
    if hasattr(features, "peak_range"):
        peak_range = getattr(features, "peak_range", ())
        position_group = getattr(features, "position_group", "")
    elif isinstance(features, dict):
        peak_range = features.get("peak_range") or ()
        position_group = features.get("position_group") or ""
    else:
        peak_range = ()
        position_group = data.get("pos_group") or ""

    momentum_keywords = {"trend", "role signal", "consistency", "goal contribution", "attacking output", "minutes"}
    momentum_items = [
        item for item in items
        if any(keyword in str(item.get("label") or "").lower() for keyword in momentum_keywords)
    ][:5]

    phase_items: List[Dict[str, Any]] = []
    age = career_phase_data.get("age") or data.get("age")
    if age:
        phase_items.append(_build_support_chip("Age", str(age), "neutral"))
    if position_group:
        phase_items.append(_build_support_chip("Position", str(position_group), "neutral"))
    if isinstance(peak_range, (tuple, list)) and len(peak_range) == 2:
        phase_items.append(_build_support_chip("Peak window", f"{peak_range[0]}-{peak_range[1]}", "neutral"))
    phase_label = _format_career_phase_display(career_phase_data)
    if phase_label:
        phase_items.append(_build_support_chip("Resolved phase", phase_label, "neutral"))

    synthesis_items: List[Dict[str, Any]] = []
    minutes = int(data.get("minutes_played", 0) or 0)
    goals = int(data.get("goals", 0) or 0)
    assists = int(data.get("assists", 0) or 0)
    if goals:
        synthesis_items.append(_build_support_chip("Career goals", str(goals), "positive"))
    if assists:
        synthesis_items.append(_build_support_chip("Career assists", str(assists), "positive"))
    if minutes:
        synthesis_items.append(_build_support_chip("Career minutes", f"{minutes:,}", "positive"))

    return {
        "summary": synthesis_items,
        "momentum": momentum_items,
        "phase": phase_items,
    }


def _build_career_support_tooltip(title: str, chips: List[Dict[str, Any]]) -> html.Div:
    return html.Div(
        [
            html.Div(title, className="career-command-chip-group__title"),
            html.Div(
                [_build_career_thesis_chip(item) for item in chips],
                className="career-command-chip-group__chips",
            ),
        ],
        className="career-command-chip-group",
    )


def _extract_season_rating_series(history_df: pd.DataFrame) -> Optional[pd.DataFrame]:
    if not isinstance(history_df, pd.DataFrame) or history_df.empty or "Season" not in history_df.columns:
        return None

    rating_columns = [
        "Rating",
        "rating",
        "Average rating",
        "average_rating",
        "besoccer_season_rating",
        "besoccer_rating",
        "Besoccer rating",
        "Sofascore rating",
        "sofascore_rating",
    ]
    rating_col = next((column for column in rating_columns if column in history_df.columns), None)
    if not rating_col:
        return None

    plot_df = history_df[["Season", rating_col]].copy()
    plot_df[rating_col] = pd.to_numeric(plot_df[rating_col], errors="coerce")
    plot_df = plot_df.dropna(subset=[rating_col]).reset_index(drop=True)
    if plot_df.empty:
        return None

    plot_df["Season"] = plot_df["Season"].apply(_normalize_season_label)
    plot_df = (
        plot_df.assign(_season_sort=plot_df["Season"].apply(_season_sort_key))
        .sort_values("_season_sort")
        .drop(columns="_season_sort")
        .reset_index(drop=True)
    )
    plot_df = plot_df.rename(columns={rating_col: "Rating"})
    return plot_df


def _build_career_progression_rating_chart(data: Dict[str, Any]) -> Optional[html.Div]:
    history_df = data.get("history_df", pd.DataFrame())
    plot_df = _extract_season_rating_series(history_df)
    if plot_df is None or plot_df.empty:
        return None

    latest_rating = float(plot_df["Rating"].iloc[-1])
    best_rating = float(plot_df["Rating"].max())
    best_season = str(plot_df.loc[plot_df["Rating"].idxmax(), "Season"])

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=plot_df["Season"],
            y=plot_df["Rating"],
            mode="lines",
            line=dict(color="#ffcf70", width=3, shape="spline", smoothing=0.7),
            name="Season rating",
            hovertemplate="Rating %{y:.2f}<extra></extra>",
        )
    )
    fig = glass_figure_layout(fig)
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=34, r=18, t=12, b=34),
        height=400,
        hovermode="x unified",
        showlegend=False,
        legend=dict(
            bgcolor="rgba(0,0,0,0)",
            bordercolor="rgba(255,255,255,0.08)",
            borderwidth=1,
        ),
        hoverlabel=dict(
            bgcolor="rgba(24,24,26,0.96)",
            bordercolor="rgba(255,255,255,0.12)",
            font_size=13,
            font_family="Roboto, sans-serif",
            font_color="#FFFFFF",
        ),
    )
    fig.update_xaxes(title=None, ticklabelstandoff=8)
    fig.update_yaxes(title="Rating", range=[0, 10], tick0=0, dtick=1, tickformat=".1f")

    return html.Div(
        [
            html.Div(
                [
                    html.Div("Season Rating", className="career-command-trend__title"),
                    html.Div(
                        [
                            html.Span(f"{latest_rating:.2f}", className="career-command-trend__stat-value"),
                            html.Span("latest", className="career-command-trend__stat-label"),
                            html.Span(f"Best {best_rating:.2f} in {best_season}", className="career-command-trend__best"),
                        ],
                        className="career-command-trend__meta",
                    ),
                ],
                className="career-command-trend__header",
            ),
            dcc.Graph(
                figure=fig,
                config={"displayModeBar": False, "responsive": True},
                className="career-command-trend__graph",
                responsive=True,
                style={"width": "100%", "minWidth": "0", "height": "400px"},
            ),
        ],
        className="career-command-trend",
    )


def _build_career_command(
    data: Dict,
    career_phase_data: Dict[str, Any],
    brief: Any,
) -> html.Div:
    thesis = brief.career_thesis
    trajectory_label = "Career Progression"
    body = _build_career_progression_summary(data, career_phase_data, thesis)
    momentum = int(career_phase_data.get("momentum_score", 3) or 3)
    phase_display = _format_career_phase_display(career_phase_data)
    support_groups = _get_career_thesis_support_groups(data, career_phase_data, thesis)
    rating_chart = _build_career_progression_rating_chart(data)
    summary_id = "career-progression-summary-panel"
    momentum_id = "career-progression-momentum-kpi"
    phase_id = "career-progression-phase-kpi"

    tooltip_nodes: List[Any] = []
    if support_groups.get("summary"):
        tooltip_nodes.append(
            dbc.Tooltip(
                _build_career_support_tooltip("Career synthesis is based on", support_groups["summary"]),
                target=summary_id,
                placement="top",
                className="ai-tooltip-dark career-command-tooltip",
            )
        )
    if support_groups.get("momentum"):
        tooltip_nodes.append(
            dbc.Tooltip(
                _build_career_support_tooltip("Momentum is based on", support_groups["momentum"]),
                target=momentum_id,
                placement="top",
                className="ai-tooltip-dark career-command-tooltip",
            )
        )
    if support_groups.get("phase"):
        tooltip_nodes.append(
            dbc.Tooltip(
                _build_career_support_tooltip("Career phase is based on", support_groups["phase"]),
                target=phase_id,
                placement="top",
                className="ai-tooltip-dark career-command-tooltip",
            )
        )

    return html.Div(
        className="career-command-card",
        children=[
            html.Div(
                className="career-command-card__hero",
                children=[
                    html.Div(_build_identity_hero(data, career_phase_data), className="career-command-card__identity"),
                    html.Div(
                        className="career-command-card__summary",
                        children=[
                            html.Div(
                                [
                                    html.Span(html.I(className="bi bi-graph-up-arrow"), className="career-dashboard-section__icon"),
                                    html.H6(trajectory_label, className="career-dashboard-section__title career-command-card__title"),
                                ],
                                className="career-dashboard-section__title-row career-command-card__title-row",
                            ),
                            html.Div(
                                [
                                    html.Div(
                                        html.P(body, className="career-command-card__body"),
                                        className="career-command-card__headline-panel career-command-card__tooltip-target",
                                        id=summary_id,
                                    ),
                                    html.Div(
                                        [
                                            html.Div(
                                                [
                                                    html.Span("Momentum", className="career-command-kpi__label"),
                                                    _build_momentum_dots(momentum),
                                                ],
                                                className="career-command-kpi career-command-card__tooltip-target",
                                                id=momentum_id,
                                            ),
                                            html.Div(
                                                [
                                                    html.Span("Phase", className="career-command-kpi__label"),
                                                    _build_phase_badge(phase_display, class_name="career-phase-badge career-phase-badge--inline"),
                                                ],
                                                className="career-command-kpi career-command-card__tooltip-target",
                                                id=phase_id,
                                            ),
                                        ],
                                        className="career-command-kpis career-command-kpis--side",
                                    ),
                                ],
                                className="career-command-card__headline-layout",
                            ),
                            *tooltip_nodes,
                        ],
                    ),
                ],
            ),
            rating_chart,
            _build_command_metrics_strip(data),
        ],
    )


def _build_insight_card(item: Any, section_label: str, source: str = "dashboard") -> html.Div:
    meta = _get_career_surface_meta(item, section_label)
    llm_generated = bool(getattr(item, "llm_generated", False))
    resolved_evidence_key = resolve_career_surface_evidence_key(
        getattr(item, "evidence_key", ""),
        label=getattr(item, "title", ""),
    )
    focus_metric = str(getattr(item, "focus_metric", "") or "")
    stat_items = []
    if getattr(item, "badge_value", "") and getattr(item, "badge_label", ""):
        stat_items.append((item.badge_value, item.badge_label))
    if getattr(item, "secondary_value", "") and getattr(item, "secondary_label", ""):
        stat_items.append((item.secondary_value, item.secondary_label))
    return html.Div(
        className=f"career-dashboard-card career-dashboard-card--{getattr(item, 'emphasis', 'neutral')}",
        children=[
            html.Div(
                [
                    html.Div(
                        [
                            html.Span(html.I(className=meta["icon_class"]), className="career-dashboard-card__icon-glyph"),
                            html.Div(
                                [
                                    html.Div(section_label, className="career-dashboard-card__eyebrow"),
                                    html.Div(
                                        [
                                            html.Span(meta["tone_label"]),
                                            _build_ai_origin_badge(llm_generated),
                                        ],
                                        className="career-dashboard-card__tone",
                                    ),
                                ],
                                className="career-dashboard-card__meta",
                            ),
                        ],
                        className="career-dashboard-card__top",
                    ),
                ]
            ),
            html.Div(item.title, className="career-dashboard-card__title"),
            html.Div(
                [
                    html.Div(
                        [
                            html.Div(value, className="career-dashboard-card__stat-value"),
                            html.Div(label, className="career-dashboard-card__stat-label"),
                        ],
                        className="career-dashboard-card__stat",
                    )
                    for value, label in stat_items
                ],
                className="career-dashboard-card__stats",
            ) if stat_items else html.Span(),
            html.P(item.body, className="career-dashboard-card__body"),
            html.Div(
                [
                    html.Span(html.I(className="bi bi-activity"), className="career-dashboard-card__support-icon"),
                    html.P(item.support, className="career-dashboard-card__support"),
                ],
                className="career-dashboard-card__support-wrap",
            ),
            html.Div(
                _build_career_evidence_button(
                    resolved_evidence_key,
                    source=source,
                    trigger_index=f"{section_label.lower()}:{getattr(item, 'title', '')}",
                    focus_metric=focus_metric,
                ),
                className="career-dashboard-card__footer",
            ),
        ],
    )


def _build_minutes_trend_evidence(data: Dict) -> html.Div:
    history_df = data.get("history_df", pd.DataFrame())
    header = html.H6([
        html.I(className="bi bi-stopwatch me-2"),
        html.Span("Minutes Trend", className="animate-glass-draw"),
    ], className="mb-3 fw-semibold", style={"color": "var(--accent-cyan, #00d4ff)"})

    if history_df is None or history_df.empty:
        return html.Div([header, html.P("Minutes history is not available.", className="text-muted small")])

    minutes_col = next((c for c in history_df.columns if "minute" in c.lower()), None)
    if not minutes_col or "Season" not in history_df.columns:
        return html.Div([header, html.P("Minutes history is not available.", className="text-muted small")])

    plot_df = history_df[["Season", minutes_col]].copy()
    plot_df[minutes_col] = pd.to_numeric(plot_df[minutes_col], errors="coerce").fillna(0)

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=plot_df["Season"],
        y=plot_df[minutes_col],
        mode="lines+markers",
        line=dict(color=HKFATheme.ACCENT_BLUE, width=3),
        marker=dict(size=8, color=HKFATheme.ACCENT_CYAN if hasattr(HKFATheme, "ACCENT_CYAN") else HKFATheme.ACCENT_BLUE),
        fill="tozeroy",
        fillcolor="rgba(83, 228, 255, 0.12)",
        name="Minutes",
        hovertemplate="%{x}<br>%{y:.0f} minutes<extra></extra>",
    ))
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=36, r=18, t=10, b=46),
        height=280,
        xaxis=dict(title=None, ticklabelstandoff=8),
        yaxis=dict(title="Minutes", rangemode="tozero"),
        hovermode="x unified",
        showlegend=False,
    )
    fig = glass_figure_layout(fig)

    latest_minutes = int(plot_df[minutes_col].iloc[-1]) if not plot_df.empty else 0
    peak_minutes = int(plot_df[minutes_col].max()) if not plot_df.empty else 0
    latest_season = str(plot_df["Season"].iloc[-1]) if not plot_df.empty else "—"

    summary = html.Div(
        [
            html.Div(
                [
                    html.Div(f"{latest_minutes:,}", className="career-command-kpi__value"),
                    html.Div(f"{latest_season} minutes", className="career-command-kpi__label"),
                ],
                className="career-command-kpi",
            ),
            html.Div(
                [
                    html.Div(f"{peak_minutes:,}", className="career-command-kpi__value"),
                    html.Div("career peak", className="career-command-kpi__label"),
                ],
                className="career-command-kpi",
            ),
        ],
        className="career-command-kpis",
    )

    return html.Div([
        header,
        summary,
        dcc.Graph(
            figure=fig,
            config={"displayModeBar": False, "responsive": True},
            className="w-100",
            responsive=True,
            style={"width": "100%", "minWidth": "0"},
        ),
    ])


def _build_recent_form_evidence(data: Dict) -> html.Div:
    recent_windows = data.get("recent_form_windows") or {}
    comparison = (recent_windows.get("comparisons") or {}).get("last5_vs_previous5") or {}
    last5 = recent_windows.get("last5") or {}
    previous5 = recent_windows.get("previous5") or {}
    header = html.H6([
        html.I(className="bi bi-activity me-2"),
        html.Span("Recent Form", className="animate-glass-draw"),
    ], className="mb-3 fw-semibold", style={"color": "var(--accent-cyan, #00d4ff)"})

    if not comparison or not last5 or not previous5:
        return html.Div([header, html.P("Recent form comparison is not available.", className="text-muted small")])

    def _per90(total: Any, minutes: Any) -> float:
        try:
            total_value = float(total)
            minutes_value = float(minutes)
        except (TypeError, ValueError):
            return 0.0
        if minutes_value <= 0:
            return 0.0
        return (total_value * 90.0) / minutes_value

    compare_rows = [
        ("Minutes", int(last5.get("minutes_total", 0) or 0), int(previous5.get("minutes_total", 0) or 0), comparison.get("minutes_trend_pct", 0.0), False),
        ("Goals", int(last5.get("goals_total", 0) or 0), int(previous5.get("goals_total", 0) or 0), comparison.get("goals_trend_pct", 0.0), False),
        ("Assists", int(last5.get("assists_total", 0) or 0), int(previous5.get("assists_total", 0) or 0), comparison.get("assists_trend_pct", 0.0), False),
        (
            "Goal contributions/90",
            round(_per90(last5.get("goal_contributions_total", 0), last5.get("minutes_total", 0)), 2),
            round(_per90(previous5.get("goal_contributions_total", 0), previous5.get("minutes_total", 0)), 2),
            round(
                (
                    (
                        _per90(last5.get("goal_contributions_total", 0), last5.get("minutes_total", 0))
                        - _per90(previous5.get("goal_contributions_total", 0), previous5.get("minutes_total", 0))
                    )
                    / abs(_per90(previous5.get("goal_contributions_total", 0), previous5.get("minutes_total", 0)))
                    * 100.0
                ),
                2,
            ) if _per90(previous5.get("goal_contributions_total", 0), previous5.get("minutes_total", 0)) > 0 else 0.0,
            True,
        ),
    ]

    table_rows = []
    for label, current_value, previous_value, delta_pct, is_decimal in compare_rows:
        tone = HKFATheme.POSITIVE if float(delta_pct) > 0 else (HKFATheme.NEGATIVE if float(delta_pct) < 0 else HKFATheme.TEXT_SECONDARY)
        current_display = f"{current_value:.2f}" if is_decimal else f"{current_value:,}"
        previous_display = f"{previous_value:.2f}" if is_decimal else f"{previous_value:,}"
        table_rows.append(
            html.Tr(
                [
                    html.Td(label),
                    html.Td(current_display),
                    html.Td(previous_display),
                    html.Td(f"{float(delta_pct):+.1f}%", style={"color": tone, "fontWeight": "600"}),
                ]
            )
        )

    summary = html.Div(
        [
            html.Div(
                [
                    html.Div("Last 5", className="career-command-kpi__label"),
                    html.Div(f"{int(last5.get('minutes_total', 0) or 0):,}", className="career-command-kpi__value"),
                    html.Div("minutes", className="career-command-kpi__label"),
                ],
                className="career-command-kpi",
            ),
            html.Div(
                [
                    html.Div("Previous 5", className="career-command-kpi__label"),
                    html.Div(f"{int(previous5.get('minutes_total', 0) or 0):,}", className="career-command-kpi__value"),
                    html.Div("minutes", className="career-command-kpi__label"),
                ],
                className="career-command-kpi",
            ),
        ],
        className="career-command-kpis",
    )

    table = dbc.Table(
        [
            html.Thead(html.Tr([html.Th("Metric"), html.Th("Last 5"), html.Th("Previous 5"), html.Th("Delta")])),
            html.Tbody(table_rows),
        ],
        bordered=False,
        hover=True,
        responsive=True,
        className="mb-0",
    )

    return html.Div([header, summary, table])


def _build_career_trend_evidence(data: Dict, career_facts: Optional[Dict[str, Any]] = None) -> html.Div:
    history_df = data.get("history_df", pd.DataFrame())
    header = html.H6([
        html.I(className="bi bi-graph-up-arrow me-2"),
        html.Span("Career Trend", className="animate-glass-draw"),
    ], className="mb-3 fw-semibold", style={"color": "var(--accent-cyan, #00d4ff)"})

    if history_df is None or history_df.empty or "Season" not in history_df.columns:
        return html.Div([header, html.P("Career trend is not available.", className="text-muted small")])

    summary = (career_facts or {}).get("career_summary") or {}
    primary_metric = str(summary.get("primary_metric") or "")
    minutes_col = next((c for c in history_df.columns if "minute" in str(c).lower()), None)
    metric_col = primary_metric if primary_metric in history_df.columns else (minutes_col or "")
    if not metric_col:
        return html.Div([header, html.P("Career trend is not available.", className="text-muted small")])

    plot_df = history_df[["Season", metric_col]].copy()
    plot_df[metric_col] = pd.to_numeric(plot_df[metric_col], errors="coerce")
    plot_df = plot_df.dropna(subset=[metric_col]).reset_index(drop=True)
    if plot_df.empty:
        return html.Div([header, html.P("Career trend is not available.", className="text-muted small")])

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=plot_df["Season"],
        y=plot_df[metric_col],
        mode="lines+markers",
        line=dict(color=HKFATheme.ACCENT_BLUE, width=3),
        marker=dict(size=8, color=HKFATheme.ACCENT_CYAN if hasattr(HKFATheme, "ACCENT_CYAN") else HKFATheme.ACCENT_BLUE),
        fill="tozeroy",
        fillcolor="rgba(83, 228, 255, 0.10)",
        hovertemplate=f"%{{x}}<br>{metric_col}: %{{y:.2f}}<extra></extra>",
    ))
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=36, r=18, t=10, b=46),
        height=300,
        xaxis=dict(title=None, ticklabelstandoff=8),
        yaxis=dict(title=metric_col, rangemode="tozero"),
        hovermode="x unified",
        showlegend=False,
    )
    fig = glass_figure_layout(fig)

    latest_value = float(plot_df[metric_col].iloc[-1]) if not plot_df.empty else 0.0
    metric_trend_pct = float(summary.get("primary_metric_trend_pct") or 0.0)
    consistency_level = str(summary.get("consistency_level") or "MODERADA")

    meta = html.Div(
        [
            html.Div(
                [
                    html.Div(f"{latest_value:.1f}", className="career-command-kpi__value"),
                    html.Div(f"latest {metric_col.lower()}", className="career-command-kpi__label"),
                ],
                className="career-command-kpi",
            ),
            html.Div(
                [
                    html.Div(f"{metric_trend_pct:+.1f}%", className="career-command-kpi__value"),
                    html.Div("trend", className="career-command-kpi__label"),
                ],
                className="career-command-kpi",
            ),
            html.Div(
                [
                    html.Div(consistency_level, className="career-command-kpi__value"),
                    html.Div("consistency", className="career-command-kpi__label"),
                ],
                className="career-command-kpi",
            ),
        ],
        className="career-command-kpis",
    )

    return html.Div([
        header,
        meta,
        dcc.Graph(
            figure=fig,
            config={"displayModeBar": False, "responsive": True},
            className="w-100",
            responsive=True,
            style={"width": "100%", "minWidth": "0"},
        ),
    ])


def _build_career_phase_resolution_evidence(
    data: Dict[str, Any],
    career_phase_data: Dict[str, Any],
    career_signals: Dict[str, Any],
    career_facts: Optional[Dict[str, Any]] = None,
) -> html.Div:
    header = html.H6([
        html.I(className="bi bi-signpost-split me-2"),
        html.Span("Career Phase", className="animate-glass-draw"),
    ], className="mb-3 fw-semibold", style={"color": "var(--accent-cyan, #00d4ff)"})

    evidence = ((career_facts or {}).get("evidence_facts") or {}).get("career_phase_resolution") or {}
    resolution = dict(evidence.get("progression_resolution") or career_phase_data.get("progression_resolution") or {})
    recommended_phase = str(
        career_phase_data.get("recommended_phase")
        or resolution.get("recommended_phase")
        or "Find Consistency"
    )
    peak_range = evidence.get("peak_range") or career_phase_data.get("peak_range") or []
    age = int(evidence.get("age") or career_phase_data.get("age") or data.get("age") or 0)
    phase_key = str(career_phase_data.get("career_phase") or "unknown")
    phase = phase_key.replace("-", " ").title()
    momentum = int(career_phase_data.get("momentum_score") or 3)
    transfer_quality = str(evidence.get("transfer_window_quality") or ((career_signals.get("transfer_window") or {}).get("quality") or "MODERADA"))
    consistency_level = str(evidence.get("consistency_level") or ((career_signals.get("consistency_score") or {}).get("level") or "MODERADA"))
    base_phase = str(resolution.get("base_phase") or "").replace("-", " ").title()
    resolved_phase = str(resolution.get("resolved_phase") or phase_key).replace("-", " ").title()
    peak_start = int(peak_range[0]) if len(peak_range) == 2 else 0
    peak_end = int(peak_range[1]) if len(peak_range) == 2 else 0

    if recommended_phase == "Ambitious":
        current_read = "Ambitious"
        summary_title = "The comparative case is strong enough to justify aiming higher."
        summary_body = "This read usually means the player is already competitive in the right groups and the remaining gap to top tier is manageable."
    elif recommended_phase == "Keep Pushing":
        current_read = "Keep Pushing"
        summary_title = "The trend is moving the right way, but the case still needs more proof."
        summary_body = "The level is promising enough to keep pressing forward, even if the strongest benchmark has not been fully reached yet."
    elif recommended_phase == "Maintain Consistency":
        current_read = "Maintain Consistency"
        summary_title = "The level is credible now, so the main task is proving it holds."
        summary_body = "This read is less about chasing a bigger jump immediately and more about making the same level repeatable."
    else:
        current_read = "Find Consistency"
        summary_title = "The next step still depends on making the level feel more reliable."
        summary_body = "This read means the player has useful signals, but too much of the case still depends on unstable role, form, or context."

    if resolution.get("adjustment_applied") and base_phase and base_phase != resolved_phase:
        current_read = f"{current_read} ({base_phase} -> {resolved_phase})"

    watch_next = str(resolution.get("next_condition") or "Watch whether minutes and consistency hold across the next run.")

    kpis = html.Div(
        [
            html.Div([html.Div(recommended_phase, className="career-command-kpi__value"), html.Div("recommendation", className="career-command-kpi__label")], className="career-command-kpi"),
            html.Div([html.Div(f"{momentum}/5", className="career-command-kpi__value"), html.Div("momentum", className="career-command-kpi__label")], className="career-command-kpi"),
            html.Div([html.Div(f"{age}" if age else "—", className="career-command-kpi__value"), html.Div("age", className="career-command-kpi__label")], className="career-command-kpi"),
            html.Div([html.Div(str(resolution.get("validation_status") or "accept").replace("_", " ").title(), className="career-command-kpi__value"), html.Div("validator", className="career-command-kpi__label")], className="career-command-kpi"),
        ],
        className="career-command-kpis",
    )

    detail_rows = [
        ("Peak window", f"{peak_range[0]}-{peak_range[1]}" if len(peak_range) == 2 else "—"),
        ("Current read", current_read),
        ("Consistency", consistency_level),
        ("Window", transfer_quality),
        ("Watch next", watch_next),
    ]

    body = dbc.Table(
        [html.Tbody([html.Tr([html.Td(label), html.Td(value)]) for label, value in detail_rows])],
        bordered=False,
        hover=True,
        responsive=True,
        className="mb-0",
    )

    summary = html.Div(
        [
            html.Div("Why this read", className="career-dashboard-card__eyebrow"),
            html.Div(summary_title, className="career-outlook-card__title"),
            html.P(summary_body, className="career-dashboard-card__body"),
        ],
        className="career-outlook-card mb-3",
    )

    return html.Div([header, kpis, summary, html.Div(body, className="career-outlook-card")])


def _build_comparative_dimension_evidence(title: str, evidence: Dict[str, Any], *, icon_class: str = "bi bi-bar-chart-line") -> html.Div:
    header = html.H6([
        html.I(className=f"{icon_class} me-2"),
        html.Span(title, className="animate-glass-draw"),
    ], className="mb-3 fw-semibold", style={"color": "var(--accent-cyan, #00d4ff)"})
    dimension = evidence.get("dimension") or {}
    if not dimension:
        return html.Div([header, html.P("Comparison data is not available for this view yet.", className="text-muted small")])

    percentile = float(dimension.get("percentile") or 0.0)
    average_gap = float(dimension.get("average_gap") or 0.0)
    top_gap = float(dimension.get("top_tier_gap") or 0.0)
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=["Player", "Average", "Top Tier"],
        y=[
            float(dimension.get("player_value") or 0.0),
            float(dimension.get("average_value") or 0.0),
            float(dimension.get("top_tier_value") or 0.0),
        ],
        marker_color=["#00d4ff", "rgba(255,255,255,0.45)", "#f5b942"],
    ))
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=24, r=12, t=10, b=36),
        height=280,
        showlegend=False,
    )
    fig = glass_figure_layout(fig)
    kpis = html.Div(
        [
            html.Div([html.Div(f"{percentile:.1f}", className="career-command-kpi__value"), html.Div("percentile", className="career-command-kpi__label")], className="career-command-kpi"),
            html.Div([html.Div(f"{average_gap:+.1f}", className="career-command-kpi__value"), html.Div("vs avg", className="career-command-kpi__label")], className="career-command-kpi"),
            html.Div([html.Div(f"{top_gap:+.1f}", className="career-command-kpi__value"), html.Div("vs top tier", className="career-command-kpi__label")], className="career-command-kpi"),
        ],
        className="career-command-kpis",
    )
    return html.Div([header, kpis, dcc.Graph(figure=fig, config={"displayModeBar": False})])


def _build_score_shell_evidence(title: str, evidence: Dict[str, Any], metric_key: str, label_key: str) -> html.Div:
    header = html.H6([
        html.I(className="bi bi-graph-up-arrow me-2"),
        html.Span(title, className="animate-glass-draw"),
    ], className="mb-3 fw-semibold", style={"color": "var(--accent-cyan, #00d4ff)"})
    score_value = float(evidence.get(metric_key) or 0.0)
    label_value = str(evidence.get(label_key) or "unavailable").replace("_", " ")
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=score_value,
        gauge={"axis": {"range": [0, 100]}, "bar": {"color": "#00d4ff"}},
    ))
    fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", margin=dict(l=12, r=12, t=12, b=12), height=260)
    return html.Div([
        header,
        html.Div(
            [
                html.Div([html.Div(f"{score_value:.1f}", className="career-command-kpi__value"), html.Div("score", className="career-command-kpi__label")], className="career-command-kpi"),
                html.Div([html.Div(label_value.title(), className="career-command-kpi__value"), html.Div("read", className="career-command-kpi__label")], className="career-command-kpi"),
            ],
            className="career-command-kpis",
        ),
        dcc.Graph(figure=fig, config={"displayModeBar": False}),
    ])


def _format_context_read_label(value: str) -> str:
    normalized = str(value or "").strip().lower()
    mapping = {
        "driving_team_context": "Driving Team Context",
        "outperforming_team": "Outperforming Team",
        "balanced": "Balanced",
        "carried_by_team": "Not Yet Driving Context",
        "prime_window": "Prime Window",
        "late_prime": "Late Prime",
        "early_window": "Early Window",
        "late_cycle": "Late Cycle",
        "high": "High",
        "moderate": "Moderate",
        "low": "Low",
    }
    if normalized in mapping:
        return mapping[normalized]
    return str(value or "").replace("_", " ").title()


def _build_team_context_evidence(evidence: Dict[str, Any]) -> html.Div:
    header = html.H6([
        html.I(className="bi bi-diagram-3 me-2"),
        html.Span("Team Context", className="animate-glass-draw"),
    ], className="mb-3 fw-semibold", style={"color": "var(--accent-cyan, #00d4ff)"})

    score_value = float(evidence.get("team_context_score") or 0.0)
    label_value = _format_context_read_label(str(evidence.get("team_context_label") or "balanced"))
    benchmark_metric = str(evidence.get("benchmark_metric") or "current benchmark")
    comparison_rows = [
        row for row in (evidence.get("comparison_rows") or [])
        if isinstance(row, dict) and row.get("available", True)
    ]
    context_scores = [row for row in (evidence.get("context_scores") or []) if isinstance(row, dict)]

    top_kpis = html.Div(
        [
            html.Div([html.Div(f"{score_value:.1f}", className="career-command-kpi__value"), html.Div("score", className="career-command-kpi__label")], className="career-command-kpi"),
            html.Div([html.Div(label_value, className="career-command-kpi__value"), html.Div("read", className="career-command-kpi__label")], className="career-command-kpi"),
            html.Div([html.Div(benchmark_metric.title(), className="career-command-kpi__value"), html.Div("benchmark metric", className="career-command-kpi__label")], className="career-command-kpi"),
        ],
        className="career-command-kpis",
    )

    comparison_block: html.Div
    if comparison_rows:
        legend = html.Div(
            [
                html.Div([
                    html.Div(style={"width": "10px", "height": "10px", "borderRadius": "999px", "backgroundColor": "#00d4ff", "marginRight": "6px"}),
                    html.Span("Player", style={"fontSize": "0.72rem", "color": HKFATheme.TEXT_SECONDARY}),
                ], style={"display": "flex", "alignItems": "center", "marginRight": "14px"}),
                html.Div([
                    html.Div(style={"width": "3px", "height": "18px", "backgroundColor": "#FFFFFF", "boxShadow": "0 0 8px rgba(255,255,255,0.9)", "marginRight": "6px"}),
                    html.Span("Average", style={"fontSize": "0.72rem", "color": HKFATheme.TEXT_SECONDARY}),
                ], style={"display": "flex", "alignItems": "center", "marginRight": "14px"}),
                html.Div([
                    html.Div(style={"width": "3px", "height": "18px", "backgroundColor": "#f5b942", "boxShadow": "0 0 8px rgba(245,184,66,0.9)", "marginRight": "6px"}),
                    html.Span("Top Tier", style={"fontSize": "0.72rem", "color": HKFATheme.TEXT_SECONDARY}),
                ], style={"display": "flex", "alignItems": "center"}),
            ],
            style={"display": "flex", "justifyContent": "flex-end", "marginBottom": "10px", "flexWrap": "wrap", "gap": "8px"},
        )

        comparison_rows_ui = []
        for row in comparison_rows:
            label = str(row.get("label") or "")
            player_value = float(row.get("player_value") or 0.0)
            average_value = float(row.get("average_value") or 0.0)
            top_tier_value = float(row.get("top_tier_value") or 0.0)
            percentile = float(row.get("percentile") or 0.0)
            average_gap = float(row.get("average_gap") or 0.0)
            top_gap = float(row.get("top_tier_gap") or 0.0)
            scale_max = max(player_value, average_value, top_tier_value, 1.0)
            player_width = max(2.0, min(100.0, (player_value / scale_max) * 100.0))
            average_marker = max(0.5, min(99.5, (average_value / scale_max) * 100.0))
            top_tier_marker = max(0.5, min(99.5, (top_tier_value / scale_max) * 100.0))

            comparison_rows_ui.append(
                html.Div(
                    [
                        html.Div(
                            [
                                html.Span(label, style={"color": HKFATheme.TEXT_SECONDARY, "fontSize": "0.86rem"}),
                                html.Div(
                                    [
                                        html.Span(f"P{percentile:.1f}", style={"color": HKFATheme.TEXT_PRIMARY, "fontSize": "0.82rem", "fontWeight": "600"}),
                                        html.Span(
                                            f"vs avg {average_gap:+.1f} · vs top tier {top_gap:+.1f}",
                                            style={"color": HKFATheme.TEXT_SECONDARY, "fontSize": "0.72rem", "marginLeft": "8px"},
                                        ),
                                    ],
                                    style={"display": "flex", "alignItems": "center", "flexWrap": "wrap", "justifyContent": "flex-end"},
                                ),
                            ],
                            style={"display": "flex", "justifyContent": "space-between", "alignItems": "center", "gap": "12px"},
                        ),
                        html.Div(
                            style={"position": "relative", "marginTop": "6px", "marginBottom": "14px"},
                            children=[
                                html.Div(
                                    style={
                                        "height": "10px",
                                        "borderRadius": "999px",
                                        "background": "rgba(255,255,255,0.06)",
                                        "overflow": "hidden",
                                    },
                                    children=[
                                        html.Div(
                                            style={
                                                "width": f"{player_width:.2f}%",
                                                "height": "100%",
                                                "background": "linear-gradient(90deg, rgba(0,212,255,0.72), #00d4ff)",
                                                "borderRadius": "999px",
                                                "boxShadow": "0 0 16px rgba(0,212,255,0.28)",
                                            }
                                        )
                                    ],
                                ),
                                html.Div(style={
                                    "position": "absolute",
                                    "left": f"{average_marker:.2f}%",
                                    "top": "-6px",
                                    "height": "22px",
                                    "width": "3px",
                                    "backgroundColor": "#FFFFFF",
                                    "boxShadow": "0 0 8px rgba(255,255,255,0.9)",
                                    "zIndex": "21",
                                }),
                                html.Div(style={
                                    "position": "absolute",
                                    "left": f"{top_tier_marker:.2f}%",
                                    "top": "-4px",
                                    "height": "18px",
                                    "width": "3px",
                                    "backgroundColor": "#f5b942",
                                    "boxShadow": "0 0 8px rgba(245,184,66,0.9)",
                                    "zIndex": "22",
                                }),
                            ],
                        ),
                    ]
                )
            )

        comparison_block = html.Div(
            [
                html.Div("Comparative Standing", className="career-dashboard-card__eyebrow"),
                html.P(
                    f"These comparisons show where your current {benchmark_metric.lower()} level sits against team and league reference groups.",
                    className="career-dashboard-card__body",
                ),
                legend,
                html.Div(comparison_rows_ui),
            ]
        )
    else:
        comparison_block = html.Div(
            html.P("Comparison data is not available for this view yet.", className="text-muted small")
        )

    context_scores_block: html.Div
    if context_scores:
        context_fig = go.Figure(go.Bar(
            x=[float(row.get("score") or 0.0) for row in context_scores],
            y=[str(row.get("label") or "") for row in context_scores],
            orientation="h",
            marker_color=["#00d4ff", "#7dd3fc", "#f5b942", "#f97316"],
            text=[_format_context_read_label(str(row.get("read") or "")) for row in context_scores],
            textposition="outside",
        ))
        context_fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=36, r=36, t=12, b=24),
            height=280,
            xaxis=dict(range=[0, 100]),
            showlegend=False,
        )
        context_fig = glass_figure_layout(context_fig)
        context_scores_block = html.Div(
            [
                html.Div("Decision Inputs", className="career-dashboard-card__eyebrow"),
                html.P(
                    "These support scores explain why the recommendation is cautious, balanced, or aggressive.",
                    className="career-dashboard-card__body",
                ),
                dcc.Graph(figure=context_fig, config={"displayModeBar": False}),
            ]
        )
    else:
        context_scores_block = html.Div()

    return html.Div([
        header,
        top_kpis,
        html.Div([comparison_block], className="career-outlook-card"),
        html.Div([context_scores_block], className="career-outlook-card mt-3"),
    ])


def _build_career_value_summary_evidence(data: Dict[str, Any], career_facts: Optional[Dict[str, Any]] = None) -> html.Div:
    header = html.H6([
        html.I(className="bi bi-briefcase me-2"),
        html.Span("Career Value", className="animate-glass-draw"),
    ], className="mb-3 fw-semibold", style={"color": "var(--accent-cyan, #00d4ff)"})

    evidence = ((career_facts or {}).get("evidence_facts") or {}).get("career_value_summary") or {}
    season_count = int(evidence.get("season_count") or 0)
    career_minutes = int(evidence.get("career_minutes") or data.get("minutes_played") or 0)
    career_goals = int(evidence.get("career_goals") or data.get("goals") or 0)
    career_assists = int(evidence.get("career_assists") or data.get("assists") or 0)
    consistency_level = str(evidence.get("consistency_level") or "MODERADA")

    kpis = html.Div(
        [
            html.Div([html.Div(f"{season_count}", className="career-command-kpi__value"), html.Div("seasons tracked", className="career-command-kpi__label")], className="career-command-kpi"),
            html.Div([html.Div(f"{career_minutes:,}", className="career-command-kpi__value"), html.Div("career minutes", className="career-command-kpi__label")], className="career-command-kpi"),
            html.Div([html.Div(f"{career_goals}", className="career-command-kpi__value"), html.Div("career goals", className="career-command-kpi__label")], className="career-command-kpi"),
            html.Div([html.Div(f"{career_assists}", className="career-command-kpi__value"), html.Div("career assists", className="career-command-kpi__label")], className="career-command-kpi"),
        ],
        className="career-command-kpis",
    )

    summary_copy = html.Div(
        [
            html.Div("Body of Work", className="career-dashboard-card__eyebrow"),
            html.P(
                f"This profile already carries {career_minutes:,} minutes across {season_count} tracked seasons, with {career_goals} goals and {career_assists} assists.",
                className="career-dashboard-card__body",
            ),
            html.P(
                f"Consistency is currently read as {consistency_level}.",
                className="career-dashboard-card__support",
            ),
        ],
        className="career-outlook-card",
    )

    return html.Div([header, kpis, summary_copy])


def _build_key_career_signals(brief: Any) -> html.Div:
    return html.Div(
        className="career-dashboard-section",
        children=[
            html.Div(
                [
                    html.Div(
                        [
                            html.Span(html.I(className="bi bi-broadcast-pin"), className="career-dashboard-section__icon"),
                            html.H6("Key Career Signals", className="career-dashboard-section__title"),
                        ],
                        className="career-dashboard-section__title-row",
                    ),
                    html.P("Short, evidence-backed readings of what is changing in your career.", className="career-dashboard-section__subtitle"),
                ],
                className="career-dashboard-section__header",
            ),
            html.Div(
                [_build_insight_card(item, "Signal") for item in brief.signals],
                className="career-dashboard-grid career-dashboard-grid--signals",
            ),
        ],
    )


def _build_career_levers(brief: Any) -> html.Div:
    return html.Div(
        className="career-dashboard-section",
        children=[
            html.Div(
                [
                    html.Div(
                        [
                            html.Span(html.I(className="bi bi-lightning-charge"), className="career-dashboard-section__icon"),
                            html.H6("Career Levers", className="career-dashboard-section__title"),
                        ],
                        className="career-dashboard-section__title-row",
                    ),
                    html.P("The most meaningful areas shaping your next step, backed by profile evidence.", className="career-dashboard-section__subtitle"),
                ],
                className="career-dashboard-section__header",
            ),
            html.Div(
                [_build_insight_card(item, "Leverage") for item in brief.levers],
                className="career-dashboard-grid career-dashboard-grid--levers",
            ),
        ],
    )


def _build_evidence_explanation_block(explanation_payload: Optional[Dict[str, Any]]) -> html.Div:
    """Renders the optional contextual explanation shown inside evidence modals."""
    payload = explanation_payload if isinstance(explanation_payload, dict) else {}
    headline = str(payload.get("headline") or "").strip()
    what_this_shows = str(payload.get("what_this_shows") or "").strip()
    why_it_matters = str(payload.get("why_it_matters") or "").strip()
    what_to_watch = str(payload.get("what_to_watch") or "").strip()
    confidence = str(payload.get("confidence") or "").strip().upper()
    llm_generated = bool(payload.get("llm_generated", False))
    if not all([headline, what_this_shows, why_it_matters, what_to_watch]):
        return html.Div()

    return html.Div(
        className="career-dashboard-section",
        children=[
            html.Div(
                [
                    html.Div(
                        [
                            html.Span(html.I(className="bi bi-chat-square-text"), className="career-dashboard-section__icon"),
                            html.H6("What This Means", className="career-dashboard-section__title"),
                        ],
                        className="career-dashboard-section__title-row",
                    ),
                    html.P("A deeper read of the evidence you opened, in simple language.", className="career-dashboard-section__subtitle"),
                ],
                className="career-dashboard-section__header",
            ),
            html.Div(
                className="career-outlook-card",
                children=[
                    html.Div(
                        [
                            html.Div("Evidence Read", className="career-dashboard-card__eyebrow"),
                            html.Div(
                                [
                                    html.Span(confidence or "MEDIUM"),
                                    _build_ai_origin_badge(llm_generated),
                                ],
                                className="career-dashboard-card__tone",
                            ),
                        ],
                        className="career-dashboard-card__meta",
                    ),
                    html.Div(headline, className="career-outlook-card__title"),
                    html.Div(
                        [
                            html.P("What this shows", className="career-dashboard-card__eyebrow"),
                            html.P(what_this_shows, className="career-dashboard-card__body"),
                            html.P("Why it matters", className="career-dashboard-card__eyebrow"),
                            html.P(why_it_matters, className="career-dashboard-card__body"),
                            html.P("What to watch", className="career-dashboard-card__eyebrow"),
                            html.P(what_to_watch, className="career-dashboard-card__support"),
                        ]
                    ),
                ],
            ),
        ],
    )


def _build_career_outlook(brief: Any) -> html.Div:
    outlook = brief.outlook
    llm_generated = bool(outlook.get("llm_generated", False))
    outlook_label = str(outlook.get("label", "Build") or "Build")
    resolved_evidence_key = resolve_career_surface_evidence_key(
        outlook.get("evidence_key", "career_arc"),
        label=outlook_label,
    )
    return html.Div(
        className="career-dashboard-section",
        children=[
            html.Div(
                className="career-outlook-card",
                children=[
                    html.Div(
                        [
                            html.Span(html.I(className="bi bi-compass"), className="career-dashboard-section__icon"),
                            html.Div(
                                [
                                    html.Div("Career Outlook", className="career-dashboard-card__eyebrow"),
                                    html.Div(
                                        [
                                            html.Span("Strategic Horizon"),
                                            _build_ai_origin_badge(llm_generated),
                                        ],
                                        className="career-dashboard-card__tone",
                                    ),
                                ],
                                className="career-dashboard-card__meta",
                            ),
                        ],
                        className="career-dashboard-card__top",
                    ),
                    html.Div(outlook_label, className="career-outlook-card__title"),
                    html.P(outlook.get("body", ""), className="career-dashboard-card__body"),
                    html.Div(
                        [
                            html.Span(html.I(className="bi bi-graph-up"), className="career-dashboard-card__support-icon"),
                            html.P(outlook.get("support", ""), className="career-dashboard-card__support"),
                        ],
                        className="career-dashboard-card__support-wrap",
                    ),
                    html.Div(
                        _build_career_evidence_button(
                            resolved_evidence_key,
                            trigger_index=f"outlook:{outlook_label}",
                        ),
                        className="career-dashboard-card__footer",
                    ),
                ],
            )
        ],
    )


def _build_ai_origin_badge(llm_generated: bool) -> html.Span:
    """Renders a subtle origin badge when content comes from the shared LLM layer."""
    if not llm_generated:
        return html.Span()
    return html.Span(
        [
            html.I(className="bi bi-stars"),
            html.Span("AI"),
        ],
        className="career-ai-origin-badge",
        title="This copy was synthesized by the shared AI layer and validated before render.",
    )


def render_career_evidence_view(
    evidence_key: str,
    player_name: str,
    player_id: str,
    focus_metric: str = "",
) -> Dict[str, Any]:
    """Returns modal metadata + content for a career evidence destination."""
    from utils.domain_ai import build_evidence_explanation

    evidence_bundle = _prepare_career_evidence_bundle(player_name, player_id)
    data = evidence_bundle.get("data") or {}
    career_phase_data = evidence_bundle.get("career_phase_data") or {}
    career_signals = evidence_bundle.get("career_signals") or {}
    career_facts = evidence_bundle.get("career_facts") or {}
    resolved_key = resolve_career_surface_evidence_key(evidence_key)
    meta = get_evidence_destination_meta(resolved_key)
    key = meta["key"]

    if key == "minutes_trend":
        content = _build_minutes_trend_evidence(data)
    elif key == "recent_form":
        content = _build_recent_form_evidence(data)
    elif key == "career_trend":
        content = _build_career_trend_evidence(data, career_facts)
    elif key == "career_phase_resolution":
        content = _build_career_phase_resolution_evidence(data, career_phase_data or {}, career_signals, career_facts)
    elif key == "team_positional_rank":
        content = _build_comparative_dimension_evidence("Team Positional Rank", (career_facts.get("evidence_facts") or {}).get("team_positional_rank") or {}, icon_class="bi bi-person-badge")
    elif key == "team_global_rank":
        content = _build_comparative_dimension_evidence("Team Overall Rank", (career_facts.get("evidence_facts") or {}).get("team_global_rank") or {}, icon_class="bi bi-people")
    elif key == "league_positional_standing":
        content = _build_comparative_dimension_evidence("League Positional Standing", (career_facts.get("evidence_facts") or {}).get("league_positional_standing") or {}, icon_class="bi bi-trophy")
    elif key == "league_global_standing":
        content = _build_comparative_dimension_evidence("League Overall Standing", (career_facts.get("evidence_facts") or {}).get("league_global_standing") or {}, icon_class="bi bi-diagram-3")
    elif key == "top_tier_gap":
        content = _build_score_shell_evidence("Top-Tier Gap", (career_facts.get("evidence_facts") or {}).get("top_tier_gap") or {}, "top_tier_gap_score", "headline_fact")
    elif key == "consistency_profile":
        content = _build_score_shell_evidence("Consistency Profile", (career_facts.get("evidence_facts") or {}).get("consistency_profile") or {}, "consistency_score", "consistency_label")
    elif key == "team_context":
        content = _build_team_context_evidence((career_facts.get("evidence_facts") or {}).get("team_context") or {})
    elif key == "career_timing_context":
        content = _build_score_shell_evidence("Career Timing Context", (career_facts.get("evidence_facts") or {}).get("career_timing_context") or {}, "career_timing_score", "career_timing_label")
    elif key == "career_value_summary":
        content = _build_career_value_summary_evidence(data, career_facts)
    elif key == "career_arc":
        content = _build_career_arc(data)
    elif key == "percentile_profile":
        content = _build_league_standing(data, focus_metric=focus_metric)
    elif key == "similarity_profiles":
        content = _build_similar_players(data)
    elif key == "projection_outlook":
        content = _build_projection_section(data, player_id)
    elif key == "tactical_dna":
        content = html.Div(
            [
                _build_cluster_dna(data),
                html.Hr(style={"borderColor": HKFATheme.BORDER_COLOR, "margin": "16px 0"}),
                _build_similar_players(data),
            ]
        )
    else:
        content = html.Div(
            html.P("Detailed evidence is not available for this insight yet.", className="text-muted small mb-0")
        )

    explanation_payload: Optional[Dict[str, Any]] = None
    try:
        explanation = build_evidence_explanation(
            player_id=player_id,
            player_name=player_name,
            evidence_key=key,
            career_facts=career_facts,
        )
        if explanation is not None:
            explanation_payload = {
                "headline": explanation.headline,
                "what_this_shows": explanation.what_this_shows,
                "why_it_matters": explanation.why_it_matters,
                "what_to_watch": explanation.what_to_watch,
                "confidence": explanation.confidence,
                "llm_generated": bool(getattr(explanation, "llm_generated", False)),
            }
    except Exception as exc:
        logger.debug("career evidence explanation error: %s", exc)

    wrapped_content = html.Div(
        [
            content,
            _build_evidence_explanation_block(explanation_payload),
        ]
    )

    return {
        "key": key,
        "title": meta["title"],
        "content": wrapped_content,
    }


def render_player_dashboard(
    player_name: str,
    player_id: str,
    user_role: str = "player",
    ai_payload: Optional[Dict[str, Any]] = None,
    synthesize_with_ai: bool = True,
) -> html.Div:
    """
    Orchestrates the 6-section player dashboard for Estado A (no card open).
    Fetches data once and delegates to independent builders with per-section error isolation.
    """
    from utils.career_intelligence import (
        get_career_phase_data,
        get_career_signals,
        get_development_priorities,
        build_career_dashboard_brief,
    )
    from utils.domain_ai.career_dashboard_ai import normalize_career_dashboard_brief_payload

    data = _fetch_dashboard_data(player_name, player_id)
    normalized_ai_payload = normalize_career_dashboard_brief_payload(ai_payload)

    # Compute career phase inline (pure function, no I/O)
    career_phase_data: Optional[Dict] = None
    try:
        career_phase_data = get_career_phase_data(data, data.get("history_df", pd.DataFrame()))
    except Exception as _cpe:
        logger.debug(f"career_phase_data computation failed: {_cpe}")

    # Compute career signals and development priorities for Strategic Intelligence block
    career_signals: Dict = {}
    development_priorities: List = []
    try:
        career_signals = get_career_signals(data, data.get("history_df", pd.DataFrame()), career_phase_data or {})
    except Exception as _cse:
        logger.debug(f"career_signals computation failed: {_cse}")
    try:
        development_priorities = get_development_priorities(data.get("percentiles_data") or {})
    except Exception as _dpe:
        logger.debug(f"development_priorities computation failed: {_dpe}")

    dashboard_brief = build_career_dashboard_brief(
        data,
        career_phase_data or {},
        career_signals,
        development_priorities,
        ai_payload=normalized_ai_payload,
        synthesize_with_ai=synthesize_with_ai,
    )

    def _safe_build(builder_fn, *args, **kwargs) -> html.Div:
        try:
            return builder_fn(*args, **kwargs)
        except Exception as e:
            logger.warning(f"Dashboard section '{builder_fn.__name__}' failed: {e}")
            return html.P("Sección no disponible", className="text-muted small")

    sections = [
        _safe_build(_build_career_command, data, career_phase_data or {}, dashboard_brief),
        _safe_build(_build_key_career_signals, dashboard_brief),
        _safe_build(_build_career_levers, dashboard_brief),
        _safe_build(_build_career_outlook, dashboard_brief),
    ]

    return html.Div(
        html.Div(sections, className="stage-view stage-view--dashboard stage-view--career-command pb-2"),
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
    competition_display = get_competition_display_name(competition, long_form=True)
    competition_logo = payload.get("competition_logo") or get_competition_logo(competition)
    home_logo = (
        payload.get("home_logo")
        or payload.get("home_logo_url")
        or _resolve_team_logo(home)
    )
    away_logo = (
        payload.get("away_logo")
        or payload.get("away_logo_url")
        or _resolve_team_logo(away)
    )
    has_var = bool(payload.get("has_var"))
    is_tv = bool(payload.get("is_tv"))
    broadcast_type = str(payload.get("broadcast_type") or "").strip()
    role_label = POSITION_FULL_NAMES.get(str(player_current_role or player_position_main).upper(), player_current_role or player_position_main)
    opponent_team = opponent if opponent else (away if home else home)
    player_id = _get_logged_in_player_id()
    recent_form = _get_recent_form_summary(player_id)
    h2h_summary = _get_head_to_head_summary(player_id, opponent_team)
    if h2h_summary:
        h2h_summary = sorted(
            h2h_summary,
            key=lambda item: pd.to_datetime(item.get("date")) if item.get("date") is not None else pd.Timestamp.min,
        )
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
        clean_variant: bool = True,
    ) -> dbc.Card:
        base_style = {
            "position": "relative",
        }
        if extra_style:
            base_style.update(extra_style)
        class_name = "border-0 prematch-float-card"
        if clean_variant:
            class_name = f"{class_name} prematch-clean-card"
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

    def _lucide(name: str) -> html.I:
        return html.I(**{"data-lucide": name, "className": "lucide-inline-icon me-1"})

    def _card_icon(color: str, size: str = "18px", class_name: str = "") -> html.I:
        return html.I(
            **{"data-lucide": "rectangle-vertical"},
            className=class_name,
            style={"width": size, "height": size, "color": color, "opacity": "0.95", "lineHeight": "1"},
        )

    def _team_block(name: str, logo: str, align: str, jersey: str = "") -> html.Div:
        justify = "flex-start" if align == "left" else "flex-end"
        crest_block = html.Div([
            html.Img(src=logo, style={"width": "96px", "height": "96px", "objectFit": "contain"}) if logo else html.Div(
                name[:2].upper(),
                style={
                    "width": "96px", "height": "96px", "borderRadius": "50%",
                    "display": "flex", "alignItems": "center", "justifyContent": "center",
                    "background": "rgba(255,255,255,0.08)", "color": "#f3f7fb", "fontWeight": "800",
                },
            ),
            html.Div(name or "TBC", style={"color": "#f4f8fc", "fontWeight": "700", "fontSize": "1.08rem", "textAlign": "center", "letterSpacing": "0.01em", "marginTop": "10px", "width": "96px"}),
        ], style={"display": "flex", "flexDirection": "column", "alignItems": "center", "justifyContent": "center"})
        return html.Div([
            html.Div([
                html.Img(src=jersey, style={"width": "90px", "height": "90px", "objectFit": "contain", "opacity": "0.98"}) if jersey and align == "right" else None,
                crest_block,
                html.Img(src=jersey, style={"width": "90px", "height": "90px", "objectFit": "contain", "opacity": "0.98"}) if jersey and align == "left" else None,
            ], style={"display": "flex", "justifyContent": justify, "alignItems": "flex-start", "gap": "16px"}),
        ], style={"flex": "0 1 240px", "minWidth": "210px", "maxWidth": "250px", "textAlign": "center", "display": "flex", "flexDirection": "column", "alignItems": "center"})

    stream_href = streaming_url if streaming_url and "facebook.com" not in streaming_url.lower() else ""
    broadcast_chips: List[Any] = []
    home_jersey = _resolve_team_jersey(home, "home")
    away_jersey = _resolve_team_jersey(away, "home")
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
                html.Img(src=competition_logo, style={"width": "54px", "height": "54px", "objectFit": "contain", "marginBottom": "8px"}) if competition_logo else None,
                html.Div(competition_display, style={"color": "#f6f8fb", "fontWeight": "700", "fontSize": "1.05rem"}),
            ], style={"display": "flex", "flexDirection": "column", "alignItems": "center", "marginBottom": "24px"}),
            html.Div([
                _team_block(home, home_logo, "right", home_jersey),
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
                _team_block(away, away_logo, "left", away_jersey),
            ], style={"display": "flex", "alignItems": "center", "justifyContent": "center", "gap": "28px", "flexWrap": "wrap"}),
            html.Hr(style={"borderColor": "rgba(255,255,255,0.14)", "margin": "20px 0 18px"}),
            html.Div([
                _chip("bi-geo-alt", stadium or "Stadium TBC", HKFATheme.ACCENT_BLUE),
                html.Div(broadcast_chips, style={"display": "flex", "gap": "10px", "flexWrap": "wrap", "justifyContent": "flex-end"}),
            ], style={"display": "flex", "justifyContent": "space-between", "alignItems": "center", "gap": "12px", "flexWrap": "wrap"}),
        ]),
        accent=HKFATheme.ACCENT_GOLD,
        extra_class="prematch-fixture-card",
        extra_style={},
        clean_variant=False,
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

    def _stat_card(label: str, value: str, accent: str, subtext: str = "", icon: Any = "bi-dot") -> dbc.Card:
        icon_node = (
            html.I(className=f"bi {icon} me-2", style={"color": accent})
            if isinstance(icon, str)
            else icon
        )
        return _glass_card(
            dbc.CardBody([
                html.Div([
                    icon_node,
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
                html.Div(_stat_card("Goals", f"{int(recent_form.get('goals_total', 0) or 0)}", HKFATheme.ACCENT_RED, f"{recent_form.get('goals_per90', 0):.2f} per 90" if minutes_total else "", html.Img(src="/assets/icons/soccer-ball.svg", style={"width": "20px", "height": "20px", "objectFit": "contain", "marginRight": "8px"})), style={"flex": "1 1 150px"}),
                html.Div(_stat_card("Assists", f"{int(recent_form.get('assists_total', 0) or 0)}", HKFATheme.ACCENT_BLUE, f"{recent_form.get('assists_per90', 0):.2f} per 90" if minutes_total else "", html.I(**{"data-lucide": "sport-shoe", "className": "lucide-inline-icon rival-assist-icon me-2", "style": {"color": HKFATheme.ACCENT_BLUE, "width": "20px", "height": "20px"}})), style={"flex": "1 1 150px"}),
                html.Div(_stat_card("xG", f"{recent_form.get('xg_total', 0):.2f}", "#4ed0a6", f"{recent_form.get('xg_per90', 0):.2f} per 90" if minutes_total else "", "bi-graph-up-arrow"), style={"flex": "1 1 150px"}),
                html.Div(_stat_card("xA", f"{recent_form.get('xa_total', 0):.2f}", "#a28dff", f"{recent_form.get('xa_per90', 0):.2f} per 90" if minutes_total else "", "bi-bezier2"), style={"flex": "1 1 150px"}),
                html.Div(_stat_card("Rating", "—", HKFATheme.ACCENT_GOLD, "", "bi-star"), style={"flex": "1 1 150px"}),
            ], style={"display": "flex", "gap": "12px", "flexWrap": "wrap", "marginTop": "40px"}),
            style={"marginBottom": "36px"},
        ),
    ], className="mb-4", style={"marginBottom": "54px"})

    rival_cards: List[Any] = []
    for rival_idx, rival in enumerate(rivals):
        accent = HKFATheme.ACCENT_RED if rival.get("matchup_tier") == "Primary Matchup" else HKFATheme.ACCENT_BLUE
        recent_data_available = bool(rival.get("recent_data_available"))
        form_badge_id = f"rival-form-badge-{rival_idx}"
        def _recent_value(key: str) -> str:
            if not recent_data_available:
                return "—"
            return str(rival.get(key, 0))
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
                            "background": "rgba(84,210,154,0.12)" if rival.get("form_label") == "In Form" else ("rgba(239,107,107,0.12)" if rival.get("form_label") == "Out of Form" else "rgba(244,195,81,0.12)"),
                            "border": "1px solid rgba(255,255,255,0.10)",
                            "color": "#eaf2f8",
                            "fontSize": "0.74rem",
                            "fontWeight": "600",
                            "cursor": "help",
                        }, id=form_badge_id),
                        dbc.Tooltip(
                            rival.get("form_reason", "") or "No recent match history available yet.",
                            target=form_badge_id,
                            placement="top",
                        ),
                    ], style={"display": "flex", "gap": "8px", "flexWrap": "wrap", "marginBottom": "12px"}),
                    html.Div([
                        html.Div("Last 5", style={
                            "color": "#aebbc8",
                            "fontSize": "0.68rem",
                            "letterSpacing": "0.08em",
                            "textTransform": "uppercase",
                            "marginBottom": "8px",
                            "paddingLeft": "4px",
                        }),
                    ]),
                    html.Div([
                        # Minutos
                        html.Span([
                            html.I(className="bi bi-stopwatch", style={"fontSize": "1.3rem", "opacity": "0.85"}),
                            html.Span(_recent_value("recent_minutes")),
                        ], style={"display": "inline-flex", "alignItems": "center", "gap": "8px"}),

                        # Goles
                        html.Span([
                            html.Img(
                                src="/assets/icons/soccer-ball.svg",
                                style={"width": "22px", "height": "22px", "opacity": "0.9"}
                            ),
                            html.Span(_recent_value("recent_goals")),
                        ], style={"display": "inline-flex", "alignItems": "center", "gap": "8px"}),

                        # Asistencias
                        html.Span([
                            html.I(
                                **{"data-lucide": "sport-shoe"},
                                style={"width": "22px", "height": "22px", "opacity": "0.9"}
                            ),
                            html.Span(_recent_value("recent_assists")),
                        ], style={"display": "inline-flex", "alignItems": "center", "gap": "8px"}),

                        # Amarillas
                        html.Span([
                            _card_icon("#f4c351", size="20px"),
                            html.Span(_recent_value("recent_yellow_cards")),
                        ], style={"display": "inline-flex", "alignItems": "center", "gap": "8px"}),

                        # Rojas
                        html.Span([
                            _card_icon("#ef6b6b", size="20px"),
                            html.Span(_recent_value("recent_red_cards")),
                        ], style={"display": "inline-flex", "alignItems": "center", "gap": "8px"}),
                    ], style={
                        "display": "flex",
                        "justifyContent": "space-between",
                        "alignItems": "center",
                        "color": "#c7d0dc",
                        "fontSize": "0.9rem",
                        "fontWeight": "600",
                        "marginBottom": "20px",
                        "padding": "0 4px"
                    }),
                    html.Div([
                        html.Div("Strength", style={"color": "#97e3b0", "fontSize": "0.72rem", "textTransform": "uppercase", "letterSpacing": "0.08em", "fontWeight": "700"}),
                        html.Div(rival.get("strength_text", ""), style={"color": "#eff4fa", "fontWeight": "400", "marginTop": "4px", "fontSize": "0.9rem"}),
                    ], className="mb-3"),
                    html.Div([
                        html.Div("Weakness", style={"color": "#ffb3b3", "fontSize": "0.72rem", "textTransform": "uppercase", "letterSpacing": "0.08em", "fontWeight": "700"}),
                        html.Div(rival.get("weakness_text", ""), style={"color": "#eff4fa", "fontWeight": "400", "marginTop": "4px", "fontSize": "0.9rem"}),
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
                        html.Div("Physical", style={"color": HKFATheme.ACCENT_BLUE, "fontSize": "0.72rem", "textTransform": "uppercase", "letterSpacing": "0.08em", "fontWeight": "700"}),
                        html.Div(rival.get("physical_text") or f"{rival.get('physical_val', 0):.1f} {rival.get('physical_label', '')}", style={"color": "#eff4fa", "fontWeight": "400", "fontSize": "0.86rem", "marginTop": "4px"}),
                    ]) if rival.get("physical_label") else None,
                ]),
                accent=accent,
                extra_style={"height": "100%"},
            ), className="prematch-rival-card")
        )

    rivals_section = html.Div([
        html.Div(
            _section_title("bi-shield-exclamation", "Rivals to Watch", f"Likely direct matchups from {opponent_team}" if opponent_team else ""),
            style={"marginBottom": "36px"},
        ),
        html.Div(rival_cards, className="prematch-rivals-grid") if rival_cards else html.Div(
            "No direct rival profiles available yet.",
            style={"color": "#c5d1dd", "fontSize": "0.92rem"},
        ),
    ], className="mb-4", style={"marginBottom": "54px"})

    h2h_items = []
    timeline_events: List[Dict[str, Any]] = [dict(item, _is_future=False) for item in h2h_summary]
    next_h2h_dt = None
    try:
        next_h2h_dt = _coerce_cutoff_datetime(payload)
    except Exception:
        next_h2h_dt = None
    if opponent_team and next_h2h_dt is not None:
        timeline_events.append({
            "_is_now": True,
            "_is_future": False,
            "date": next_h2h_dt,
            "outcome": "NOW",
            "score": "",
            "competition": "",
            "competition_logo": "",
            "goals": 0,
            "assists": 0,
            "minutes": 0,
            "yellow_cards": 0,
            "red_cards": 0,
            "substitution": "",
            "penalties": False,
        })
        timeline_events.append({
            "_is_future": True,
            "date": next_h2h_dt,
            "outcome": "NEXT",
            "score": "",
            "competition": competition,
            "competition_logo": competition_logo,
            "stadium": stadium,
            "goals": 0,
            "assists": 0,
            "minutes": 0,
            "yellow_cards": 0,
            "red_cards": 0,
            "substitution": "",
            "penalties": False,
        })
    total_h2h_goals = sum(int(item.get("goals", 0) or 0) for item in h2h_summary)
    total_h2h_assists = sum(int(item.get("assists", 0) or 0) for item in h2h_summary)
    record_w = sum(1 for item in h2h_summary if item.get("outcome") == "W")
    record_d = sum(1 for item in h2h_summary if item.get("outcome") == "D")
    record_l = sum(1 for item in h2h_summary if item.get("outcome") == "L")
    for idx, match in enumerate(timeline_events):
        is_now = bool(match.get("_is_now"))
        is_future = bool(match.get("_is_future"))
        accent = {"W": "#76d289", "D": "#f4c351", "L": "#ef6b6b", "NEXT": "#79c8ff", "NOW": "#f4c351"}.get(match.get("outcome"), "#a1adbb")
        orientation = "top" if idx % 2 == 0 else "bottom"
        if is_future:
            orientation = "top"
        date_value = match.get("date")
        date_label = "Date TBC"
        day_number = ""
        date_meta = ""
        time_meta = ""
        try:
            if date_value is not None:
                ts = pd.to_datetime(date_value)
                day_number = ts.strftime("%d")
                date_meta = ts.strftime("%b %Y")
                date_label = ts.strftime("%d %b %Y")
                if is_future:
                    ts_py = ts.to_pydatetime()
                    if ts_py.tzinfo is None:
                        ts_py = ts_py.replace(tzinfo=timezone.utc)
                    ts_hkt = ts_py.astimezone(timezone(timedelta(hours=8)))
                    time_meta = ts_hkt.strftime("%H:%M")
                else:
                    time_meta = ts.strftime("%H:%M")
        except Exception:
            pass
        competition_name = str(match.get("competition") or "Competition")
        competition_name = re.sub(r"^Hong Kong\s+", "", competition_name, flags=re.IGNORECASE).strip()
        competition_name = re.sub(r"\s+Hong Kong\s+", " ", competition_name, flags=re.IGNORECASE).strip()
        competition_name = re.sub(r"^HK\s+", "", competition_name, flags=re.IGNORECASE).strip()
        competition_name = re.sub(r"\s+HK\s+", " ", competition_name, flags=re.IGNORECASE).strip()
        competition_name = re.sub(r"\s*\([^)]*\)\s*$", "", competition_name).strip()
        competition_name = re.split(r"\s*[\(\[\-]\s*", competition_name, maxsplit=1)[0].strip()
        competition_logo = str(match.get("competition_logo") or "")
        historical_label = str(match.get("opponent_label") or "")
        home_team_name = ""
        away_team_name = ""
        if is_future:
            home_team_name = str(home or "")
            away_team_name = str(away or "")
        elif " vs " in historical_label:
            parts = historical_label.split(" vs ", 1)
            home_team_name = re.sub(r"\s*\([^)]*\)\s*$", "", parts[0]).strip()
            away_team_name = re.sub(r"\s*\([^)]*\)\s*$", "", parts[1]).strip()
        home_team_logo = _resolve_team_logo(home_team_name) if home_team_name else ""
        away_team_logo = _resolve_team_logo(away_team_name) if away_team_name else ""
        detail_grid = None
        if is_future:
            detail_items = []
            if match.get("stadium"):
                detail_items.append(
                    html.Div([
                        html.I(className="bi bi-geo-alt"),
                        html.Span(str(match.get("stadium")), className="prematch-h2h-icon-value"),
                    ], className="prematch-h2h-detail-item")
                )
            if detail_items:
                detail_grid = html.Div(detail_items, className="prematch-h2h-details prematch-h2h-details--future")
        else:
            detail_items = [
                html.Div([
                    html.I(className="bi bi-stopwatch"),
                    html.Span(str(int(match.get("minutes", 0) or 0)), className="prematch-h2h-icon-value"),
                ], className="prematch-h2h-detail-item"),
                html.Div([
                    html.Img(src="/assets/icons/soccer-ball.svg", className="prematch-h2h-ball-icon"),
                    html.Span(str(int(match.get("goals", 0) or 0)), className="prematch-h2h-icon-value"),
                ], className="prematch-h2h-detail-item"),
                html.Div([
                    html.I(**{"data-lucide": "sport-shoe", "className": "lucide-inline-icon rival-assist-icon"}),
                    html.Span(str(int(match.get("assists", 0) or 0)), className="prematch-h2h-icon-value"),
                ], className="prematch-h2h-detail-item"),
                html.Div([
                    _card_icon("#f3c84d", size="14px"),
                    html.Span(str(int(match.get("yellow_cards", 0) or 0)), className="prematch-h2h-icon-value"),
                ], className="prematch-h2h-detail-item"),
                html.Div([
                    _card_icon("#ef6b6b", size="14px"),
                    html.Span(str(int(match.get("red_cards", 0) or 0)), className="prematch-h2h-icon-value"),
                ], className="prematch-h2h-detail-item"),
                html.Div([
                    html.I(className="bi bi-arrow-left-right"),
                    html.Span(str(match.get("substitution") or "Full"), className="prematch-h2h-icon-value"),
                ], className="prematch-h2h-detail-item"),
            ]
            if match.get("stadium"):
                detail_items.append(
                    html.Div([
                        html.I(className="bi bi-geo-alt"),
                        html.Span(str(match.get("stadium")), className="prematch-h2h-icon-value"),
                    ], className="prematch-h2h-detail-item")
                )
            detail_grid = html.Div(detail_items, className="prematch-h2h-details")
        if is_now:
            h2h_items.append(
                html.Div([
                    html.Div(className="prematch-h2h-node prematch-h2h-node--now"),
                    html.Div("NOW", className="prematch-h2h-now-label"),
                ], className="prematch-h2h-item prematch-h2h-item--now", id=f"prematch-h2h-item-{idx}")
            )
            continue
        h2h_items.append(
            html.Div([
                html.Div(className="prematch-h2h-node"),
                html.Div(time_meta, className="prematch-h2h-time") if is_future and time_meta else None,
                html.Div([
                    html.Img(src=competition_logo, className="prematch-h2h-card-comp-logo") if competition_logo else None,
                    html.Div([
                        html.Div(day_number or "—", className="prematch-h2h-day"),
                        html.Div([
                            html.Div(date_meta or date_label, className="prematch-h2h-date-meta"),
                            html.Div([
                                html.Span(competition_name, className="prematch-h2h-comp"),
                            ], className="prematch-h2h-comp-row"),
                        ], className="prematch-h2h-head-main"),
                    ], className="prematch-h2h-head"),
                    html.Div([
                        html.Span(match.get("outcome", "—"), className="prematch-h2h-outcome", style={"color": accent}),
                        html.Div([
                            html.Img(src=home_team_logo, className="prematch-h2h-team-logo") if home_team_logo else html.Span(className="prematch-h2h-team-logo prematch-h2h-team-logo--placeholder"),
                            html.Span(
                                "VS" if is_future else f"{match.get('score', '—')}{' (p)' if match.get('penalties') else ''}",
                                className="prematch-h2h-score",
                            ),
                            html.Img(src=away_team_logo, className="prematch-h2h-team-logo") if away_team_logo else html.Span(className="prematch-h2h-team-logo prematch-h2h-team-logo--placeholder"),
                        ], className="prematch-h2h-score-group"),
                    ], className="prematch-h2h-result-row"),
                    detail_grid,
                ], className="prematch-h2h-card"),
            ], className=f"prematch-h2h-item prematch-h2h-item--{orientation}{' prematch-h2h-item--future' if is_future else ''}", id=f"prematch-h2h-item-{idx}")
        )

    h2h_section = html.Div([
        html.Div(
            _section_title("bi-clock-history", "Your record vs this opponent", f"All meetings on record against {opponent_team}" if opponent_team else ""),
            style={"marginBottom": "36px"},
        ),
        html.Div([
            html.Div([
                html.Div("Record", className="prematch-h2h-summary-label"),
                html.Div([
                    html.I(className="bi bi-bar-chart-line", style={"color": "#b58cff"}),
                    html.Span(f"{record_w}-{record_d}-{record_l}"),
                ], className="prematch-h2h-summary-value"),
            ], className="prematch-h2h-summary-item"),
            html.Div([
                html.Div("Goals", className="prematch-h2h-summary-label"),
                html.Div([
                    html.Img(src="/assets/icons/soccer-ball.svg", className="prematch-h2h-summary-ball"),
                    html.Span(str(total_h2h_goals)),
                ], className="prematch-h2h-summary-value"),
            ], className="prematch-h2h-summary-item"),
            html.Div([
                html.Div("Assists", className="prematch-h2h-summary-label"),
                html.Div([
                    html.I(**{"data-lucide": "sport-shoe", "className": "lucide-inline-icon rival-assist-icon", "style": {"color": HKFATheme.ACCENT_BLUE}}),
                    html.Span(str(total_h2h_assists)),
                ], className="prematch-h2h-summary-value"),
            ], className="prematch-h2h-summary-item"),
            html.Div([
                html.Div("Meetings", className="prematch-h2h-summary-label"),
                html.Div([
                    html.I(className="bi bi-clock-history", style={"color": HKFATheme.ACCENT_GOLD}),
                    html.Span(str(len(h2h_summary))),
                ], className="prematch-h2h-summary-value"),
            ], className="prematch-h2h-summary-item"),
        ], className="prematch-h2h-summary") if h2h_summary else None,
        html.Div([
            html.Div(className="prematch-h2h-track"),
            html.Button([
                html.Span("Today", className="prematch-h2h-hint-label"),
                html.I(className="bi bi-arrow-right prematch-h2h-hint-arrow"),
            ], id="prematch-h2h-today-btn", className="prematch-h2h-hint", n_clicks=0),
            html.Div(h2h_items, className="prematch-h2h-scroll"),
        ], className="prematch-h2h-timeline") if h2h_items else html.Div(
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

    data_signals = sum(
        1 for flag in [
            bool(top_scorer_name),
            bool(rivals),
            bool(h2h_summary),
            bool(recent_form.get("minutes_total", 0)),
        ] if flag
    )
    confidence_label = {
        4: "High confidence",
        3: "Good confidence",
        2: "Moderate confidence",
    }.get(data_signals, "Limited confidence")
    confidence_color = {
        4: "#76d289",
        3: HKFATheme.ACCENT_BLUE,
        2: HKFATheme.ACCENT_GOLD,
    }.get(data_signals, "#b7c2d1")

    main_rival = rivals[0] if rivals else {}
    rival_name = main_rival.get("name", "their direct defender")
    rival_role = main_rival.get("role_label", main_rival.get("position_group", ""))
    rival_strength = str(main_rival.get("strength_text", "") or "").strip()
    rival_weakness = str(main_rival.get("weakness_text", "") or "").strip()

    assist_bias = int(recent_form.get("assists_total", 0) or 0) > int(recent_form.get("goals_total", 0) or 0)
    if rival_weakness:
        plan_headline = f"Target {rival_name} early and force the duel into the phase where they {rival_weakness.lower()}."
    elif top_scorer_name:
        plan_headline = f"Control the first action around {top_scorer_name} and attack quickly once their front line is broken."
    else:
        plan_headline = f"Play with fast first actions against {opponent_team} and attack the open space after the regain."

    plan_rows = []
    if top_scorer_name:
        plan_rows.append((
            "bi-crosshair",
            "#ef6b6b",
            "Main threat",
            f"{top_scorer_name} is their top scorer with {top_scorer_goals} goals. Be ready for the first movement around the box."
        ))
    if rival_name:
        duel_text = (
            f"Likely matchup: {rival_name}"
            + (f" ({rival_role})" if rival_role else "")
            + (
                f". Strong because {rival_strength.lower()}, but exploitable because they {rival_weakness.lower()}."
                if rival_strength and rival_weakness
                else ""
            )
        )
        plan_rows.append((
            "bi-person-bounding-box",
            HKFATheme.ACCENT_BLUE,
            "Primary duel",
            duel_text,
        ))
    progression_text = (
        "Lean into release passes and quick combinations to attack the space behind their first line."
        if assist_bias else
        "Attack the box aggressively once the move reaches the final third, especially after quick wide combinations."
    )
    plan_rows.append((
        "bi-diagram-3",
        "#a28dff",
        "Progression",
        progression_text,
    ))
    if h2h_summary:
        recent_h2h_outcome = h2h_summary[-1].get("outcome", "")
        h2h_text = (
            f"You have {record_w}W-{record_d}D-{record_l}L on record against {opponent_team}. "
            f"Use that context, but treat the next duel as a new game-state."
        )
        if recent_h2h_outcome in {"W", "L", "D"}:
            h2h_text = (
                f"All-time H2H stands at {record_w}W-{record_d}D-{record_l}L. "
                f"The last meeting ended {recent_h2h_outcome}, so be ready for a different opening pattern this time."
            )
        plan_rows.append((
            "bi-clock-history",
            HKFATheme.ACCENT_GOLD,
            "Context",
            h2h_text,
        ))

    game_plan_card = _glass_card(
        dbc.CardBody([
            html.Div([
                _section_title("bi-robot", "AI Game-Plan", "Structured from recent form, rival profiles and head-to-head data."),
                html.Span(
                    confidence_label,
                    style={
                        "padding": "6px 10px",
                        "borderRadius": "999px",
                        "background": f"rgba({_hex_to_rgb(confidence_color)}, 0.12)",
                        "border": f"1px solid rgba({_hex_to_rgb(confidence_color)}, 0.24)",
                        "color": "#eef4fa",
                        "fontSize": "0.72rem",
                        "fontWeight": "600",
                        "whiteSpace": "nowrap",
                    },
                ),
            ], style={"display": "flex", "justifyContent": "space-between", "alignItems": "flex-start", "gap": "12px", "marginBottom": "20px", "flexWrap": "wrap"}),
            html.Div(
                plan_headline,
                style={
                    "color": "#f4f8fc",
                    "fontSize": "1.02rem",
                    "fontWeight": "700",
                    "lineHeight": "1.55",
                    "marginBottom": "18px",
                },
            ),
            html.Div([
                html.Div([
                    html.Div([
                        html.I(className=f"bi {icon}", style={"color": accent, "fontSize": "1rem", "lineHeight": "1"}),
                        html.Span(label, style={"color": "#f0f5fa", "fontWeight": "700", "fontSize": "0.84rem", "letterSpacing": "0.02em"}),
                    ], style={"display": "flex", "alignItems": "center", "gap": "8px", "marginBottom": "6px"}),
                    html.Div(text, style={"color": "#d8e1eb", "fontSize": "0.9rem", "lineHeight": "1.6"}),
                ], style={
                    "padding": "12px 14px",
                    "borderRadius": "14px",
                    "background": "rgba(255,255,255,0.04)",
                    "border": "1px solid rgba(255,255,255,0.08)",
                }) for icon, accent, label, text in plan_rows
            ], style={"display": "grid", "gridTemplateColumns": "repeat(auto-fit, minmax(220px, 1fr))", "gap": "12px"}),
        ]),
        accent=HKFATheme.ACCENT_GOLD,
    )

    return html.Div([
        html.Div(fixture_card, style={"marginBottom": "36px"}),
        html.Div(recent_form_section, style={"marginBottom": "36px"}),
        html.Div(rivals_section, style={"marginBottom": "36px"}),
        html.Div(h2h_section, style={"marginBottom": "36px"}),
        game_plan_card,
    ], className="stage-view stage-view--prematch")


def render_career_insights(payload: Dict[str, Any], user_role: str = "player") -> html.Div:
    """
    Renders the Career Insights stage with contextual projection, UMAP clustering,
    archetype badge, season-over-season delta KPIs, AI insight line,
    and a role-conditional Dossier export button.

    When payload contains source="overlay", the signal widget matching the
    triggering signal type is highlighted with a cyan left-border accent.
    """
    season = payload.get("season", "")
    player_id = payload.get("player_id", "")
    player_name = payload.get("player_name", "Player")
    overlay_source = payload.get("source", "")
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
                _build_delta_kpis(current_row, prev_row, kpi_metrics, history_df),
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
        dcc.Graph(
            figure=projection_fig,
            config={"displayModeBar": False, "responsive": True},
            className="w-100",
            responsive=True,
            style={"width": "100%", "minWidth": "0"},
        ),
        className="mb-3",
    )

    # ── UMAP clustering figure ─────────────────────────────────────────────
    umap_fig = get_umap_figure(player_id)
    umap_section = html.Div(
        dcc.Graph(
            figure=umap_fig,
            config={"displayModeBar": False, "responsive": True},
            className="w-100",
            responsive=True,
            style={"width": "100%", "minWidth": "0"},
        ),
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

    # Apply overlay-source highlight: cyan left-border on the insight widget
    insight_highlight_style = {}
    if overlay_source == "overlay":
        insight_highlight_style = {
            "borderLeft": "3px solid #00D4FF",
            "paddingLeft": "10px",
            "borderRadius": "0 8px 8px 0",
        }

    return html.Div([
            html.H6([
                html.I(className="bi bi-calendar3 me-2"),
                html.Span(
                    f"Career Perspective — Season {season}",
                    className="animate-glass-draw",
                ),
            ], className="mb-3 fw-semibold", style={"color": "var(--accent-cyan, #00d4ff)"}),
            archetype_section,
            html.Div(insight_section, style=insight_highlight_style) if insight_section else None,
            delta_section,
            dbc.Row([
                dbc.Col(projection_section, width=12, lg=6),
                dbc.Col(umap_section, width=12, lg=6),
            ]),
            dossier_button,
        ], className="stage-view stage-view--career pb-2")

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
            registry = ModelRegistry()
            km_u = registry.load("kmeans_overall_k5")
            if km_u is not None:
                # LOAD metadata to sync features
                reg_data = registry._load_registry()
                expected_features = reg_data.get("kmeans_overall_k5", {}).get("latest", {}).get("features")
                
                if expected_features:
                    available_cols = [c for c in expected_features if c in df_plot.columns]
                    X_u_df = df_plot[available_cols].fillna(0).copy()
                    for mc in expected_features:
                        if mc not in X_u_df.columns: X_u_df[mc] = 0.0
                    X_u = X_u_df[expected_features].values
                    # Re-standardize for this specific model's expected features
                    X_u_scaled = (X_u - X_u.mean(axis=0)) / (X_u.std(axis=0) + 1e-6)
                    
                    cluster_labels_umap = km_u.predict(X_u_scaled)
                    archetype_labels_umap = label_archetypes(km_u, expected_features)
                else:
                    cluster_labels_umap = km_u.predict(X_scaled)
                    archetype_labels_umap = label_archetypes(km_u, feature_cols)
        except Exception as e:
            logger.debug(f"UMAP figure clustering error: {e}")
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


def render_season_stage(payload: dict) -> html.Div:
    """
    Provisional season card stage — shows basic season stats without any AI calls.
    Used when a user clicks a season milestone in the timeline.
    """
    season = payload.get("season", "—")
    season_team = payload.get("season_team") or "—"
    stats = payload.get("stats") or {}
    mp = stats.get("matches_played", 0)
    g = stats.get("goals", 0)
    a = stats.get("assists", 0)
    mn = stats.get("minutes_played", 0)

    def _kpi(icon: str, label: str, value) -> html.Div:
        return html.Div([
            html.I(className=f"bi {icon} d-block mb-1",
                   style={"color": HKFATheme.ACCENT_BLUE, "fontSize": "0.95rem"}),
            html.Div(str(value), style={"fontSize": "1.3rem", "fontWeight": "800",
                                        "color": HKFATheme.TEXT_PRIMARY, "lineHeight": "1"}),
            html.Div(label, style={"fontSize": "0.6rem", "color": HKFATheme.TEXT_SECONDARY,
                                   "textTransform": "uppercase", "letterSpacing": "0.08em",
                                   "marginTop": "4px"}),
        ], className="season-pulse-card")

    return html.Div([
        html.Div([
            html.Span(season, style={"fontWeight": "700", "fontSize": "1.1rem",
                                     "color": HKFATheme.TEXT_PRIMARY}),
            html.Span(f"  ·  {season_team}",
                      style={"color": HKFATheme.TEXT_SECONDARY, "fontSize": "0.9rem"}),
        ], className="mb-3"),
        html.Div([
            _kpi("bi-calendar-check", "Matches", mp),
            _kpi("bi-bullseye", "Goals", g),
            _kpi("bi-hand-index-thumb", "Assists", a),
            _kpi("bi-stopwatch", "Minutes", mn),
        ], style={"display": "flex", "gap": "6px", "flexWrap": "wrap", "marginBottom": "24px"}),
        html.Div([
            html.I(className="bi bi-bar-chart-line me-2",
                   style={"color": HKFATheme.TEXT_SECONDARY}),
            html.Span("Season Analytics — Coming Soon",
                      style={"color": HKFATheme.TEXT_SECONDARY, "fontSize": "0.85rem"}),
        ], style={"padding": "12px 16px", "borderRadius": "8px",
                  "background": "rgba(255,255,255,0.03)",
                  "border": "1px solid rgba(255,255,255,0.08)"}),
    ], className="p-3")
