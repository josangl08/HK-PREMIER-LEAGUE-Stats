# ABOUTME: CLI wrapper to download team logos from TheSportsDB with deterministic project slugs.
# ABOUTME: Reuses the shared API-first logo resolver used before Transfermarkt fallback.

from __future__ import annotations

import argparse
import os
import sys

sys.path.append(os.getcwd())

from utils.team_logo_api import fetch_team_logo_from_api


def main() -> None:
    parser = argparse.ArgumentParser(description="Download team logos from TheSportsDB.")
    parser.add_argument("teams", nargs="+", help="Team names to download.")
    args = parser.parse_args()

    for team_name in args.teams:
        try:
            result = fetch_team_logo_from_api(team_name, overwrite=True)
            if result:
                print(f"{team_name} -> {result}")
            else:
                print(f"{team_name} -> NOT FOUND")
        except Exception as exc:
            print(f"{team_name} -> ERROR: {exc}")


if __name__ == "__main__":
    main()
