#!/usr/bin/env python3
# ABOUTME: Audits and merges duplicate player identities in the SQL database.
# ABOUTME: Safely resolves groups that share the same tm_id or a single tm_id across the same player name.

from __future__ import annotations

import logging
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from sqlalchemy import func, select, text

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from models.db_models import MatchHistory, Player, PlayerSeasonStat
from utils.db_engine import SessionFactory

logger = logging.getLogger(__name__)

_REF_TABLES = [
    "agent_player_links",
    "user_player_links",
    "match_history",
    "injuries",
    "player_photos",
    "card_designs",
    "match_update_queue",
]


@dataclass
class MergeGroup:
    name: str
    canonical_id: str
    duplicate_ids: List[str]
    reason: str


def _count_related(session, model, player_id: str) -> int:
    return int(
        session.execute(
            select(func.count()).select_from(model).where(model.player_id == player_id)
        ).scalar_one()
    )


def _player_score(session, player: Player) -> int:
    score = 0
    if player.tm_id:
        score += 100
    if player.current_team_id:
        score += 50
    if player.position_main:
        score += 10 if "," not in player.position_main else 4
    score += _count_related(session, PlayerSeasonStat, player.id) * 8
    score += _count_related(session, MatchHistory, player.id) * 2
    return score


def _pick_canonical_player(session, players: List[Player]) -> Player:
    ranked = sorted(
        players,
        key=lambda p: (
            _player_score(session, p),
            1 if p.current_team_id else 0,
            1 if p.tm_id else 0,
            p.id,
        ),
        reverse=True,
    )
    return ranked[0]


def _season_set(session, player_id: str) -> set[str]:
    return set(
        session.execute(
            select(PlayerSeasonStat.season_id).where(PlayerSeasonStat.player_id == player_id)
        ).scalars().all()
    )


def _is_sparse_duplicate(player: Player) -> bool:
    return not player.current_team_id and not player.tm_id and not player.position_main


def _merge_player_fields(canonical: Player, duplicate: Player) -> None:
    if canonical.tm_id is None and duplicate.tm_id is not None:
        canonical.tm_id = duplicate.tm_id
    if not canonical.current_team_id and duplicate.current_team_id:
        canonical.current_team_id = duplicate.current_team_id
    if (
        (not canonical.position_main or "," in str(canonical.position_main))
        and duplicate.position_main
        and "," not in str(duplicate.position_main)
    ):
        canonical.position_main = duplicate.position_main
    if not canonical.position_main and duplicate.position_main:
        canonical.position_main = duplicate.position_main
    if not canonical.nationality and duplicate.nationality:
        canonical.nationality = duplicate.nationality
    if not canonical.birth_country and duplicate.birth_country:
        canonical.birth_country = duplicate.birth_country
    if not canonical.foot and duplicate.foot:
        canonical.foot = duplicate.foot
    if not canonical.height and duplicate.height:
        canonical.height = duplicate.height
    if not canonical.age and duplicate.age:
        canonical.age = duplicate.age
    if not canonical.birth_date and duplicate.birth_date:
        canonical.birth_date = duplicate.birth_date


def _merge_season_stats(session, canonical_id: str, duplicate_id: str) -> int:
    moved = 0
    dup_stats = session.execute(
        select(PlayerSeasonStat).where(PlayerSeasonStat.player_id == duplicate_id)
    ).scalars().all()
    for dup in dup_stats:
        canon = session.execute(
            select(PlayerSeasonStat).where(
                PlayerSeasonStat.player_id == canonical_id,
                PlayerSeasonStat.season_id == dup.season_id,
            )
        ).scalar_one_or_none()
        if canon is None:
            dup.player_id = canonical_id
            moved += 1
            continue

        for field in (
            "matches_played",
            "minutes_played",
            "goals",
            "assists",
            "yellow_cards",
            "red_cards",
        ):
            canon_val = getattr(canon, field) or 0
            dup_val = getattr(dup, field) or 0
            setattr(canon, field, max(canon_val, dup_val))

        merged_advanced = dict(canon.advanced_stats or {})
        merged_advanced.update({k: v for k, v in (dup.advanced_stats or {}).items() if v not in (None, "", 0, 0.0)})
        canon.advanced_stats = merged_advanced
        session.delete(dup)
        moved += 1
    session.flush()
    return moved


