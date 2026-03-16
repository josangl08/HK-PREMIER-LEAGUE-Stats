# ABOUTME: Agent tools for HK Premier League Stats Platform (Feature G).
# ABOUTME: Typed LangChain tools wrapping existing DataManager, Aggregator, and AI layer calls.

"""
Agent tools module defining the capabilities of the LangGraph agent.
Each tool is a typed wrapper over the project's internal data and ML APIs.
"""

# Standard Library
import logging
import os
from typing import Any, Dict, List, Optional

# Third-party
from langchain_core.tools import tool

logger = logging.getLogger(__name__)


@tool
def query_players(filters: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Search for players based on specific criteria (team, position, season, nationality).
    Filters can include: 'team', 'position', 'season', 'age_min', 'age_max', 'nationality'.
    Returns a list of matching player basic records with keys: player_name, team, position, season.
    """
    try:
        from utils.app_context import get_hong_kong_data_manager
        dm = get_hong_kong_data_manager()
    except RuntimeError:
        return []

    if dm.processed_data is None or dm.processed_data.empty:
        return []

    df = dm.processed_data.copy()

    # Apply each supported filter
    if "team" in filters and filters["team"]:
        df = df[df["Team"].str.lower() == str(filters["team"]).lower()]

    if "position" in filters and filters["position"]:
        position_col = "Position_Group" if "Position_Group" in df.columns else "Position_Primary_Group"
        if position_col in df.columns:
            df = df[df[position_col].str.lower() == str(filters["position"]).lower()]

    if "season" in filters and filters["season"]:
        if "Season" in df.columns:
            df = df[df["Season"] == str(filters["season"])]

    if "age_min" in filters and "Age" in df.columns:
        df = df[df["Age"] >= int(filters["age_min"])]

    if "age_max" in filters and "Age" in df.columns:
        df = df[df["Age"] <= int(filters["age_max"])]

    if "nationality" in filters and "Nationality" in df.columns and filters["nationality"]:
        df = df[df["Nationality"].str.lower() == str(filters["nationality"]).lower()]

    player_col = "Player" if "Player" in df.columns else "player_name"
    position_col = "Position_Group" if "Position_Group" in df.columns else "Position_Primary_Group"

    results = []
    for _, row in df.iterrows():
        record: Dict[str, Any] = {
            "player_name": row.get(player_col, ""),
            "team": row.get("Team", ""),
            "season": row.get("Season", ""),
        }
        if position_col in row.index:
            record["position"] = row.get(position_col, "")
        if "Age" in row.index:
            record["age"] = row.get("Age", None)
        results.append(record)

    return results


@tool
def get_percentiles(player_name: str, season: str, metrics: List[str]) -> Dict[str, Optional[float]]:
    """
    Calculate the league percentile rank (0-100) for a player across specified metrics for a given season.
    Useful for understanding a player's relative performance level.
    Returns a dict mapping each metric name to its percentile value, or None if not available.
    """
    try:
        from utils.app_context import get_hong_kong_data_manager
        dm = get_hong_kong_data_manager()
    except RuntimeError:
        return {m: None for m in metrics}

    if dm.processed_data is None or dm.processed_data.empty:
        return {m: None for m in metrics}

    df = dm.processed_data

    player_col = "Player" if "Player" in df.columns else "player_name"

    # Filter to the requested season for league comparison
    if "Season" in df.columns:
        season_df = df[df["Season"] == season]
    else:
        season_df = df

    if season_df.empty:
        return {m: None for m in metrics}

    # Find the player row in this season
    player_mask = season_df[player_col].str.lower() == player_name.lower()
    player_rows = season_df[player_mask]

    if player_rows.empty:
        return {m: None for m in metrics}

    player_row = player_rows.iloc[0]

    result: Dict[str, Optional[float]] = {}
    for metric in metrics:
        if metric not in season_df.columns or metric not in player_row.index:
            result[metric] = None
            continue
        player_value = player_row[metric]
        try:
            percentile = float((season_df[metric] <= player_value).mean() * 100)
            result[metric] = round(percentile, 1)
        except (TypeError, ValueError):
            result[metric] = None

    return result


@tool
def detect_changes(player_name: str, season: str, threshold: float = 0.15) -> List[Dict[str, Any]]:
    """
    Compare a player's performance metrics against the league average for the season.
    Returns a list of metrics where the player deviates by more than 'threshold' (fractional) from league average.
    Each result has: metric, player_value, league_avg, deviation (positive = above average).
    """
    try:
        from utils.app_context import get_hong_kong_data_manager
        dm = get_hong_kong_data_manager()
    except RuntimeError:
        return []

    if dm.processed_data is None or dm.processed_data.empty:
        return []

    df = dm.processed_data
    player_col = "Player" if "Player" in df.columns else "player_name"

    if "Season" in df.columns:
        season_df = df[df["Season"] == season]
    else:
        season_df = df

    if season_df.empty:
        return []

    player_mask = season_df[player_col].str.lower() == player_name.lower()
    player_rows = season_df[player_mask]

    if player_rows.empty:
        return []

    player_row = player_rows.iloc[0]

    # Only check numeric columns
    numeric_cols = season_df.select_dtypes(include="number").columns.tolist()
    # Exclude non-performance columns
    excluded = {"Age", "Jersey number"}
    numeric_cols = [c for c in numeric_cols if c not in excluded]

    deviating = []
    for col in numeric_cols:
        if col not in player_row.index:
            continue
        player_value = player_row[col]
        league_avg = season_df[col].mean()

        if league_avg == 0:
            continue

        try:
            deviation = float((player_value - league_avg) / abs(league_avg))
            if abs(deviation) >= threshold:
                deviating.append({
                    "metric": col,
                    "player_value": round(float(player_value), 3),
                    "league_avg": round(float(league_avg), 3),
                    "deviation": round(deviation, 3),
                })
        except (TypeError, ValueError, ZeroDivisionError):
            continue

    # Sort by absolute deviation descending
    deviating.sort(key=lambda x: abs(x["deviation"]), reverse=True)
    return deviating


@tool
def generate_card(player_name: str, season: str) -> str:
    """
    Generate a summary performance card for a player.
    Returns a Markdown string representing the card layout.
    Full rendering (Feature A) is scheduled for S4.
    """
    return f"[Card generation pending Feature A] Player: {player_name}, Season: {season}"


@tool
def create_dossier(player_name: str) -> str:
    """
    Create a comprehensive scouting dossier for a player, including performance history and AI insights.
    Returns a Markdown string of the dossier.
    Full dossier generation with Track 3 integration (Feature C) is scheduled for S4.
    """
    return f"[Dossier generation pending Feature C] Player: {player_name}"


@tool
def generate_caption(player_name: str, context: str) -> str:
    """
    Generate a natural language social media caption for a player based on their recent performance context.
    Uses Gemini Flash for creative synthesis. Requires GOOGLE_API_KEY environment variable.
    """
    api_key = os.environ.get("GOOGLE_API_KEY", "").strip().strip('"').strip("'")
    if not api_key:
        return "[Caption generation requires GOOGLE_API_KEY]"

    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
        from langchain_core.messages import HumanMessage

        model_name = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
        llm = ChatGoogleGenerativeAI(model=model_name, google_api_key=api_key)
        prompt = (
            f"Write a short, engaging social media caption (2-3 sentences) for "
            f"{player_name} in the context of: {context}. "
            f"Style: professional football, Hong Kong Premier League."
        )
        response = llm.invoke([HumanMessage(content=prompt)])
        return str(response.content).strip()
    except Exception as exc:
        logger.warning("generate_caption failed: %s", exc)
        return f"[Caption generation error: {exc}]"
