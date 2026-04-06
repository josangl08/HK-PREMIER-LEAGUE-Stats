# ABOUTME: One-time migration script to re-normalize competition_type in the fixtures table.
# ABOUTME: Applies updated COMPETITION_MAPPING to all existing records and reports changes.

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.db_engine import SessionFactory
from models.db_models import Fixture
from data.managers.fixture_manager import COMPETITION_MAPPING, STADIUM_MAPPING


def normalize_competition(raw: str) -> str:
    if raw in COMPETITION_MAPPING:
        return COMPETITION_MAPPING[raw]
    for k, v in sorted(COMPETITION_MAPPING.items(), key=lambda x: len(x[0]), reverse=True):
        if k in raw:
            return v
    return raw


def main():
    session = SessionFactory()
    try:
        fixtures = session.query(Fixture).all()
        changed = 0
        unmapped = set()

        for f in fixtures:
            old = f.competition_type or ""
            new = normalize_competition(old)
            if new != old:
                print(f"  [{f.id}] '{old}' -> '{new}'")
                f.competition_type = new
                changed += 1
            elif old and old not in set(COMPETITION_MAPPING.values()):
                unmapped.add(old)

        session.commit()
        print(f"\nUpdated {changed} records.")
        if unmapped:
            print(f"\nStill unmapped ({len(unmapped)}):")
            for v in sorted(unmapped):
                print(f"  {repr(v)}")
    finally:
        session.close()


if __name__ == "__main__":
    main()
