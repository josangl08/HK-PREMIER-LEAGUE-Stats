#!/usr/bin/env python
# ABOUTME: Verifies existing tm_ids for HK players in a given season by cross-referencing TM squad pages.
# ABOUTME: Outputs CONFIRMED / NAME_MISMATCH / NOT_IN_SQUAD per player and exports a CSV report.

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
from pathlib import Path

sys.path.append(os.getcwd())

from sqlalchemy import text

from data.extractors.transfermarkt_extractor import _TEAM_TM_CLUB_IDS
from data.extractors.transfermarkt_playwright_extractor import TransfermarktPlaywrightExtractor
from utils.db_engine import SessionFactory, init_db

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

RATE_LIMIT = 4.0
NAME_MATCH_THRESHOLD = 0.75  # minimum SequenceMatcher ratio to count as name match


def _strip(s: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", s.lower())
        if unicodedata.category(c) != "Mn"
    ).replace("-", " ")


def _name_score(a: str, b: str) -> float:
    a_s, b_s = _strip(a), _strip(b)
    # Direct ratio
    base = difflib.SequenceMatcher(None, a_s, b_s).ratio()
    # Also try reversed token order (East-Asian names)
    tokens = a_s.split()
    if len(tokens) >= 2:
        rev = " ".join(tokens[1:]) + " " + tokens[0]
        base = max(base, difflib.SequenceMatcher(None, rev, b_s).ratio())
    return base


def fetch_squad(ext: TransfermarktPlaywrightExtractor, tm_club_id: int) -> dict[int, str]:
    """Fetch TM squad page and return {tm_id: player_name} for all squad members."""
    url = f"{ext.base_url}/x/kader/verein/{tm_club_id}"
    soup = ext._make_request(url)
    if soup is None:
        return {}
    result: dict[int, str] = {}
    for a_tag in soup.find_all("a", href=re.compile(r"/profil/spieler/\d+")):
        href = a_tag.get("href", "")
        m = re.search(r"/spieler/(\d+)", href)
        if not m:
            continue
        tid = int(m.group(1))
        name = a_tag.get_text(strip=True)
        if name and tid not in result:
            result[tid] = name
    return result


