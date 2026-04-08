#!/usr/bin/env python
# ABOUTME: Resolves and verifies Transfermarkt IDs for all players in a given season.
# ABOUTME: Handles 3 cases: save new tm_id, update wrong tm_id, skip confirmed tm_id.

from __future__ import annotations

import argparse
import csv
import difflib
import logging
import os
import re
import sys
import time
import unicodedata
from datetime import datetime
from pathlib import Path

sys.path.append(os.getcwd())

from sqlalchemy import select, and_

from data.managers.transfermarkt_refresh_manager import TransfermarktRefreshManager
from models.db_models import Player, PlayerSeasonStat
from utils.db_engine import SessionFactory, init_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

RATE_LIMIT_SECONDS = 6.0
NAME_MATCH_THRESHOLD = 0.75


# ── Name-matching helpers (inline from verify_tm_ids logic) ──────────────────

def _strip(s: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", s.lower())
        if unicodedata.category(c) != "Mn"
    ).replace("-", " ")


def _name_score(a: str, b: str) -> float:
    a_s, b_s = _strip(a), _strip(b)
    base = difflib.SequenceMatcher(None, a_s, b_s).ratio()
    tokens = a_s.split()
    if len(tokens) >= 2:
        rev = " ".join(tokens[1:]) + " " + tokens[0]
        base = max(base, difflib.SequenceMatcher(None, rev, b_s).ratio())
    return base


def _verify_via_profile(extractor, tm_id: int, player_name: str) -> tuple[str, str, float]:
    """
    Fetch TM player profile and return (status, tm_name_found, name_score).
    status: CONFIRMED | NAME_MISMATCH | NAME_NOT_FOUND | FETCH_FAILED
    """
    url = f"{extractor.base_url}/x/profil/spieler/{tm_id}"
    soup = extractor._make_request(url)
    if soup is None:
        return "FETCH_FAILED", "", 0.0
    og = soup.find("meta", property="og:title")
    title_tag = soup.find("title")
    tm_name = ""
    if og and og.get("content"):
        tm_name = og["content"].split("|")[0].strip()
    elif title_tag:
        tm_name = title_tag.get_text().split("-")[0].strip()
    tm_name = re.sub(r"\s*[-–]\s*Perfil.*", "", tm_name, flags=re.IGNORECASE).strip()
    if not tm_name:
        return "NAME_NOT_FOUND", "", 0.0
    score = _name_score(player_name, tm_name)
    if score >= NAME_MATCH_THRESHOLD:
        return "CONFIRMED", tm_name, score
    return "NAME_MISMATCH", tm_name, score


# ── DB queries ───────────────────────────────────────────────────────────────

def _get_players_for_season(
    session,
    season: str,
    team_id: str | None = None,
) -> list[Player]:
    """Return ALL players present in the given season (with and without tm_id)."""
    query = (
        select(Player)
        .join(
            PlayerSeasonStat,
            and_(
                PlayerSeasonStat.player_id == Player.id,
                PlayerSeasonStat.season_id == season,
            ),
        )
        .distinct()
    )
    if team_id:
        query = query.where(Player.current_team_id == team_id)
    return session.execute(query).scalars().all()


