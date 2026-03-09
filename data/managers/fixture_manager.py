# ABOUTME: Manager for HKFA fixtures — ICS extraction, team normalization, TheSportsDB enrichment.
# ABOUTME: Exposes get_next_fixture(team) with 24h in-memory cache. Follows ETL Manager pattern.

import os
import re
import logging
import requests
from datetime import datetime, timezone, timedelta
from typing import Optional
from pathlib import Path

from data.extractors.ics_extractor import ICSExtractor, ICSFetchError
from utils.cache_manager import get_cache

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

CACHE_KEY = "fixture_manager_all_fixtures"
CACHE_TTL = 86400  # 24 hours

HKT = timezone(timedelta(hours=8))

ASSETS_LOGOS_DIR = Path(__file__).parent.parent.parent / "assets" / "team_logos"

THESPORTSDB_TEAMS_URL = "https://www.thesportsdb.com/api/v1/json/3/lookup_all_teams.php?id=4825"

# Mapping: Traditional Chinese (ICS) → English (used in processed data + TheSportsDB)
TEAM_MAPPING: dict[str, str] = {
    "傑志": "Kitchee",
    "東方龍獅": "Eastern",
    "東方": "Eastern",
    "理文": "Lee Man",
    "標準流浪": "Rangers",
    "流浪": "Rangers",
    "冠忠南區": "Southern District",
    "南區": "Southern District",
    "大埔": "Tai Po",
    "和富大埔": "Tai Po",
    "九龍城": "Kowloon City",
    "均業北區": "North District",
    "北區": "North District",
    "港會": "Hong Kong Football Club",
    "香港足球會": "Hong Kong Football Club",
    "深水埗": "Sham Shui Po",
    "香港U23": "HK U23",
    "晉峰": "Resources Capital",
    "天水圍飛馬": "Pegasus",
    "飛馬": "Pegasus",
    "晨曦": "Morning Star",
    "南華": "South China",
    "公和屠場": "Kwong Wah",
    "公和": "Kwong Wah",
    "理工大學體育會": "Hong Kong Polytechnic University",
    "理工大學": "Hong Kong Polytechnic University",
    "嘉里": "Kerry",
    "西貢太陽神": "Sun God",
}

