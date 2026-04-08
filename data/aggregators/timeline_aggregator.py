# ABOUTME: Refactored TimelineAggregator using SQLAlchemy for high performance.
# ABOUTME: Fetches player milestones, fixtures, and match history directly from the database.

import logging
import re
from datetime import datetime, timezone, timedelta, date
from typing import List, Dict, Any, Optional
from sqlalchemy import select, and_, or_, func
from sqlalchemy.orm import joinedload

from models.db_models import Player, MatchHistory, Fixture, Team, PlayerSeasonStat, Injury
from utils.db_engine import SessionFactory
from data.managers.fixture_manager import get_fixture_manager

logger = logging.getLogger(__name__)

def get_season_from_date(dt: Any) -> str:
    """Determina la temporada YYYY-YY basándose en la fecha."""
    if hasattr(dt, "date"): dt = dt.date()
    year, month = dt.year, dt.month
    return f"{year}-{str(year+1)[-2:]}" if month >= 8 else f"{year-1}-{str(year)[-2:]}"

class TimelineAggregator:
    """
    Aggregator for player timeline milestones (Feature G).
    Backed by SQLAlchemy for maximum speed and data integrity.
    """
    def __init__(self, data_manager: Optional[Any] = None):
        self.data_manager = data_manager
        self.fixture_manager = get_fixture_manager()

    def get_player_timeline(
        self, player_id: str, insights: Optional[List[Dict]] = None
    ) -> List[Dict[str, Any]]:
        """
        Returns a chronological list of milestones for a player from SQL.
        """
        timeline = []
        session = SessionFactory()
        
        try:
            # 1. Resolve player info and relationships with eager loading
            stmt = (
                select(Player)
                .options(
                    joinedload(Player.current_team),
                    joinedload(Player.match_history),
                    joinedload(Player.injuries),
                    joinedload(Player.season_stats)
                )
                .where(Player.id == player_id)
            )
            player = session.execute(stmt).unique().scalar_one_or_none()
            
            if not player:
                logger.warning(f"Player ID {player_id} not found in database.")
                return []

            player_name = player.name
            current_team_id = player.current_team_id
            now_utc = datetime.now(timezone.utc)

            # ── Deduplicate Match History ───────────────────────────────────
            # Use (date, opponent) as unique key to prevent UI duplication
            unique_matches = {}
            for m in player.match_history:
                # Skip future ghost matches (> 1 month ahead)
                if m.date.replace(tzinfo=timezone.utc) > now_utc + timedelta(days=30):
                    continue
                
                key = (m.date.strftime("%Y-%m-%d"), m.opponent)
                if key not in unique_matches:
                    unique_matches[key] = m
            
            deduped_history = list(unique_matches.values())

            # 2. Add Next Fixtures (pre-match, live, or pending)
            if current_team_id:
                # Fetch up to 2 fixtures (current/recent one + the next future one)
                next_fixes = self.fixture_manager.get_next_fixtures(current_team_id, limit=2)
                for fix in next_fixes:
                    # Check if this fixture is already in MatchHistory
                    fix_date_str = fix["date_utc"].strftime("%Y-%m-%d")
                    is_in_history = any(
                        m.date.strftime("%Y-%m-%d") == fix_date_str 
                        and (fix["home_team"] in m.opponent or fix["away_team"] in m.opponent)
                        for m in deduped_history
                    )
                    
                    if is_in_history:
                        continue # Skip fixtures already confirmed in history

                    home_team = session.get(Team, fix["home_team"])
                    away_team = session.get(Team, fix["away_team"])
                    home_name = home_team.name if home_team else fix["home_team"]
                    away_name = away_team.name if away_team else fix["away_team"]
                    home_logo = home_team.logo_url if home_team else None
                    away_logo = away_team.logo_url if away_team else None
                    opponent_name = away_name if fix["home_team"] == current_team_id else home_name
                    
                    kickoff = fix["date_utc"].replace(tzinfo=timezone.utc)
                    
                    # Categorization logic
                    m_type = "pre-match"
                    status = "Scheduled"
                    label = f"Next: vs {opponent_name}"
                    icon = "calendar-plus"
                    
                    meta = fix.get("metadata") or {}
                    
                    # LIVE: Started < 115 minutes ago
                    if kickoff <= now_utc <= kickoff + timedelta(minutes=115):
                        status = "LIVE"
                        label = f"LIVE: vs {opponent_name}"
                        icon = "activity"
                    # PENDING: Started > 115 minutes ago but not in history
                    elif kickoff < now_utc:
                        status = "Pending Update"
                        label = f"Finished: vs {opponent_name}"
                        icon = "clock"

                    timeline.append({
                        "type": m_type,
                        "label": label,
                        "icon": icon,
                        "date": kickoff,
                        "group_year": get_season_from_date(fix["date_utc"]),
                        "payload": {
                            **fix,
                            "date_utc": fix["date_utc"].isoformat() if hasattr(fix["date_utc"], "isoformat") else fix["date_utc"],
                            "kickoff_utc": fix["kickoff_utc"].isoformat() if hasattr(fix["kickoff_utc"], "isoformat") else fix["kickoff_utc"],
                            "kickoff_hkt": fix["kickoff_hkt"].isoformat() if hasattr(fix["kickoff_hkt"], "isoformat") else fix["kickoff_hkt"],
                            "team": home_name if fix["home_team"] == current_team_id else away_name,
                            "home_team": home_name,
                            "away_team": away_name,
                            "home_logo": home_logo,
                            "away_logo": away_logo,
                            "opponent": opponent_name,
                            "streaming_url": fix.get("stream_url"),
                            "streaming_platform": fix.get("stream_platform") or ("Youtube" if fix.get("stream_url") and "youtube" in fix.get("stream_url").lower() else None),
                            "confirmation_status": status,
                            "has_var": meta.get("has_var", False),
                            "broadcast_type": meta.get("broadcast_type"),
                            "ticket_prices": meta.get("ticket_prices"),
                            "hkfa_status": meta.get("hkfa_status"),
                            "is_tv": meta.get("is_tv", False)
                        }
                    })

            # 3. Add Career Milestones (career)
            matches_by_season = {}
            
            # Fetch fixtures once to enrich historical matches
            fixtures_stmt = select(Fixture).where(
                or_(Fixture.home_team_id == current_team_id, Fixture.away_team_id == current_team_id)
            )
            all_team_fixtures = session.execute(fixtures_stmt).scalars().all() if current_team_id else []

            for m in deduped_history:
                sid = get_season_from_date(m.date)
                if sid not in matches_by_season:
                    matches_by_season[sid] = []
                
                raw = m.raw_data or {}
                # Attempt to find fixture metadata for enrichment
                fixture = next((f for f in all_team_fixtures if abs((f.date_utc.replace(tzinfo=timezone.utc) - m.date.replace(tzinfo=timezone.utc)).total_seconds()) <= 43200), None)
                meta = fixture.metadata_json if fixture else {}

                matches_by_season[sid].append({
                    "date": m.date.replace(tzinfo=timezone.utc),
                    "opponent": m.opponent,
                    "competition": m.competition_name,
                    "result": m.result,
                    "minutes_played": m.minutes_played,
                    "goals": m.goals,
                    "assists": m.assists,
                    "own_goals": raw.get("own_goals", 0),
                    "yellow_cards": m.yellow_cards,
                    "red_cards": m.red_cards,
                    "absence_reason": m.status if m.status != "Jugado" else None,
                    "player_stats": raw,
                    "has_var": meta.get("has_var", False),
                    "broadcast_type": meta.get("broadcast_type"),
                    "ticket_prices": meta.get("ticket_prices"),
                    "is_tv": meta.get("is_tv", False)
                })

            all_season_ids = {s.season_id for s in player.season_stats}
            all_season_ids.update(matches_by_season.keys())

            for sid in sorted(all_season_ids, reverse=True):
                # Skip future seasons with no real matches
                if sid not in matches_by_season and sid > get_season_from_date(now_utc.date()):
                    continue

                try:
                    year_start = int(sid.split('-')[0])
                    season_date = datetime(year_start + 1, 5, 30, tzinfo=timezone.utc)
                except:
                    season_date = now_utc

                stat = next((s for s in player.season_stats if s.season_id == sid), None)
                season_matches = matches_by_season.get(sid, [])
                season_team = None
                if stat and isinstance(stat.advanced_stats, dict):
                    for key in ("season_team", "Season Team", "Team within selected timeframe", "Team", "team", "team_name", "club", "club_name"):
                        value = stat.advanced_stats.get(key)
                        if value:
                            season_team = str(value).strip()
                            break
                if not season_team and player.current_team:
                    season_team = player.current_team.name

                timeline.append({
                    "type": "career",
                    "label": f"Season {sid}",
                    "icon": "trophy",
                    "date": season_date,
                    "group_year": sid,
                    "payload": {
                        "season": sid,
                        "player_id": player_id,
                        "player_name": player_name,
                        "season_team": season_team,
                        "matches": season_matches,
                        "stats": (
                        {
                            "matches_played": sum(1 for m in season_matches if int(m.get('minutes_played', 0) or 0) > 0),
                            "goals":          sum(int(m.get('goals', 0) or 0) for m in season_matches),
                            "assists":        sum(int(m.get('assists', 0) or 0) for m in season_matches),
                            "minutes_played": sum(int(m.get('minutes_played', 0) or 0) for m in season_matches),
                        } if season_matches else {
                            # Fallback: solo HKPL cuando no hay historial de TM scrapeado
                            "matches_played": stat.matches_played if stat else 0,
                            "goals":          stat.goals if stat else 0,
                            "assists":        stat.assists if stat else 0,
                            "minutes_played": stat.minutes_played if stat else 0,
                        }
                    )
                    }
                })

            # 4. Add Match History (post-match)
            for m in deduped_history:
                home_tm, away_tm = "Home", "Away"
                if " vs " in m.opponent:
                    parts = m.opponent.split(" vs ")
                    home_tm = re.sub(r"\(\d+\.\)", "", parts[0]).strip()
                    away_tm = re.sub(r"\(\d+\.\)", "", parts[1]).strip()
                
                def resolve_team(tm_name):
                    if not tm_name or tm_name in ("Home", "Away"): return None
                    stmt = select(Team).where(Team.name == tm_name).limit(1)
                    obj = session.execute(stmt).scalars().first()
                    if obj: return obj
                    slug = re.sub(r"[^a-z0-9]", "_", tm_name.lower()).strip("_")
                    obj = session.get(Team, slug)
                    if obj: return obj
                    mapping = {
                        "RCFC": "resources_capital", "Eastern": "eastern",
                        "Eastern Long Lions": "eastern", "Eastern Dist.": "eastern_district",
                        "Eastern District": "eastern_district", "Kitchee": "kitchee",
                        "Lee Man": "lee_man", "Southern": "southern_district",
                        "Tai Po": "tai_po", "HK Rangers": "rangers",
                        "HKFC": "hong_kong_football_club", "Happy Valley": "happy_valley"
                    }
                    if tm_name in mapping: return session.get(Team, mapping[tm_name])
                    stmt = select(Team).where(Team.name.like(f"%{tm_name}%")).order_by(func.length(Team.name).asc()).limit(1)
                    return session.execute(stmt).scalars().first()

                home_obj = resolve_team(home_tm)
                away_obj = resolve_team(away_tm)
                raw = m.raw_data or {}
                
                # Check for sofascore intelligence
                ss_intel = raw.get("sofascore_intelligence", {})
                ss_stats = ss_intel.get("statistics", {})
                ss_heatmap = ss_intel.get("heatmap", [])
                
                # High-fidelity is only True if we have real stats and a non-empty heatmap
                has_granular = bool(ss_stats.get("accuratePasses") or ss_stats.get("totalPass"))
                is_high_fidelity = bool(ss_heatmap) and has_granular

                timeline.append({
                    "type": "post-match",
                    "label": f"Result: {m.opponent}",
                    "icon": "chart-bar",
                    "date": m.date.replace(tzinfo=timezone.utc),
                    "group_year": get_season_from_date(m.date),
                    "payload": {
                        "opponent": m.opponent,
                        "home_team": home_tm,
                        "away_team": away_tm,
                        "home_logo": home_obj.logo_url if home_obj else None,
                        "away_logo": away_obj.logo_url if away_obj else None,
                        "date": m.date.replace(tzinfo=timezone.utc),
                        "competition": m.competition_name,
                        "competition_logo": m.competition_logo,
                        "result": m.result,
                        "minutes_played": m.minutes_played,
                        "goals": m.goals,
                        "assists": m.assists,
                        "own_goals": raw.get("own_goals", 0),
                        "yellow_cards": m.yellow_cards,
                        "red_cards": m.red_cards,
                        "position": m.position,
                        "status": m.status,
                        "subbed_in": raw.get("subbed_in"),
                        "subbed_out": raw.get("subbed_out"),
                        "absence_reason": m.status if m.status != "Jugado" else None,
                        "confirmation_status": "Confirmed" if m.minutes_played > 0 else "Not played",
                        # Intelligence data injection (Task 3.1)
                        "rating": raw.get("besoccer_rating") or raw.get("rating") or ss_stats.get("rating"),
                        "heatmap": ss_heatmap,
                        "match_stats": ss_stats or raw.get("player_stats"),
                        "intelligence_meta": {
                            "has_besoccer": "besoccer_rating" in raw,
                            "has_sofascore": bool(ss_intel),
                            "is_high_fidelity": is_high_fidelity
                        },
                        "player_stats": {
                            "basic_info": {
                                "name": player_name,
                                "position_primary": player.position_main
                            }
                        }
                    }
                })

            # 5. Add Injuries
            for inj in player.injuries:
                d = inj.start_date.replace(tzinfo=timezone.utc) if inj.start_date else now_utc
                timeline.append({
                    "type": "injury",
                    "label": f"Injury: {inj.injury_type}",
                    "icon": "activity",
                    "date": d,
                    "group_year": get_season_from_date(d),
                    "payload": {
                        "type": inj.injury_type,
                        "severity": inj.severity,
                        "days_out": inj.days_out,
                        "status": inj.status
                    }
                })

            # 6. Inject AI Insights
            if insights:
                for ins in insights:
                    ts = ins.get("timestamp")
                    if not ts: continue
                    try:
                        ins_dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
                        if ins_dt.tzinfo is None: ins_dt = ins_dt.replace(tzinfo=timezone.utc)
                        timeline.append({
                            "type": "ai-insight",
                            "label": ins.get("title", "AI Insight"),
                            "icon": "cpu",
                            "date": ins_dt,
                            "group_year": get_season_from_date(ins_dt),
                            "payload": ins
                        })
                    except: continue

            timeline.sort(key=lambda x: x["date"], reverse=True)
            return timeline

        finally:
            session.close()