def _apply_force_overrides(overrides: list[str]) -> int:
    """Apply manual player_id:tm_id overrides directly to DB."""
    count = 0
    with SessionFactory() as session:
        for entry in overrides:
            try:
                player_id, tm_id_str = entry.split(":")
                tm_id = int(tm_id_str)
                player = session.get(Player, player_id.strip())
                if not player:
                    logger.warning(f"Force override: player '{player_id}' not found.")
                    continue
                player.tm_id = tm_id
                logger.info(f"Force override: {player_id} → tm_id={tm_id} ({player.name})")
                count += 1
            except (ValueError, AttributeError) as e:
                logger.error(f"Invalid override format '{entry}': {e}. Use player_id:tm_id")
        session.commit()
    return count


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Sync Transfermarkt IDs for all players in a season. "
            "Saves missing tm_ids, verifies and updates wrong ones, skips correct ones."
        )
    )
    parser.add_argument(
        "--season", metavar="SEASON_ID", default="2025-26",
        help="Season to process (default: 2025-26).",
    )
    parser.add_argument(
        "--verify-existing", action="store_true",
        help=(
            "Re-verify players that already have tm_id. "
            "Updates the tm_id if the stored one doesn't match the TM profile."
        ),
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Scan and score candidates but do not write tm_id to DB.",
    )
    parser.add_argument(
        "--verbose", action="store_true",
        help="Enable DEBUG logging to see per-candidate scores.",
    )
    parser.add_argument(
        "--team", metavar="TEAM_ID",
        help="Only process players from this team_id (e.g. 'eastern', 'kitchee').",
    )
    parser.add_argument(
        "--export-csv", metavar="PATH",
        help="Export results to a CSV file for review.",
    )
    parser.add_argument(
        "--force", metavar="PLAYER_ID:TM_ID[,...]",
        help=(
            "Comma-separated manual assignments. "
            "Format: hk_abc123:456789,-123456:789012 "
            "(comma avoids shell issues with negative player IDs)."
        ),
    )
    parser.add_argument(
        "--max", type=int, default=0,
        help="Max players to process (0 = all).",
    )
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        logging.getLogger("data.extractors.transfermarkt_extractor").setLevel(logging.DEBUG)

    init_db()

    # Apply manual overrides first
    force_list = [x.strip() for x in args.force.split(",")] if args.force else None
    if force_list:
        forced = _apply_force_overrides(force_list)
        logger.info(f"Applied {forced} manual override(s).")
        if not args.team and not args.export_csv:
            return

    manager = TransfermarktRefreshManager()

    with SessionFactory() as session:
        players = _get_players_for_season(session, season=args.season, team_id=args.team)

    total = len(players)
    if total == 0:
        logger.info(f"No players found for season {args.season}.")
        return

    without_tm = sum(1 for p in players if p.tm_id is None)
    with_tm = total - without_tm
    logger.info(
        f"Season {args.season}: {total} players total — "
        f"{without_tm} without tm_id, {with_tm} with tm_id."
    )

    if args.max and args.max < total:
        players = players[: args.max]
        logger.info(f"Processing {len(players)} of {total} players (--max {args.max}).")

    results: list[dict] = []
    resolved = updated = confirmed = skipped = failed = 0

    for i, player in enumerate(players, 1):
        team_name = ""
        birth_year = None
        with SessionFactory() as session:
            p = session.get(Player, player.id)
            if p and p.current_team:
                team_name = p.current_team.name or ""
            birth_year = (
                p.birth_date.year if p and p.birth_date
                else ((datetime.now().year - p.age) if p and p.age else None)
            )

        logger.info(
            f"[{i}/{len(players)}] {player.name} | id={player.id} | team={player.current_team_id} "
            f"| nat={player.nationality} | birth={birth_year} | tm_id={player.tm_id}"
        )

        row: dict = {
            "player_id": player.id,
            "name": player.name,
            "team_id": player.current_team_id or "",
            "nationality": player.nationality or "",
            "birth_year": birth_year or "",
            "old_tm_id": player.tm_id or "",
            "tm_id_found": "",
            "tm_name": "",
            "name_score": "",
            "status": "",
        }

        if player.tm_id is not None:
            # ── Case: player already has tm_id ────────────────────────────
            if not args.verify_existing:
                row["tm_id_found"] = player.tm_id
                row["status"] = "skipped"
                skipped += 1
                results.append(row)
                continue

            # Verify existing tm_id against TM profile
            v_status, tm_name, score = _verify_via_profile(
                manager.extractor, player.tm_id, player.name
            )
            row["tm_name"] = tm_name
            row["name_score"] = f"{score:.3f}"

            if v_status == "CONFIRMED":
                row["tm_id_found"] = player.tm_id
                row["status"] = "confirmed"
                confirmed += 1
                logger.info(f"  ✓ Confirmed: tm_id={player.tm_id} → '{tm_name}' (score={score:.2f})")
            else:
                # Wrong or unverifiable — re-search
                logger.warning(
                    f"  ⚠ {v_status}: DB='{player.name}' TM='{tm_name}' "
                    f"(score={score:.2f}) — re-searching..."
                )
                if args.dry_run:
                    found = manager.extractor.search_player_by_name(
                        player.name,
                        team=team_name,
                        nationality=player.nationality or player.birth_country or "",
                        birth_year=birth_year,
                        team_id=player.current_team_id or "",
                    )
                else:
                    # Temporarily clear tm_id so resolve_tm_identity searches again
                    with SessionFactory() as session:
                        p = session.get(Player, player.id)
                        p.tm_id = None
                        session.commit()
                    found = manager.resolve_tm_identity(player.id, team=team_name)
                    if not found:
                        # Restore original tm_id if re-search failed
                        with SessionFactory() as session:
                            p = session.get(Player, player.id)
                            p.tm_id = player.tm_id
                            session.commit()

                row["tm_id_found"] = found or ""
                if found and found != player.tm_id:
                    row["status"] = "updated"
                    updated += 1
                    logger.info(f"  ✓ Updated: {player.tm_id} → {found}")
                elif found == player.tm_id:
                    row["status"] = "confirmed"
                    confirmed += 1
                    logger.info(f"  ✓ Re-confirmed same id: tm_id={found}")
                else:
                    row["status"] = "verify_failed"
                    failed += 1
                    logger.info(f"  ✗ Could not re-resolve after mismatch.")

        else:
            # ── Case: no tm_id — search and save ─────────────────────────
            if args.dry_run:
                found = manager.extractor.search_player_by_name(
                    player.name,
                    team=team_name,
                    nationality=player.nationality or player.birth_country or "",
                    birth_year=birth_year,
                    team_id=player.current_team_id or "",
                )
            else:
                found = manager.resolve_tm_identity(player.id, team=team_name)

            row["tm_id_found"] = found or ""
            if found:
                row["status"] = "resolved"
                resolved += 1
                logger.info(f"  ✓ Resolved: tm_id={found}")
            else:
                row["status"] = "unresolved"
                failed += 1
                logger.info(f"  ✗ No confident match found.")

        results.append(row)

        if i < len(players):
            time.sleep(RATE_LIMIT_SECONDS)

    # ── Summary ──────────────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"Season {args.season} | {len(players)} players processed")
    print(f"  ✓ Resolved (new):      {resolved}")
    if args.verify_existing:
        print(f"  ✓ Updated (corrected): {updated}")
        print(f"  ✓ Confirmed (ok):      {confirmed}")
    print(f"  — Skipped (has tm_id): {skipped}")
    print(f"  ✗ Failed/unresolved:   {failed}")
    if args.dry_run:
        print("  (dry-run: no changes written to DB)")

    # Print unresolved list
    unresolved = [r for r in results if r["status"] in ("unresolved", "verify_failed")]
    if unresolved:
        print(f"\nStill unresolved ({len(unresolved)}):")
        for r in unresolved:
            print(f"  {r['player_id']} | {r['name']} | {r['team_id']} | {r['nationality']}")
        print(
            "\nTo manually assign: "
            "python scripts/resolve_tm_ids.py --force hk_abc123:456789 hk_def456:789012"
        )

    # CSV export
    if args.export_csv and results:
        path = Path(args.export_csv)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(results[0].keys()))
            writer.writeheader()
            writer.writerows(results)
        print(f"\nExported {len(results)} rows → {path}")


if __name__ == "__main__":
    main()