def _move_simple_refs(session, table_name: str, canonical_id: str, duplicate_id: str) -> int:
    if table_name in {"agent_player_links", "user_player_links"}:
        session.execute(
            text(
                f"""
                INSERT OR IGNORE INTO {table_name} ({'agent_id' if table_name == 'agent_player_links' else 'user_id'}, player_id)
                SELECT {'agent_id' if table_name == 'agent_player_links' else 'user_id'}, :canonical_id
                FROM {table_name}
                WHERE player_id = :duplicate_id
                """
            ),
            {"canonical_id": canonical_id, "duplicate_id": duplicate_id},
        )
        result = session.execute(
            text(f"DELETE FROM {table_name} WHERE player_id = :duplicate_id"),
            {"duplicate_id": duplicate_id},
        )
        return int(result.rowcount or 0)

    result = session.execute(
        text(f"UPDATE {table_name} SET player_id = :canonical_id WHERE player_id = :duplicate_id"),
        {"canonical_id": canonical_id, "duplicate_id": duplicate_id},
    )
    return int(result.rowcount or 0)


def _delete_player_row(session, player_id: str) -> None:
    session.execute(text("DELETE FROM players WHERE id = :player_id"), {"player_id": player_id})


def find_merge_groups(session) -> List[MergeGroup]:
    players = session.execute(select(Player).order_by(Player.name, Player.id)).scalars().all()
    by_name: Dict[str, List[Player]] = defaultdict(list)
    for player in players:
        by_name[player.name].append(player)

    groups: List[MergeGroup] = []
    for name, dup_players in by_name.items():
        if len(dup_players) < 2:
            continue

        canonical = _pick_canonical_player(session, dup_players)
        tm_ids = {p.tm_id for p in dup_players if p.tm_id is not None}
        reason: Optional[str] = None
        if len(tm_ids) == 1 and tm_ids:
            reason = "same_name_single_tm_id"
        elif len(tm_ids) == 0:
            canonical_seasons = _season_set(session, canonical.id)
            sparse_duplicates = [p for p in dup_players if p.id != canonical.id]
            if not sparse_duplicates:
                continue
            if all(
                _is_sparse_duplicate(p)
                and _season_set(session, p.id).issubset(canonical_seasons)
                for p in sparse_duplicates
            ):
                reason = "same_name_sparse_subset"
            else:
                continue
        else:
            # more than one non-null tm_id under the same name is ambiguous
            continue

        duplicate_ids = [p.id for p in dup_players if p.id != canonical.id]
        if duplicate_ids:
            groups.append(
                MergeGroup(
                    name=name,
                    canonical_id=canonical.id,
                    duplicate_ids=duplicate_ids,
                    reason=reason,
                )
            )
    return groups


def merge_groups(apply_changes: bool = False) -> Dict[str, int]:
    session = SessionFactory()
    merged_players = 0
    merged_groups = 0
    moved_refs = 0
    try:
        groups = find_merge_groups(session)
        logger.info("Found %s safe duplicate groups", len(groups))
        for group in groups:
            logger.info(
                "Group %s -> canonical=%s duplicates=%s reason=%s",
                group.name,
                group.canonical_id,
                ",".join(group.duplicate_ids),
                group.reason,
            )
            if not apply_changes:
                continue

            canonical = session.get(Player, group.canonical_id)
            if canonical is None:
                continue

            for duplicate_id in group.duplicate_ids:
                duplicate = session.get(Player, duplicate_id)
                if duplicate is None:
                    continue

                _merge_player_fields(canonical, duplicate)
                moved_refs += _merge_season_stats(session, canonical.id, duplicate.id)
                session.flush()
                for table_name in _REF_TABLES:
                    moved_refs += _move_simple_refs(session, table_name, canonical.id, duplicate.id)

                session.flush()
                _delete_player_row(session, duplicate.id)
                merged_players += 1

            merged_groups += 1

        if apply_changes:
            session.commit()
        else:
            session.rollback()

        return {
            "groups": len(groups),
            "merged_groups": merged_groups,
            "merged_players": merged_players,
            "moved_refs": moved_refs,
        }
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def main(argv: List[str]) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    apply_changes = "--apply" in argv
    result = merge_groups(apply_changes=apply_changes)
    logger.info(
        "Duplicate player merge complete. apply=%s groups=%s merged_groups=%s merged_players=%s moved_refs=%s",
        apply_changes,
        result["groups"],
        result["merged_groups"],
        result["merged_players"],
        result["moved_refs"],
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
