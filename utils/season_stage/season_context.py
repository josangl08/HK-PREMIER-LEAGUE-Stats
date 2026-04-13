# ABOUTME: Builds the selected-season context for the season stage from payload, SQL season data, and match history.
# ABOUTME: Keeps season-stage data assembly separate from UI rendering and legacy stage helper flows.

from __future__ import annotations

from typing import Any, Dict, List, Optional

import pandas as pd

from utils.app_context import get_hong_kong_data_manager
from utils.common import get_current_season


def _normalize_competition_name(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return "Other"
    return text


def load_selected_season_dataframe(season: str) -> pd.DataFrame:
    """Returns a processed season DataFrame without mutating the global manager season state."""
    try:
        dm = get_hong_kong_data_manager()
        if dm.current_season == season and dm.aggregator is not None:
            return dm.aggregator.data.copy()

        raw_df = dm._load_season_dataframe(season)
        if raw_df is None or raw_df.empty:
            return pd.DataFrame()
        return dm.processor.process_season_data(raw_df, season)
    except Exception:
        return pd.DataFrame()


def get_season_player_row(player_name: str, season: str) -> Optional[pd.Series]:
    season_df = load_selected_season_dataframe(season)
    if season_df.empty or "Player" not in season_df.columns:
        return None
    matches = season_df[season_df["Player"] == player_name]
    if matches.empty:
        return None
    return matches.iloc[0]


def build_season_competition_split(matches: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Aggregates played-match output by competition for the selected season."""
    competition_rows: Dict[str, Dict[str, Any]] = {}
    for match in matches or []:
        minutes = int(match.get("minutes_played", 0) or 0)
        if minutes <= 0:
            continue
        competition = _normalize_competition_name(match.get("competition"))
        row = competition_rows.setdefault(
            competition,
            {
                "competition": competition,
                "matches_played": 0,
                "minutes_played": 0,
                "goals": 0,
                "assists": 0,
                "yellow_cards": 0,
                "red_cards": 0,
            },
        )
        row["matches_played"] += 1
        row["minutes_played"] += minutes
        row["goals"] += int(match.get("goals", 0) or 0)
        row["assists"] += int(match.get("assists", 0) or 0)
        row["yellow_cards"] += int(match.get("yellow_cards", 0) or 0)
        row["red_cards"] += int(match.get("red_cards", 0) or 0)

    rows = list(competition_rows.values())
    rows.sort(key=lambda item: (-item["minutes_played"], item["competition"]))
    return rows


def build_previous_season_context(player_name: str, season: str, history_df: pd.DataFrame) -> Dict[str, Any]:
    if history_df is None or history_df.empty or "Season" not in history_df.columns:
        return {}
    season_matches = history_df[history_df["Season"] == season]
    if season_matches.empty:
        return {}
    current_idx = season_matches.index[-1]
    if current_idx <= 0:
        return {}
    prev_row = history_df.iloc[current_idx - 1]
    return {"season": str(prev_row.get("Season") or ""), "row": prev_row}


def build_season_snapshot(payload: Dict[str, Any], season_row: Optional[pd.Series]) -> Dict[str, Any]:
    stats = dict(payload.get("stats") or {})
    snapshot = {
        "matches_played": int(stats.get("matches_played", 0) or 0),
        "goals": int(stats.get("goals", 0) or 0),
        "assists": int(stats.get("assists", 0) or 0),
        "minutes_played": int(stats.get("minutes_played", 0) or 0),
    }
    if season_row is not None:
        for key in ("Matches played", "Goals", "Assists", "Minutes played"):
            if key in season_row.index:
                normalized_key = key.lower().replace(" ", "_")
                snapshot[normalized_key] = int(float(season_row.get(key) or 0))
    return snapshot


def build_season_stage_context(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Builds the full season-stage context from payload and season data."""
    from utils.stage_helpers import _fetch_player_season_history, _get_position_group

    season = str(payload.get("season") or "")
    player_id = str(payload.get("player_id") or "")
    player_name = str(payload.get("player_name") or "Player")
    season_team = str(payload.get("season_team") or "—")
    history_df = _fetch_player_season_history(player_name)
    season_row = get_season_player_row(player_name, season)
    season_df = load_selected_season_dataframe(season)

    pos_group = "Midfielder"
    try:
        dm = get_hong_kong_data_manager()
        if season_row is not None and "Position_Group" in season_row.index:
            pos_group = str(season_row.get("Position_Group") or "Midfielder")
        else:
            pos_group = _get_position_group(player_name, dm)
    except Exception:
        pass

    return {
        "season": season,
        "current_season": get_current_season(),
        "is_current_season": season == get_current_season(),
        "player_id": player_id,
        "player_name": player_name,
        "season_team": season_team,
        "season_df": season_df,
        "season_row": season_row,
        "history_df": history_df,
        "snapshot": build_season_snapshot(payload, season_row),
        "previous_season": build_previous_season_context(player_name, season, history_df),
        "competition_split": build_season_competition_split(payload.get("matches") or []),
        "matches": payload.get("matches") or [],
        "pos_group": pos_group,
    }
