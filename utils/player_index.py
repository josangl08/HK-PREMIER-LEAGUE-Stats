# ABOUTME: Cross-season player identity index for the HKPL dataset.
# ABOUTME: Resolves Wyscout IDs (2018-2022) or generates deterministic slugs (2023+).

import csv
import hashlib
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# Seasons that include the Wyscout id column in the CSV export
_WYSCOUT_SEASONS = {"2018-19", "2019-20", "2020-21", "2021-22", "2022-23"}

_CACHE_DIR = Path(__file__).parent.parent / "data" / "cache"
_INDEX_FILE = Path(__file__).parent.parent / "data" / "player_index.json"

# Season filename mapping (mirrors HongKongDataExtractor.available_seasons)
_SEASON_FILES = {
    "2018-19": "hong_kong_2018_19.csv",
    "2019-20": "hong_kong_2019_20.csv",
    "2020-21": "hong_kong_2020_21.csv",
    "2021-22": "hong_kong_2021_22.csv",
    "2022-23": "hong_kong_2022_23.csv",
    "2023-24": "hong_kong_2023_24.csv",
    "2024-25": "hong_kong_2024_25.csv",
    "2025-26": "hong_kong_2025_26.csv",
}


def _normalize(value: str) -> str:
    """Strip whitespace and BOM from CSV cell values."""
    return value.strip().lstrip("\ufeff") if value else ""


def _generate_slug(name: str, birth_country: str, foot: str, height: str) -> str:
    """
    Generates a deterministic 8-char slug from immutable biometric fields.
    Prefixed with 'hk_' to distinguish from real Wyscout IDs.
    """
    fingerprint = f"{name}|{birth_country}|{foot}|{height}"
    return "hk_" + hashlib.sha1(fingerprint.encode("utf-8")).hexdigest()[:8]