def verify_via_profile(
    ext: TransfermarktPlaywrightExtractor, tm_id: int, player_name: str
) -> tuple[str, str, float]:
    """
    Fetch TM player profile and return (status, tm_name_found, name_score).
    Used for players whose team is not in _TEAM_TM_CLUB_IDS.
    """
    url = f"{ext.base_url}/x/profil/spieler/{tm_id}"
    soup = ext._make_request(url)
    if soup is None:
        return "FETCH_FAILED", "", 0.0
    # Extract player name from page title or h1
    og = soup.find("meta", property="og:title")
    title_tag = soup.find("title")
    tm_name = ""
    if og and og.get("content"):
        tm_name = og["content"].split("|")[0].strip()
    elif title_tag:
        tm_name = title_tag.get_text().split("-")[0].strip()
    # Strip TM page suffix like " - Perfil del jugador 25/26" or " - Perfil del jugador 2026"
    tm_name = re.sub(r"\s*[-–]\s*Perfil.*", "", tm_name, flags=re.IGNORECASE).strip()
    if not tm_name:
        return "NAME_NOT_FOUND", "", 0.0
    score = _name_score(player_name, tm_name)
    if score >= NAME_MATCH_THRESHOLD:
        return "CONFIRMED", tm_name, score
    return "NAME_MISMATCH", tm_name, score


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify existing tm_ids for all players in a season.")
    parser.add_argument("--season", default="2025-26", help="Season ID (default: 2025-26)")
    parser.add_argument("--team", help="Only verify players from this team_id.")
    parser.add_argument("--hk-only", action="store_true",
                        help="Only verify HK players (hk_ prefix). Default: all players with tm_id.")
    parser.add_argument("--export-csv", metavar="PATH", default="reports/tm_verify_results.csv",
                        help="Export results to CSV.")
    parser.add_argument("--fix", action="store_true",
                        help="Auto-correct mismatched tm_ids using squad-page search.")
    args = parser.parse_args()

    init_db()
    ext = TransfermarktPlaywrightExtractor()

    try:
        with SessionFactory() as session:
            filters = [
                f'pss.season_id = "{args.season}"',
                'p.tm_id IS NOT NULL',
            ]
            if args.hk_only:
                filters.append('p.id LIKE "hk_%"')
            if args.team:
                filters.append(f'p.current_team_id = "{args.team}"')
            rows = session.execute(text(f'''
                SELECT DISTINCT p.id, p.name, p.current_team_id, p.tm_id, p.nationality
                FROM players p
                JOIN player_season_stats pss ON pss.player_id = p.id
                WHERE {" AND ".join(filters)}
                ORDER BY p.current_team_id, p.name
            ''')).fetchall()

        hk_count = sum(1 for r in rows if r[0].startswith("hk_"))
        foreign_count = len(rows) - hk_count
        logger.info(
            f"Verifying {len(rows)} players for season {args.season} "
            f"(HK={hk_count}, foreign={foreign_count})."
        )

        # Group by team and pre-fetch squad pages
        squad_cache: dict[int, dict[int, str]] = {}  # tm_club_id → {tm_id: name}

        results: list[dict] = []
        confirmed = name_mismatch = not_in_squad = fetch_failed = 0

        current_team = None
        squad: dict[int, str] = {}

        for player_id, player_name, team_id, tm_id, nationality in rows:
            tm_id = int(tm_id)

            # Load squad page once per team (only for known HKPL clubs)
            if team_id != current_team:
                current_team = team_id
                tm_club_id = _TEAM_TM_CLUB_IDS.get(team_id)
                if tm_club_id:
                    if tm_club_id not in squad_cache:
                        logger.info(f"Fetching squad for {team_id} (tm_club_id={tm_club_id})...")
                        squad_cache[tm_club_id] = fetch_squad(ext, tm_club_id)
                        time.sleep(RATE_LIMIT)
                    squad = squad_cache[tm_club_id]
                else:
                    squad = {}

            # Determine status
            if squad:
                if tm_id in squad:
                    tm_name = squad[tm_id]
                    score = _name_score(player_name, tm_name)
                    if score >= NAME_MATCH_THRESHOLD:
                        status = "CONFIRMED"
                        confirmed += 1
                    else:
                        status = "NAME_MISMATCH"
                        name_mismatch += 1
                        logger.warning(
                            f"  MISMATCH {player_id}: DB='{player_name}' TM='{tm_name}' "
                            f"(score={score:.2f}) tm_id={tm_id}"
                        )
                else:
                    tm_name = ""
                    score = 0.0
                    status = "NOT_IN_SQUAD"
                    not_in_squad += 1
                    logger.warning(
                        f"  NOT_IN_SQUAD {player_id}: '{player_name}' tm_id={tm_id} "
                        f"not found in {team_id} squad"
                    )
            else:
                # Unknown team — verify via profile page
                status, tm_name, score = verify_via_profile(ext, tm_id, player_name)
                if status == "CONFIRMED":
                    confirmed += 1
                elif status == "NAME_MISMATCH":
                    name_mismatch += 1
                    logger.warning(
                        f"  MISMATCH {player_id}: DB='{player_name}' TM='{tm_name}' "
                        f"(score={score:.2f}) tm_id={tm_id}"
                    )
                else:
                    fetch_failed += 1
                time.sleep(RATE_LIMIT)

            results.append({
                "player_id": player_id,
                "db_name": player_name,
                "team_id": team_id or "",
                "tm_id": tm_id,
                "tm_name": tm_name,
                "name_score": f"{score:.3f}",
                "status": status,
                "nationality": nationality or "",
            })

        # Summary
        total = len(results)
        print(f"\n{'='*55}")
        print(f"Season: {args.season} | Total verified: {total}")
        print(f"  CONFIRMED:      {confirmed} ({confirmed/total*100:.1f}%)")
        print(f"  NAME_MISMATCH:  {name_mismatch}")
        print(f"  NOT_IN_SQUAD:   {not_in_squad}")
        print(f"  FETCH_FAILED:   {fetch_failed}")

        # Print problems
        problems = [r for r in results if r["status"] != "CONFIRMED"]
        if problems:
            print(f"\nProblems ({len(problems)}):")
            for r in problems:
                print(
                    f"  [{r['status']}] {r['player_id']} | {r['db_name']} | "
                    f"team={r['team_id']} | tm_id={r['tm_id']} | tm_name='{r['tm_name']}'"
                )

        # CSV export
        if args.export_csv:
            path = Path(args.export_csv)
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=list(results[0].keys()))
                writer.writeheader()
                writer.writerows(results)
            print(f"\nExported {total} rows → {path}")

    finally:
        ext.close()


if __name__ == "__main__":
    main()
