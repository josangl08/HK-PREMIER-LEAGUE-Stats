#!/usr/bin/env python
# ABOUTME: Resolves large continental match crests from Transfermarkt match report pages for user-linked players.
# ABOUTME: Reuses season history scraping to recover missing match_report_url values before downloading logos.

from __future__ import annotations

import argparse
import os
import re
import sys
import time
from datetime import datetime
from typing import Dict, Optional, Tuple

from sqlalchemy import select

sys.path.append(os.getcwd())

from data.extractors.transfermarkt_extractor import TransfermarktExtractor
from data.extractors.transfermarkt_playwright_extractor import TransfermarktPlaywrightExtractor
from models.db_models import MatchHistory, Player, UserPlayerLink, agent_player_links
from utils.team_logo_api import clean_team_name, fetch_team_logo_from_api
from utils.db_engine import SessionFactory, init_db


def normalize_opponent(text: str) -> str:
    value = re.sub(r"\(\d+\.\)", "", str(text or "")).strip().lower()
    value = re.sub(r"[^a-z0-9]+", " ", value).strip()
    return value


def match_history_entry(db_match: MatchHistory, entry: Dict) -> bool:
    db_date = db_match.date.strftime("%d/%m/%Y")
    if db_date != str(entry.get("date") or ""):
        return False
    db_opp = normalize_opponent(db_match.opponent or "")
    entry_opp = normalize_opponent(entry.get("opponent") or "")
    if db_opp and entry_opp and db_opp == entry_opp:
        return True
    return False


def split_opponent_pair(opponent_text: str) -> tuple[str | None, str | None]:
    text = str(opponent_text or "").strip()
    if " vs " not in text:
        return None, None
    home_raw, away_raw = text.split(" vs ", 1)
    def _clean(value: str) -> str:
        cleaned = re.sub(r"\(\d+\.\)", "", value or "").strip()
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned
    return _clean(home_raw), _clean(away_raw)


def is_national_team_competition(name: str | None) -> bool:
    text = str(name or "").lower()
    national_tokens = [
        "asian cup",
        "world cup",
        "qualification",
        "qualifier",
        "nations cup",
        "friendly international",
        "u17",
        "u20",
        "u23",
        "u-17",
        "u-20",
        "u-23",
    ]
    return any(token in text for token in national_tokens)


def is_club_continental_competition(name: str | None) -> bool:
    text = str(name or "").lower()
    club_tokens = [
        "afc champions league",
        "champions league two",
        "afc cup",
        "copa de la afc",
        "acl",
    ]
    return any(token in text for token in club_tokens) and not is_national_team_competition(text)


def get_user_linked_player_ids(session) -> set[str]:
    player_ids = {row[0] for row in session.execute(select(UserPlayerLink.player_id)).all()}
    player_ids.update(row[0] for row in session.execute(select(agent_player_links.c.player_id)).all())
    return player_ids


