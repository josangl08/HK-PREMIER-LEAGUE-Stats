#!/usr/bin/env python
# ABOUTME: Resolves local HKPL/domestic match logos for user-linked players using local assets/DB, API, then TM fallback.
# ABOUTME: Derives home and away teams from opponent text when raw_data lacks explicit team names.

from __future__ import annotations

import argparse
import os
import re
import sys
from typing import Optional

from sqlalchemy import select

sys.path.append(os.getcwd())

from data.extractors.transfermarkt_extractor import TransfermarktExtractor
from models.db_models import MatchHistory, UserPlayerLink, agent_player_links
from utils.db_engine import SessionFactory, init_db
from utils.team_logo_api import clean_team_name, fetch_team_logo_from_api
from utils.stage_helpers import _resolve_team_logo


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


def resolve_best_logo(team_name: Optional[str]) -> Optional[str]:
    if not team_name:
        return None
    cleaned_name = clean_team_name(team_name)
    return _resolve_team_logo(cleaned_name) or fetch_team_logo_from_api(cleaned_name)


def main() -> None:
    parser = argparse.ArgumentParser(description="Resolve local user-linked MatchHistory logos.")
    parser.add_argument("--dry-run", action="store_true", help="Show candidate updates without writing.")
    parser.add_argument("--limit", type=int, default=0, help="Optional max number of rows to process.")
    args = parser.parse_args()

    init_db()
    extractor = TransfermarktExtractor()
    logo_cache: dict[str, Optional[str]] = {}

    with SessionFactory() as session:
        player_ids = {row[0] for row in session.execute(select(UserPlayerLink.player_id)).all()}
        player_ids.update(row[0] for row in session.execute(select(agent_player_links.c.player_id)).all())
        if not player_ids:
            print("No user/agent-linked players found.")
            return

        rows = session.execute(
            select(MatchHistory)
            .where(MatchHistory.player_id.in_(tuple(player_ids)))
            .order_by(MatchHistory.date.desc())
        ).scalars().all()

        target_rows = []
        for match in rows:
            if is_national_team_competition(match.competition_name):
                continue
            if is_club_continental_competition(match.competition_name):
                continue
            raw = dict(match.raw_data or {})
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
            report_url = raw.get("match_report_url")
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

            home_key = clean_team_name(home_team)
            away_key = clean_team_name(away_team)

            if home_key not in logo_cache:
                logo_cache[home_key] = resolve_best_logo(home_team)
            if away_key not in logo_cache:
                logo_cache[away_key] = resolve_best_logo(away_team)

            home_logo = logo_cache.get(home_key) or raw.get("home_logo")
            away_logo = logo_cache.get(away_key) or raw.get("away_logo")

            if (not home_logo or not away_logo) and report_url and home_team and away_team:
                logo_result = extractor.resolve_match_report_logos(report_url, home_team, away_team)
                home_logo = home_logo or logo_result.get("home_logo")
                away_logo = away_logo or logo_result.get("away_logo")

            if home_logo or away_logo:
                raw["home_logo"] = home_logo
                raw["away_logo"] = away_logo
                raw["logo_resolution_status"] = "resolved"
                resolved += 1
            else:
                raw["logo_resolution_status"] = "failed"
                failed += 1

            match.raw_data = raw

            if args.dry_run:
                skipped += 1

        if args.dry_run:
            print(f"Dry run: target={len(target_rows)} resolved={resolved} failed={failed} skipped={skipped}")
            return

        session.commit()
        print(f"Processed {len(target_rows)} rows. resolved={resolved} failed={failed} skipped={skipped}")


if __name__ == "__main__":
    main()