def _read_csv_rows(csv_path: Path) -> list[dict]:
    """Reads a CSV and returns rows as dicts with normalized keys."""
    with open(csv_path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        return [{_normalize(k): _normalize(v) for k, v in row.items()} for row in reader]


class PlayerIndex:
    """
    Maintains a persistent cross-season player ID index.

    Structure of player_index.json:
    {
      "_meta": { "built_at": "...", "total_players": N },
      "by_id": {
        "65492":        { "canonical_name": "Yapp Hung Fai", "id_type": "wyscout",   "seasons": [...], "fingerprint": {...} },
        "hk_a1b2c3d4": { "canonical_name": "A. Rollin",     "id_type": "generated", "seasons": [...], "fingerprint": {...} }
      },
      "by_name": {
        "Yapp Hung Fai": "65492",
        "A. Rollin":     "hk_a1b2c3d4"
      }
    }
    """

    def __init__(self):
        self._index: Dict = {"_meta": {}, "by_id": {}, "by_name": {}}
        self._loaded = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_player_id(self, name: str) -> Optional[str]:
        """Returns the canonical player ID for a given name, or None."""
        self._ensure_loaded()
        return self._index["by_name"].get(name)

    def get_player_info(self, player_id: str) -> Optional[Dict]:
        """Returns full index entry for a player ID."""
        self._ensure_loaded()
        return self._index["by_id"].get(player_id)

    def get_all_player_names(self) -> list[str]:
        """Returns all canonical player names in the index."""
        self._ensure_loaded()
        return list(self._index["by_name"].keys())

    def build(self, force: bool = False) -> bool:
        """
        Builds the index from all cached CSV files.
        Skips if index already exists and force=False.
        Returns True on success.
        """
        if _INDEX_FILE.exists() and not force:
            logger.info("Player index already exists — skipping build (use force=True to rebuild).")
            self._load()
            return True

        logger.info("Building player index from cached CSV files...")
        by_id: Dict[str, Dict] = {}
        by_name: Dict[str, str] = {}

        # ── PASS 1: ingest seasons WITH Wyscout id ──────────────────────
        name_to_wyscout: Dict[str, str] = {}  # for cross-referencing pass 2

        for season in sorted(_WYSCOUT_SEASONS):
            csv_path = _CACHE_DIR / _SEASON_FILES.get(season, "")
            if not csv_path.exists():
                logger.debug(f"Cache missing for {season}, skipping.")
                continue

            rows = _read_csv_rows(csv_path)
            for row in rows:
                name = row.get("Player", "")
                wyscout_raw = row.get("Wyscout id", "")
                if not name or not wyscout_raw:
                    continue

                player_id = wyscout_raw  # keep as string
                name_to_wyscout[name] = player_id

                fingerprint = {
                    "birth_country": row.get("Birth country", ""),
                    "foot": row.get("Foot", ""),
                    "height": row.get("Height", ""),
                }

                if player_id not in by_id:
                    by_id[player_id] = {
                        "canonical_name": name,
                        "id_type": "wyscout",
                        "seasons": [],
                        "fingerprint": fingerprint,
                    }
                if season not in by_id[player_id]["seasons"]:
                    by_id[player_id]["seasons"].append(season)

                # by_name: favour most recent season if name appears multiple times
                by_name[name] = player_id

        # ── PASS 2: ingest seasons WITHOUT Wyscout id ───────────────────
        no_wyscout_seasons = [s for s in _SEASON_FILES if s not in _WYSCOUT_SEASONS]

        for season in sorted(no_wyscout_seasons):
            csv_path = _CACHE_DIR / _SEASON_FILES.get(season, "")
            if not csv_path.exists():
                continue

            rows = _read_csv_rows(csv_path)
            for row in rows:
                name = row.get("Player", "")
                if not name:
                    continue

                fingerprint = {
                    "birth_country": row.get("Birth country", ""),
                    "foot": row.get("Foot", ""),
                    "height": row.get("Height", ""),
                }

                # Try to recover historical Wyscout ID by name
                if name in name_to_wyscout:
                    player_id = name_to_wyscout[name]
                    id_type = "wyscout_recovered"
                else:
                    player_id = _generate_slug(
                        name,
                        fingerprint["birth_country"],
                        fingerprint["foot"],
                        fingerprint["height"],
                    )
                    id_type = "generated"

                if player_id not in by_id:
                    by_id[player_id] = {
                        "canonical_name": name,
                        "id_type": id_type,
                        "seasons": [],
                        "fingerprint": fingerprint,
                    }
                if season not in by_id[player_id]["seasons"]:
                    by_id[player_id]["seasons"].append(season)

                by_name[name] = player_id

        # ── Persist ─────────────────────────────────────────────────────
        self._index = {
            "_meta": {
                "built_at": datetime.now(timezone.utc).isoformat(),
                "total_players": len(by_id),
                "wyscout_confirmed": sum(1 for v in by_id.values() if v["id_type"] == "wyscout"),
                "wyscout_recovered": sum(1 for v in by_id.values() if v["id_type"] == "wyscout_recovered"),
                "generated_slugs": sum(1 for v in by_id.values() if v["id_type"] == "generated"),
            },
            "by_id": by_id,
            "by_name": by_name,
        }

        _INDEX_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = str(_INDEX_FILE) + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self._index, f, indent=2, ensure_ascii=False)
        os.replace(tmp, _INDEX_FILE)

        meta = self._index["_meta"]
        logger.info(
            f"Player index built: {meta['total_players']} players — "
            f"wyscout={meta['wyscout_confirmed']}, "
            f"recovered={meta['wyscout_recovered']}, "
            f"generated={meta['generated_slugs']}"
        )
        self._loaded = True
        return True

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load(self):
        """Loads the index from disk."""
        try:
            with open(_INDEX_FILE, encoding="utf-8") as f:
                self._index = json.load(f)
            self._loaded = True
            logger.debug(f"Player index loaded ({self._index['_meta'].get('total_players', '?')} players).")
        except Exception as e:
            logger.error(f"Failed to load player index: {e}")

    def _ensure_loaded(self):
        if not self._loaded:
            if _INDEX_FILE.exists():
                self._load()
            else:
                logger.warning("Player index not found. Call PlayerIndex.build() first.")


# Module-level singleton
_player_index = PlayerIndex()


def get_player_index() -> PlayerIndex:
    """Returns the module-level PlayerIndex singleton."""
    return _player_index
