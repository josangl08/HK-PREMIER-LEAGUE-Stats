# ABOUTME: Script to resolve ambiguous Player.position_main values using DB-only logic.
# ABOUTME: Reads PlayerSeasonStat.advanced_stats for Primary position; falls back to Transfermarkt search.

import sys
import time
import logging
import argparse
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select, or_
from models.db_models import Player, PlayerSeasonStat
from utils.db_engine import SessionFactory, init_db
from data.extractors.transfermarkt_extractor import TransfermarktExtractor
from data.processors.hong_kong_processor import POSITION_FULL_NAMES

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

RATE_LIMIT_SECONDS = 2

# Transfermarkt position label → internal abbreviation
_TM_TEXT_TO_ABBR: Dict[str, str] = {
    'goalkeeper': 'GK', 'portero': 'GK',
    'centre-back': 'CB', 'central': 'CB', 'central defender': 'CB', 'defensa central': 'CB', 'defensa': 'CB',
    'right-back': 'RB', 'lateral derecho': 'RB',
    'left-back': 'LB', 'lateral izquierdo': 'LB',
    'right wing-back': 'RWB', 'left wing-back': 'LWB',
    'defensive midfield': 'DM', 'pivote': 'DM', 'mediocentro defensivo': 'DM',
    'central midfield': 'CM', 'mediocentro': 'CM', 'centrocampista': 'CM',
    'attacking midfield': 'AMF', 'mediapunta': 'AMF', 'centrocampista ofensivo': 'AMF',
    'right midfield': 'RM', 'left midfield': 'LM',
    'interior derecho': 'RM', 'interior izquierdo': 'LM',
    'right winger': 'RW', 'extremo derecho': 'RW',
    'left winger': 'LW', 'extremo izquierdo': 'LW',
    'right wing forward': 'RWF', 'left wing forward': 'LWF',
    'centre-forward': 'CF', 'centre forward': 'CF', 'delantero centro': 'CF',
    'striker': 'ST', 'delantero': 'ST',
    'second striker': 'SS', 'segunda punta': 'SS',
}


def _tm_text_to_abbr(tm_text: str) -> Optional[str]:
    if not tm_text:
        return None
    key = tm_text.lower().strip()
    if key in _TM_TEXT_TO_ABBR:
        return _TM_TEXT_TO_ABBR[key]
    for pattern, code in _TM_TEXT_TO_ABBR.items():
        if pattern in key:
            return code
    return None


def _season_sort_key(season_id: str) -> tuple[int, int]:
    season_text = str(season_id or "").strip()
    try:
        start_text, end_text = season_text.split("-", 1)
        start_year = int(start_text)
        end_year = int(end_text) if len(end_text) == 4 else int(f"{start_text[:2]}{end_text}")
        return start_year, end_year
    except Exception:
        return 0, 0


def _extract_position_tokens(position_value: str) -> List[str]:
    if not position_value:
        return []
    return [
        token.strip()
        for token in str(position_value).split(",")
        if token and token.strip() and token.strip().lower() not in ("none", "nan")
    ]


def _is_valid_primary_position(position_value: str) -> bool:
    normalized = str(position_value or "").strip()
    if not normalized:
        return False
    return normalized.lower() not in ("none", "nan", "unknown")


