# ABOUTME: Aggregator for player timeline milestones (Feature G).
# ABOUTME: Combines historical season data, fixtures, and TM match history; adds confirmation_status to milestones.

import logging
import re
import json
from datetime import datetime, timezone, timedelta, date
from typing import List, Dict, Any, Optional, TYPE_CHECKING
from pathlib import Path

if TYPE_CHECKING:
    from data.hong_kong_data_manager import HongKongDataManager

from data.managers.fixture_manager import get_fixture_manager, _resolve_logo as _resolve_team_logo
from utils.player_index import get_player_index
from data.extractors.transfermarkt_extractor import TransfermarktExtractor
from data.processors.player_match_processor import enrich_absence_reason

logger = logging.getLogger(__name__)

# Manual mapping for Transfermarkt IDs (internal Wyscout/Slug -> TM Numeric ID)
# Used for players where automatic name-based mapping is non-trivial or not yet implemented.
TM_ID_MAP = {
    "148891": "160182",  # José Ángel (Wyscout 148891 -> TM 160182)
    "125040": "146608",  # Manuel Bleda (Wyscout 125040 -> TM 146608)
    "355333": "339749",  # Felipe Sá (Wyscout 355333 -> TM 339749)
}

_TM_DATE_FORMATS = ["%m/%d/%y", "%d/%m/%y", "%d/%m/%Y", "%b %d, %Y", "%d %b %Y", "%Y-%m-%d"]


def _parse_tm_date(date_str: str) -> Optional[date]:
    """Try parsing a Transfermarkt date string into a date object."""
    for fmt in _TM_DATE_FORMATS:
        try:
            return datetime.strptime(date_str.strip(), fmt).date()
        except ValueError:
            continue
    return None


def _parse_opponent(opponent_str: str) -> tuple:
    """Parse 'Team A(n.) vs Team B(m.)' → (home_team, away_team), stripping rank suffixes."""
    cleaned = re.sub(r'\(\d+\.\)', '', opponent_str or "").strip()
    parts = re.split(r'\s+[Vv][Ss]\s+', cleaned, maxsplit=1)
    if len(parts) == 2:
        return parts[0].strip(), parts[1].strip()
    return cleaned, ""


def _build_match_report_from_tm_status(tm_match: dict) -> Optional[dict]:
    """Map TM match `status` field to a match_report dict for enrich_absence_reason."""
    status = (tm_match.get("status") or "").lower()
    if not status:
        return None
    if "no convocado" in status:
        return {"in_squad": False}
    if "lesion" in status or "lesionado" in status:
        return {"absence_marker": "lesion"}
    if "sancionado" in status:
        return {"absence_marker": "suspendido"}
    return None


def _find_tm_match(fixture_utc: datetime, tm_matches: List[Dict]) -> Optional[Dict]:
    """
    Return the TM match dict whose date is within ±1 day of fixture_utc.
    Returns None if no match is found.
    """
    fixture_date = fixture_utc.date()
    for m in tm_matches:
        tm_date = _parse_tm_date(m.get("date", ""))
        if tm_date is None:
            continue
        if abs((fixture_date - tm_date).days) <= 1:
            return m
    return None


def _map_absence_reason(reason: Optional[str]) -> Optional[str]:
    """Map internal absence slug to user-friendly display text."""
    if not reason:
        return None
    mapping = {
        "not_summoned": "Not Summoned",
        "injured": "Absence: Injury",
        "suspended": "Absence: Suspension",
        "unknown": "Absence: Unknown"
    }
    return mapping.get(reason, f"Absence: {reason.replace('_', ' ').title()}")


