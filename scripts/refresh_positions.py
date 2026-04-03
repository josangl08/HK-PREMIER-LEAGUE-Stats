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


def _resolve_from_stats(season_stats: List[PlayerSeasonStat]):
    """
    Inspects advanced_stats across all season records for a player.
    Returns (primary, single_position, all_positions_list):
      - primary: value of 'Primary position' if found in any season (already an abbr)
      - single_pos: value of 'Position' if it's unambiguous (no comma) in ALL seasons
      - positions: flat list of all distinct positions found across seasons
    """
    primary = None
    all_positions = []

    for ss in season_stats:
        if not ss.advanced_stats:
            continue
        p = ss.advanced_stats.get('Primary position')
        if p and str(p).strip() and str(p).strip().lower() not in ('none', 'nan', ''):
            if primary is None:
                primary = str(p).strip()

        pos_raw = ss.advanced_stats.get('Position')
        if pos_raw and str(pos_raw).strip() and str(pos_raw).strip().lower() not in ('none', 'nan', ''):
            for token in str(pos_raw).split(','):
                token = token.strip()
                if token and token not in all_positions:
                    all_positions.append(token)

    # Single unambiguous position: every season record has the same single value
    single_pos = None
    if not primary and len(all_positions) == 1:
        single_pos = all_positions[0]

    return primary, single_pos, all_positions


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


def run(dry_run: bool = False) -> None:
    """
    Resolves Player.position_main for all players where it is NULL or a
    comma-separated list (ambiguous), using a 3-case DB-first strategy:

    Case A — DB has 'Primary position' in at least one season stat:
              write that value directly (no TM call).
    Case B — all season stats agree on a single unambiguous position:
              write that value directly (no TM call).
    Case C — multi-position, no Primary position anywhere in DB → TM:
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
        players_to_fix = session.execute(
            select(Player).where(
                or_(Player.position_main.is_(None), Player.position_main.contains(','))
            )
        ).scalars().all()

        logger.info(f"Players with NULL or multi-value position_main: {len(players_to_fix)}")

        stats_counter = {"case_a": 0, "case_b": 0, "case_c1": 0, "case_c2": 0,
                         "updated": 0, "skipped": 0, "no_match": 0}

        for player in sorted(players_to_fix, key=lambda p: p.name):
            season_stats = session.execute(
                select(PlayerSeasonStat).where(PlayerSeasonStat.player_id == player.id)
            ).scalars().all()

            primary, single_pos, all_positions = _resolve_from_stats(season_stats)

            # ── Case A: explicit Primary position in some season ─────────────
            if primary:
                abbr = primary  # already an abbreviation from Wyscout
                full = POSITION_FULL_NAMES.get(abbr, abbr)
                logger.info(f"{prefix}[A] {player.name} | primary='{primary}' → {abbr} ({full})")
                stats_counter["case_a"] += 1
                if not dry_run:
                    player.position_main = abbr
                    _update_stats_primary(session, player.id, abbr)
                    session.commit()
                    stats_counter["updated"] += 1
                continue

            # ── Case B: single unambiguous position ──────────────────────────
            if single_pos:
                abbr = single_pos
                full = POSITION_FULL_NAMES.get(abbr, abbr)
                logger.info(f"{prefix}[B] {player.name} | single pos='{single_pos}' → {abbr} ({full})")
                stats_counter["case_b"] += 1
                if not dry_run:
                    player.position_main = abbr
                    session.commit()
                    stats_counter["updated"] += 1
                continue

            # ── Case C: multi-position, no Primary anywhere ──────────────────
            hint_positions = ', '.join(all_positions) if all_positions else str(player.position_main or '')
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
                    f"{prefix}[C1] {player.name} | positions={all_positions} | tm_id={tm_id_str}"
                )
            else:
                stats_counter["case_c2"] += 1
                logger.info(
                    f"{prefix}[C2] {player.name} | positions={all_positions} | "
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
    args = parser.parse_args()
    run(dry_run=args.dry_run)