def main() -> None:
    parser = argparse.ArgumentParser(description="Resolve large AFC/ACL crests from Transfermarkt match report pages.")
    parser.add_argument("--dry-run", action="store_true", help="Show candidate updates without writing.")
    parser.add_argument("--limit", type=int, default=0, help="Optional max number of rows to process.")
    args = parser.parse_args()

    init_db()
    visible_debug = os.getenv("TM_VISIBLE_DEBUG", "").strip().lower() in {"1", "true", "yes", "on"}
    extractor = TransfermarktPlaywrightExtractor() if visible_debug else TransfermarktExtractor()
    if visible_debug and isinstance(extractor, TransfermarktPlaywrightExtractor):
        extractor._ensure_browser(None)
        print("TM_VISIBLE_DEBUG active: Playwright browser bootstrapped.")
        time.sleep(2.0)
    season_cache: Dict[Tuple[int, str], list[Dict]] = {}
    logo_cache: Dict[str, Optional[str]] = {}

    try:
        with SessionFactory() as session:
            player_ids = get_user_linked_player_ids(session)
            rows = session.execute(
                select(MatchHistory)
                .where(MatchHistory.player_id.in_(tuple(player_ids)))
                .order_by(MatchHistory.date.desc())
            ).scalars().all()

            target_rows = []
            for match in rows:
                if not is_club_continental_competition(match.competition_name):
                    continue
                raw = match.raw_data or {}
                if raw.get("logo_resolution_status") != "pending":
                    continue
                target_rows.append(match)
            if args.limit > 0:
                target_rows = target_rows[: args.limit]

            resolved = 0
            failed = 0
            skipped = 0
            for match in target_rows:
                raw = dict(match.raw_data or {})
                player = session.get(Player, match.player_id)
                if not player or not player.tm_id:
                    raw["logo_resolution_status"] = "failed"
                    match.raw_data = raw
                    failed += 1
                    continue

                season_id = match.date.strftime("%Y")
                if match.date.month < 8:
                    season_id = f"{match.date.year - 1}-{str(match.date.year)[-2:]}"
                else:
                    season_id = f"{match.date.year}-{str(match.date.year + 1)[-2:]}"

                report_url = raw.get("match_report_url")
                if not report_url:
                    cache_key = (int(player.tm_id), season_id)
                    if cache_key not in season_cache:
                        season_cache[cache_key] = extractor.get_match_history(str(player.tm_id), season_id) or []
                    matched_entry = next((entry for entry in season_cache[cache_key] if match_history_entry(match, entry)), None)
                    if matched_entry:
                        report_url = matched_entry.get("match_report_url")
                        raw["match_report_url"] = report_url
                        raw["home_team"] = raw.get("home_team") or matched_entry.get("home_team")
                        raw["away_team"] = raw.get("away_team") or matched_entry.get("away_team")

                home_team = raw.get("home_team")
                away_team = raw.get("away_team")

                if not home_team or not away_team:
                    parsed_home, parsed_away = split_opponent_pair(match.opponent or raw.get("opponent") or "")
                    home_team = home_team or parsed_home
                    away_team = away_team or parsed_away
                    if home_team:
                        raw["home_team"] = home_team
                    if away_team:
                        raw["away_team"] = away_team

                # API-first: try TheSportsDB before scraping Transfermarkt.
                home_key = clean_team_name(home_team)
                away_key = clean_team_name(away_team)

                if home_key not in logo_cache:
                    logo_cache[home_key] = fetch_team_logo_from_api(home_team)
                if away_key not in logo_cache:
                    logo_cache[away_key] = fetch_team_logo_from_api(away_team)

                home_logo = logo_cache.get(home_key) or raw.get("home_logo")
                away_logo = logo_cache.get(away_key) or raw.get("away_logo")

                if (not home_logo or not away_logo) and report_url and home_team and away_team:
                    result = extractor.resolve_match_report_logos(report_url, home_team, away_team)
                    home_logo = home_logo or result.get("home_logo")
                    away_logo = away_logo or result.get("away_logo")

                if home_logo or away_logo:
                    raw["home_logo"] = home_logo
                    raw["away_logo"] = away_logo
                    raw["logo_resolution_status"] = "resolved"
                    resolved += 1
                else:
                    raw["logo_resolution_status"] = "failed"
                    failed += 1
                match.raw_data = raw

                if not args.dry_run:
                    session.flush()
                if visible_debug:
                    time.sleep(2.0)

            if args.dry_run:
                print(f"Dry run: target={len(target_rows)} resolved={resolved} failed={failed} skipped={skipped}")
                if visible_debug:
                    print("TM_VISIBLE_DEBUG active: keeping browser open for 8 seconds before exit.")
                    time.sleep(8.0)
                return

            session.commit()
            print(f"Processed {len(target_rows)} rows. resolved={resolved} failed={failed} skipped={skipped}")
            if visible_debug:
                print("TM_VISIBLE_DEBUG active: keeping browser open for 8 seconds before exit.")
                time.sleep(8.0)
    finally:
        if hasattr(extractor, "close"):
            extractor.close()


if __name__ == "__main__":
    main()