class TimelineAggregator:
    def __init__(self, data_manager: Optional['HongKongDataManager'] = None):
        if data_manager is None:
            from data.hong_kong_data_manager import HongKongDataManager
            self.data_manager = HongKongDataManager()
        else:
            self.data_manager = data_manager
        
        self.fixture_manager = get_fixture_manager()
        self.player_index = get_player_index()

    def get_player_timeline(
        self, player_id: str, insights: Optional[List[Dict]] = None
    ) -> List[Dict[str, Any]]:
        """
        Returns a chronological list of milestones for a player.
        Pass optional `insights` to inject ai-insight type milestones at correct positions.
        """
        timeline = []
        
        # 1. Resolve player info
        player_info = self.player_index.get_player_info(player_id)
        if not player_info:
            logger.warning(f"Player ID {player_id} not found in index.")
            return []

        player_name = player_info.get("canonical_name")
        seasons = player_info.get("seasons", [])

        # Load historical record JSON for metadata merging (Task 3.2)
        historical_record = {}
        historical_path = Path(__file__).parent.parent / "historical_records" / f"{player_id}.json"
        if historical_path.exists():
            try:
                with open(historical_path, "r", encoding="utf-8") as f:
                    historical_record = json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load historical record for {player_id}: {e}")

        # Resolve current season and its end-year
        current_season = seasons[0] if seasons else None
        try:
            current_season_end_year = str(int(current_season.split('-')[0]) + 1) if current_season else None
        except Exception:
            current_season_end_year = None

        # 2. Find player's current team
        current_team = None
        player_stats = self.data_manager.get_player_overview(player_name)
        if player_stats and 'error' not in player_stats:
            current_team = player_stats.get('basic_info', {}).get('team')
        
        now_utc = datetime.now(timezone.utc)

        # ── Transfermarkt ID resolution ───────────────────────────────────
        tm_id = TM_ID_MAP.get(player_id)

        # 3. Add Next Fixture (pre-match)
        if current_team:
            next_fix = self.fixture_manager.get_next_fixture(current_team)
            if next_fix:
                opponent = next_fix.get("away_team") if next_fix.get("home_team") == current_team else next_fix.get("home_team")
                timeline.append({
                    "type": "pre-match",
                    "label": f"Next: vs {opponent}",
                    "icon": "calendar-plus",
                    "date": next_fix.get("kickoff_utc"),
                    "payload": {
                        "opponent": opponent,
                        "date": next_fix.get("kickoff_utc"),
                        "kickoff_display": next_fix.get("kickoff_display"),
                        "stadium": next_fix.get("stadium"),
                        "home_team": next_fix.get("home_team"),
                        "away_team": next_fix.get("away_team"),
                        "home_logo": next_fix.get("home_logo_url"),
                        "away_logo": next_fix.get("away_logo_url"),
                        "streaming_url": next_fix.get("streaming_url"),
                        "streaming_platform": next_fix.get("streaming_platform"),
                        "competition": next_fix.get("competition"),
                        "home_fanart": next_fix.get("home_fanart_url"),
                        "away_fanart": next_fix.get("away_fanart_url"),
                        "stadium_thumb": next_fix.get("stadium_thumb_url"),
                        "confirmation_status": "Scheduled",
                    }
                })

        # 4. Add Past Matches (post-match)
        if current_team:
            all_fixtures = self.fixture_manager.get_fixtures()
            past_team_matches = [
                f for f in all_fixtures
                if (f.get("home_team") == current_team or f.get("away_team") == current_team)
                and f.get("kickoff_utc") < now_utc
            ]
            past_team_matches.sort(key=lambda x: x.get("kickoff_utc"), reverse=True)

            tm_current_matches: List[Dict[str, Any]] = []
            if tm_id:
                for season_str in seasons:
                    try:
                        extractor = TransfermarktExtractor()
                        season_matches = extractor.get_match_history(tm_id, season_str)
                        tm_current_matches.extend(season_matches)
                    except Exception as exc:
                        logger.debug(f"TM history unavailable for {player_id}/{season_str}: {exc}")

            for match in past_team_matches:
                opponent = match.get("away_team") if match.get("home_team") == current_team else match.get("home_team")
                kickoff_utc = match.get("kickoff_utc")
                tm_match = _find_tm_match(kickoff_utc, tm_current_matches) if kickoff_utc else None
                
                # Resolve confirmation status and performance data
                tm_minutes = int(tm_match.get("minutes_played", 0) or 0) if tm_match else 0
                if tm_match:
                    confirmation_status = "Confirmed" if tm_minutes > 0 else "Not played"
                else:
                    confirmation_status = "Scheduled"

                tm_result = tm_match.get("result") if tm_match else None
                tm_goals = int(tm_match.get("goals", 0) or 0) if tm_match else 0
                tm_assists = int(tm_match.get("assists", 0) or 0) if tm_match else 0
                absence_reason = None
                if tm_match and tm_minutes == 0:
                    enriched = enrich_absence_reason(tm_match, _build_match_report_from_tm_status(tm_match))
                    absence_reason = _map_absence_reason(enriched.get("absence_reason"))

                # Task 3.2: Merge metadata from historical record JSON (precedence over ICS)
                json_stadium = None
                json_platform = None
                if historical_record and kickoff_utc:
                    fix_date_str = kickoff_utc.strftime("%d/%m/%Y")
                    for s_key, s_data in historical_record.get("seasons", {}).items():
                        for m in s_data.get("matches", []):
                            if m.get("date") == fix_date_str and opponent in m.get("opponent", ""):
                                json_stadium = m.get("stadium")
                                json_platform = m.get("streaming_platform")
                                break
                        if json_stadium or json_platform: break

                group_year = current_season_end_year or (str(kickoff_utc.year) if kickoff_utc else None)

                timeline.append({
                    "type": "post-match",
                    "label": f"Result: vs {opponent}",
                    "icon": "chart-bar",
                    "date": kickoff_utc,
                    "group_year": group_year,
                    "payload": {
                        "opponent": opponent,
                        "date": kickoff_utc,
                        "kickoff_display": match.get("kickoff_display"),
                        "home_team": match.get("home_team"),
                        "away_team": match.get("away_team"),
                        "home_logo": match.get("home_logo_url") or _resolve_team_logo(match.get("home_team", "")),
                        "away_logo": match.get("away_logo_url") or _resolve_team_logo(match.get("away_team", "")),
                        "competition": match.get("competition"),
                        "stadium": json_stadium or match.get("stadium"),
                        "streaming_platform": json_platform or match.get("streaming_platform"),
                        "result": tm_result,
                        "minutes_played": tm_minutes,
                        "goals": tm_goals,
                        "assists": tm_assists,
                        "absence_reason": absence_reason,
                        "player_stats": player_stats,
                        "match_id": match.get("uid"),
                        "confirmation_status": confirmation_status,
                    }
                })

        # 5. Add Career Milestones (career) + per-match cards for past seasons
        for season in seasons:
            try:
                year_end = int(season.split('-')[0]) + 1
                season_date = datetime(year_end, 5, 30, tzinfo=timezone.utc)
            except Exception:
                year_end = now_utc.year
                season_date = now_utc - timedelta(days=365)

            group_year = str(year_end)

            matches: List[Dict[str, Any]] = []
            if tm_id:
                try:
                    season_start_year = season.split('-')[0]
                    extractor = TransfermarktExtractor()
                    raw_matches = extractor.get_match_history(tm_id, season_start_year)
                    matches = [enrich_absence_reason(m, _build_match_report_from_tm_status(m)) for m in raw_matches]
                except Exception as match_exc:
                    logger.debug(f"Match history unavailable for {player_id}/{season}: {match_exc}")

            timeline.append({
                "type": "career",
                "label": f"Season {season}",
                "icon": "trophy",
                "date": season_date,
                "group_year": group_year,
                "payload": {
                    "season": season,
                    "player_id": player_id,
                    "player_name": player_name,
                    "matches": matches,
                }
            })

            if season != current_season:
                for tm_m in matches:
                    tm_date = _parse_tm_date(tm_m.get("date", ""))
                    if tm_date is None:
                        continue
                    match_dt = datetime(tm_date.year, tm_date.month, tm_date.day, tzinfo=timezone.utc)
                    home_t, away_t = _parse_opponent(tm_m.get("opponent", ""))
                    minutes = int(tm_m.get("minutes_played", 0) or 0)
                    
                    # Map absence reason
                    abs_reason = _map_absence_reason(tm_m.get("absence_reason"))

                    timeline.append({
                        "type": "post-match",
                        "label": f"Result: {tm_m.get('opponent', '')}",
                        "icon": "chart-bar",
                        "date": match_dt,
                        "group_year": group_year,
                        "payload": {
                            "kickoff_display": tm_m.get("date", ""),
                            "home_team": home_t,
                            "away_team": away_t,
                            "home_logo": _resolve_team_logo(home_t),
                            "away_logo": _resolve_team_logo(away_t),
                            "competition": tm_m.get("competition", ""),
                            "result": tm_m.get("result"),
                            "minutes_played": minutes,
                            "goals": int(tm_m.get("goals", 0) or 0),
                            "assists": int(tm_m.get("assists", 0) or 0),
                            "absence_reason": abs_reason,
                            "confirmation_status": "Confirmed" if minutes > 0 else "Not played",
                        }
                    })

        # Inject AI insight milestones at chronologically correct positions
        if insights:
            for ins in insights:
                ts = ins.get("timestamp")
                if not ts:
                    continue
                try:
                    ins_dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
                    if ins_dt.tzinfo is None:
                        ins_dt = ins_dt.replace(tzinfo=timezone.utc)
                except (ValueError, AttributeError):
                    logger.warning(f"Could not parse insight timestamp: {ts}")
                    continue
                timeline.append({
                    "type": "ai-insight",
                    "label": ins.get("title", "AI Insight"),
                    "icon": "cpu",
                    "date": ins_dt,
                    "group_year": str(ins_dt.year),
                    "payload": {
                        "title": ins.get("title", "AI Insight"),
                        "summary": ins.get("summary", ""),
                        "detail": ins.get("detail", ""),
                        "timestamp": ts,
                    }
                })

        # Final sort: most recent first
        timeline.sort(key=lambda x: x["date"], reverse=True)

        return timeline