def _resolve_from_stats(season_stats: List[PlayerSeasonStat]):
    """
    Inspects season stats with priority on the latest available season.
    Returns:
      - latest_primary: 'Primary position' from the latest season only
      - latest_single_pos: single unambiguous 'Position' from the latest season only
      - latest_positions: all position tokens from the latest season
      - all_positions: flat list of all distinct positions found across seasons
    """
    if not season_stats:
        return None, None, [], []

    latest_stat = max(
        season_stats,
        key=lambda ss: _season_sort_key(getattr(ss, "season_id", "") or ""),
    )
    latest_advanced = latest_stat.advanced_stats or {}

    latest_primary = None
    latest_primary_raw = latest_advanced.get("Primary position")
    if _is_valid_primary_position(latest_primary_raw):
        latest_primary = str(latest_primary_raw).strip()

    latest_positions = _extract_position_tokens(latest_advanced.get("Position", ""))
    latest_single_pos = None
    if not latest_primary and len(latest_positions) == 1:
        latest_single_pos = latest_positions[0]

    all_positions = []
    for ss in season_stats:
        if not ss.advanced_stats:
            continue
        for token in _extract_position_tokens(ss.advanced_stats.get("Position", "")):
            if token not in all_positions:
                all_positions.append(token)

    return latest_primary, latest_single_pos, latest_positions, all_positions


def _update_stats_primary(session, player_id: str, abbr: str) -> None:
    """
    Back-fills 'Primary position' in advanced_stats for all season records
    of this player that currently have a multi-value Position and no Primary position.
    """
    stats = session.execute(
        select(PlayerSeasonStat).where(PlayerSeasonStat.player_id == player_id)
    ).scalars().all()

    for ss in stats:
        if not ss.advanced_stats:
            continue
        pos = ss.advanced_stats.get('Position', '')
        existing_primary = ss.advanced_stats.get('Primary position')
        if pos and ',' in str(pos) and not existing_primary:
            # SQLAlchemy JSON column needs a new dict reference to detect mutation
            updated = dict(ss.advanced_stats)
            updated['Primary position'] = abbr
            ss.advanced_stats = updated