# Keywords identifying adult-male HKFA competitions (Chinese and English variants)
ALLOWED_COMPETITION_KEYWORDS = {
    # Hong Kong Premier League / Super League
    "超聯", "超級聯賽", "premier league", "super league",
    # FA Cup
    "足總盃", "fa cup",
    # Senior Shield
    "銀牌", "高級組銀牌", "senior shield",
    # League Cup
    "聯賽盃", "league cup",
    # Elite Cup
    "菁英盃", "elite cup",
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _team_slug(name: str) -> str:
    """Convert team name to a filesystem-safe slug for logo filenames."""
    return re.sub(r"[^a-z0-9]", "_", name.lower()).strip("_")


def _is_allowed_competition(competition: str) -> bool:
    """Return True if the competition name matches any allowed HKFA adult-male competition."""
    comp_lower = competition.lower()
    return any(kw in comp_lower for kw in ALLOWED_COMPETITION_KEYWORDS)


def _parse_summary(summary: str) -> tuple[str, str, str] | None:
    """
    Extract (home, away, competition) from an ICS SUMMARY string.

    Expected format: '<Home> vs <Away> - <Competition>'
    Returns None if the format doesn't match or competition is not allowed.
    """
    if not summary:
        return None

    # Split on ' - ' to separate match from competition
    parts = summary.split(" - ", 1)
    if len(parts) != 2:
        return None

    match_part, competition = parts[0].strip(), parts[1].strip()

    if not _is_allowed_competition(competition):
        logger.debug(f"Skipping non-allowed competition: '{competition}'")
        return None

    # Split home vs away — handle 'vs', 'VS', 'Vs'
    vs_match = re.split(r"\s+[Vv][Ss]\s+", match_part, maxsplit=1)
    if len(vs_match) != 2:
        return None

    home_zh, away_zh = vs_match[0].strip(), vs_match[1].strip()
    return home_zh, away_zh, competition


def _normalize_team(chinese_name: str) -> str:
    """Look up English name from TEAM_MAPPING; log a warning and return raw name on miss."""
    english = TEAM_MAPPING.get(chinese_name)
    if not english:
        logger.warning(
            f"Team '{chinese_name}' not found in TEAM_MAPPING — using raw name as fallback."
        )
        return chinese_name
    return english


# ── TheSportsDB asset helpers ─────────────────────────────────────────────────

_thesportsdb_team_cache: dict[str, dict] = {}  # local runtime cache for API response


def _load_thesportsdb_teams() -> dict[str, dict]:
    """Fetch all HKPL teams from TheSportsDB once; returns {team_name_lower: team_obj}."""
    global _thesportsdb_team_cache
    if _thesportsdb_team_cache:
        return _thesportsdb_team_cache

    try:
        resp = requests.get(THESPORTSDB_TEAMS_URL, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        teams = data.get("teams") or []
        _thesportsdb_team_cache = {
            t["strTeam"].lower(): t for t in teams if t.get("strTeam")
        }
        logger.info(f"Loaded {len(_thesportsdb_team_cache)} teams from TheSportsDB.")
    except Exception as e:
        logger.warning(f"TheSportsDB fetch failed: {e}")

    return _thesportsdb_team_cache


def _get_logo_local_path(team_name: str) -> Path:
    """Return the local asset path for a team logo (may not exist yet)."""
    return ASSETS_LOGOS_DIR / f"{_team_slug(team_name)}.png"


def _download_logo(team_name: str, url: str) -> Optional[str]:
    """Download a team logo to assets/team_logos/<slug>.png. Returns local web path or None."""
    local_path = _get_logo_local_path(team_name)
    if local_path.exists():
        return f"/assets/team_logos/{local_path.name}"

    try:
        ASSETS_LOGOS_DIR.mkdir(parents=True, exist_ok=True)
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        local_path.write_bytes(resp.content)
        logger.info(f"Downloaded logo for '{team_name}' → {local_path.name}")
        return f"/assets/team_logos/{local_path.name}"
    except Exception as e:
        logger.warning(f"Failed to download logo for '{team_name}': {e}")
        return None


def _resolve_logo(team_name: str) -> Optional[str]:
    """Return the local web path for a team logo, downloading it from TheSportsDB if needed."""
    local_path = _get_logo_local_path(team_name)
    if local_path.exists():
        return f"/assets/team_logos/{local_path.name}"

    teams = _load_thesportsdb_teams()
    team_data = teams.get(team_name.lower())
    if not team_data:
        # Try partial match
        for key, val in teams.items():
            if team_name.lower() in key or key in team_name.lower():
                team_data = val
                break

    if team_data and team_data.get("strTeamBadge"):
        return _download_logo(team_name, team_data["strTeamBadge"])

    return None


def _resolve_stadium(home_team: str) -> Optional[str]:
    """Return stadium name (English) for a team from TheSportsDB."""
    teams = _load_thesportsdb_teams()
    team_data = teams.get(home_team.lower())
    if team_data:
        return team_data.get("strStadium") or None
    return None


def _extract_streaming_url(description: Optional[str]) -> Optional[str]:
    """Extract first YouTube or Facebook Live URL from ICS DESCRIPTION field."""
    if not description:
        return None
    url_pattern = re.compile(
        r"https?://(?:www\.)?(?:youtube\.com|youtu\.be|facebook\.com|fb\.com)\S+"
    )
    match = url_pattern.search(description)
    return match.group(0) if match else None


# ── FixtureManager ────────────────────────────────────────────────────────────

class FixtureManager:
    """
    Orchestrates HKFA ICS extraction, team normalization, and TheSportsDB enrichment.
    Exposes get_fixtures() (cached 24h) and get_next_fixture(team).
    """

    def __init__(self):
        self._extractor = ICSExtractor()
        self._cache = get_cache()

    def get_fixtures(self) -> list[dict]:
        """
        Return all upcoming enriched fixtures for adult-male HKFA competitions.
        Result is cached for 24h using the project's AdvancedCacheManager.
        """
        cached = self._cache.get(CACHE_KEY, default=None)
        if cached is not None:
            logger.debug("Fixtures served from cache.")
            return cached

        fixtures = self._fetch_and_build()
        self._cache.set(CACHE_KEY, fixtures, ttl_seconds=CACHE_TTL)
        return fixtures

    def get_next_fixture(self, team: str) -> Optional[dict]:
        """
        Return the soonest upcoming fixture for the given team (English name).
        Searches both home and away. Returns None if no upcoming fixture found.
        """
        if not team:
            return None

        now_utc = datetime.now(timezone.utc)
        team_lower = team.lower()

        upcoming = [
            f for f in self.get_fixtures()
            if (
                f.get("home_team", "").lower() == team_lower
                or f.get("away_team", "").lower() == team_lower
            )
            and f.get("kickoff_utc") is not None
            and f["kickoff_utc"] > now_utc
        ]

        if not upcoming:
            return None

        return min(upcoming, key=lambda f: f["kickoff_utc"])

    # ── Private ──────────────────────────────────────────────────────────────

    def _fetch_and_build(self) -> list[dict]:
        """Fetch ICS, parse, normalize, enrich, and return fixture list."""
        try:
            raw_events = self._extractor.fetch()
        except ICSFetchError as e:
            logger.error(f"ICS fetch failed: {e}")
            return []

        fixtures = []
        for event in raw_events:
            fixture = self._build_fixture(event)
            if fixture:
                fixtures.append(fixture)

        logger.info(f"Built {len(fixtures)} fixtures from {len(raw_events)} ICS events.")
        return fixtures

    def _build_fixture(self, event: dict) -> Optional[dict]:
        """Parse and enrich a single ICS event. Returns None if event should be excluded."""
        summary = event.get("summary") or ""
        parsed = _parse_summary(summary)
        if parsed is None:
            return None

        home_zh, away_zh, competition = parsed
        home_en = _normalize_team(home_zh)
        away_en = _normalize_team(away_zh)

        # Convert dtstart to timezone-aware UTC datetime
        dtstart = event.get("dtstart")
        if dtstart is None:
            return None
        if not hasattr(dtstart, "tzinfo") or dtstart.tzinfo is None:
            dtstart = dtstart.replace(tzinfo=timezone.utc)
        kickoff_utc = dtstart.astimezone(timezone.utc)
        kickoff_hkt = kickoff_utc.astimezone(HKT)

        stadium_raw = event.get("location")
        # TheSportsDB has stadium in English; use raw ICS location as fallback
        stadium_en = _resolve_stadium(home_en) or (stadium_raw or "").strip() or None

        return {
            "uid": event.get("uid"),
            "home_team": home_en,
            "away_team": away_en,
            "competition": competition,
            "kickoff_utc": kickoff_utc,
            "kickoff_hkt": kickoff_hkt,
            "kickoff_display": kickoff_hkt.strftime("%-d %b %Y, %H:%M HKT"),
            "stadium": stadium_en,
            "home_logo_url": _resolve_logo(home_en),
            "away_logo_url": _resolve_logo(away_en),
            "streaming_url": _extract_streaming_url(event.get("description")),
        }


# ── Singleton accessor ─────────────────────────────────────────────────────────

_fixture_manager_instance: Optional[FixtureManager] = None


def get_fixture_manager() -> FixtureManager:
    """Return the module-level FixtureManager singleton."""
    global _fixture_manager_instance
    if _fixture_manager_instance is None:
        _fixture_manager_instance = FixtureManager()
    return _fixture_manager_instance