def run(dry_run: bool = False, all_players: bool = False) -> None:
    """
    Resolves Player.position_main using a latest-season-first strategy.

    By default it only processes players where position_main is NULL or a
    comma-separated list (ambiguous). With --all it reevaluates every player.

    Case A — latest season has 'Primary position':
              write that value directly (no TM call).
    Case B — latest season has a single unambiguous 'Position':
              write that value directly (no TM call).
    Case C — latest season is multi-position or unresolved → TM:
              C1: player.tm_id known → get_player_main_position()
              C2: no tm_id → search_player_by_name() → persist tm_id → get position

    In all cases, also back-fills PlayerSeasonStat.advanced_stats['Primary position']
    so the stats table stays consistent.
    """
    init_db()
    extractor = TransfermarktExtractor()
    session = SessionFactory()
    prefix = "[DRY-RUN] " if dry_run else ""

    try:
        player_query = select(Player)
        if not all_players:
            player_query = player_query.where(
                or_(Player.position_main.is_(None), Player.position_main.contains(','))
            )

        players_to_fix = session.execute(player_query).scalars().all()

        if all_players:
            logger.info(f"Players selected for full reevaluation: {len(players_to_fix)}")
        else:
            logger.info(f"Players with NULL or multi-value position_main: {len(players_to_fix)}")

        stats_counter = {"case_a": 0, "case_b": 0, "case_c1": 0, "case_c2": 0,
                         "updated": 0, "skipped": 0, "no_match": 0}

        for player in sorted(players_to_fix, key=lambda p: p.name):
            season_stats = session.execute(
                select(PlayerSeasonStat).where(PlayerSeasonStat.player_id == player.id)
            ).scalars().all()

            latest_primary, latest_single_pos, latest_positions, all_positions = _resolve_from_stats(season_stats)

            # ── Case A: explicit Primary position in latest season ───────────
            if latest_primary:
                abbr = latest_primary  # already an abbreviation from Wyscout
                full = POSITION_FULL_NAMES.get(abbr, abbr)
                logger.info(f"{prefix}[A] {player.name} | latest primary='{latest_primary}' → {abbr} ({full})")
                stats_counter["case_a"] += 1
                if not dry_run:
                    player.position_main = abbr
                    _update_stats_primary(session, player.id, abbr)
                    session.commit()
                    stats_counter["updated"] += 1
                continue

            # ── Case B: latest season has one clear position ─────────────────
            if latest_single_pos:
                abbr = latest_single_pos
                full = POSITION_FULL_NAMES.get(abbr, abbr)
                logger.info(f"{prefix}[B] {player.name} | latest single pos='{latest_single_pos}' → {abbr} ({full})")
                stats_counter["case_b"] += 1
                if not dry_run:
                    player.position_main = abbr
                    session.commit()
                    stats_counter["updated"] += 1
                continue

            # ── Case C: latest season ambiguous or unresolved → TM ───────────
            hint_positions = ', '.join(latest_positions or all_positions) if (latest_positions or all_positions) else str(player.position_main or '')
            team_hint = player.current_team.name if player.current_team else ""
            birth_year = None
            if player.birth_date:
                birth_year = player.birth_date.year
            elif player.age:
                birth_year = datetime.now().year - player.age

            tm_id_str: Optional[str] = None

            if player.tm_id:
                stats_counter["case_c1"] += 1
                tm_id_str = str(player.tm_id)
                logger.info(
                    f"{prefix}[C1] {player.name} | latest_positions={latest_positions or all_positions} | tm_id={tm_id_str}"
                )
            else:
                stats_counter["case_c2"] += 1
                logger.info(
                    f"{prefix}[C2] {player.name} | latest_positions={latest_positions or all_positions} | "
                    f"team='{team_hint}' nat='{player.nationality or ''}' by={birth_year}"
                )
                if dry_run:
                    continue
                found = extractor.search_player_by_name(
                    player.name,
                    team=team_hint,
                    nationality=player.nationality or player.birth_country or "",
                    birth_year=birth_year,
                    position=hint_positions,
                    team_id=player.current_team_id or "",
                )
                if not found:
                    logger.warning(f"    Could not resolve tm_id for {player.name!r} — skipping.")
                    stats_counter["no_match"] += 1
                    time.sleep(RATE_LIMIT_SECONDS)
                    continue
                player.tm_id = found
                session.commit()
                tm_id_str = str(found)
                logger.info(f"    Resolved tm_id={found}")
                time.sleep(RATE_LIMIT_SECONDS)

            if dry_run:
                continue

            tm_position = extractor.get_player_main_position(tm_id_str)
            if not tm_position:
                logger.warning(f"    TM returned no position for {player.name!r} — skipping.")
                stats_counter["skipped"] += 1
                time.sleep(RATE_LIMIT_SECONDS)
                continue

            abbr = _tm_text_to_abbr(tm_position)
            if not abbr:
                logger.warning(f"    Unrecognised TM text '{tm_position}' for {player.name!r} — skipping.")
                stats_counter["skipped"] += 1
                time.sleep(RATE_LIMIT_SECONDS)
                continue

            full = POSITION_FULL_NAMES.get(abbr, abbr)
            logger.info(f"    TM: '{tm_position}' → {abbr} ({full})")
            player.position_main = abbr
            _update_stats_primary(session, player.id, abbr)
            session.commit()
            stats_counter["updated"] += 1
            time.sleep(RATE_LIMIT_SECONDS)

        logger.info(
            f"\nDone. CaseA={stats_counter['case_a']}, CaseB={stats_counter['case_b']}, "
            f"CaseC1={stats_counter['case_c1']}, CaseC2={stats_counter['case_c2']} | "
            f"Updated={stats_counter['updated']}, Skipped={stats_counter['skipped']}, "
            f"NoMatch={stats_counter['no_match']}"
        )

    except Exception as e:
        logger.error(f"Script error: {e}", exc_info=True)
        session.rollback()
    finally:
        session.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Resolve ambiguous player positions from DB.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Log what would happen without writing to the DB.")
    parser.add_argument("--all", action="store_true",
                        help="Reevaluate all players, not only those with NULL or ambiguous position_main.")
    args = parser.parse_args()
    run(dry_run=args.dry_run, all_players=args.all)
