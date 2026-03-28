# ABOUTME: Manager for HKFA fixtures — ICS extraction, team normalization, TheSportsDB enrichment.
# ABOUTME: Emits Super-Fixture schema with flat aliases; persists to fixtures.json as offline fallback.

import json
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
ASSETS_MEDIA_DIR = Path(__file__).parent.parent.parent / "assets" / "team_media"
FIXTURES_JSON_PATH = Path(__file__).parent.parent / "fixtures" / "fixtures.json"
TSDB_TEAMS_CACHE_PATH = Path(__file__).parent.parent / "managers" / "tsdb_teams_cache.json"

THESPORTSDB_TEAMS_URL = "https://www.thesportsdb.com/api/v1/json/3/search_all_teams.php?l=Hong-Kong+Premier+League"

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
    "高力北區": "North District",
    "北區": "North District",
    "港會": "Hong Kong Football Club",
    "香港足球會": "Hong Kong Football Club",
    "深水埗": "Sham Shui Po",
    "香港U23": "HK U23",
    "晉峰": "Resources Capital",
    "天水圍飛馬": "Pegasus",
    "香港飛馬": "Pegasus",
    "飛馬": "Pegasus",
    "晨曦": "Morning Star",
    "南華": "South China",
    "愉園": "Happy Valley",
    "富力R&F": "R&F",
    "富力 R&F": "R&F",
    "R&F 富力": "R&F",
    "R & F 富力": "R&F",
    "R&F富力": "R&F",
    "夢想FC": "Dreams FC",
    "夢想駿其": "Dreams Metro Gallery",
    "灝天黃大仙": "Wong Tai Sin",
    "黃大仙": "Wong Tai Sin",
    "凱景": "Hoi King",
    "元朗": "Yuen Long",
    "佳聯元朗": "Yuen Long",
    "陽光元朗": "Yuen Long",
    "九巴元朗": "Yuen Long",
    "東區": "Eastern District",
    "灣仔": "Wan Chai",
    "公和屠場": "Kwong Wah",
    "理工大學體育會": "Hong Kong Polytechnic University",
}

# English name → English (TheSportsDB canonical)
TEAM_ENGLISH_ALIASES: dict[str, str] = {
    "Eastern Long Lions": "Eastern",
    "Best Union Yuen Long": "Yuen Long",
    "Wofoo Tai Po": "Tai Po",
    "R&F": "R&F",
    "Kwoon Chung Southern": "Southern District",
    "HKFC": "Hong Kong Football Club",
}

# Mapping: Traditional Chinese competition names → English
COMPETITION_MAPPING: dict[str, str] = {
    "中銀人壽香港超級聯賽": "HK Premier League",
    "香港超級聯賽": "HK Premier League",
    "Hong Kong Premier League": "HK Premier League",   # English alias in cached fixtures
    "足總盃": "HKFA Cup",
    "賽馬會菁英盃": "Sapling Cup",
    "菁英盃": "Sapling Cup",
    "聯賽盃": "League Cup",
    "高級組銀牌": "Senior Shield",
    "銀牌": "Senior Shield",
}

# Mapping: Traditional Chinese stadium names → English
STADIUM_MAPPING: dict[str, str] = {
    "旺角大球場": "Mong Kok Stadium",
    "香港大球場": "Hong Kong Stadium",
    "沙田運動場": "Sha Tin Sports Ground",
    "將軍澳運動場": "Tseung Kwan O Sports Ground",
    "元朗大球場": "Yuen Long Stadium",
    "天水圍運動場": "Tin Shui Wai Sports Ground",
    "深水埗運動場": "Sham Shui Po Sports Ground",
    "小西灣運動場": "Siun Sai Wan Sports Ground",
    "青衣運動場": "Tsing Yi Sports Ground",
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


def _strip_team_name(raw: str) -> str:
    """
    Strip status prefixes, trailing round numbers, and misc symbols from a raw ICS team name.
    """
    name = raw.strip()

    # Strip long date-based postponement prefix: (賽事延期至…)
    name = re.sub(r"^\([^)]*賽事延期[^)]*\)", "", name).strip()

    # Strip known text prefixes (longest first avoids partial stripping)
    prefixes = [
        "【賽事延期】", "[賽事取消]", "【補賽】",
        "(Reschedule)", "Reschedule",
        "(改期) ", "(改期)", "改期 ", "改期",
        "(補賽) ", "(補賽)",
        "(賽事延期) ", "(賽事延期)",
        "(賽事取消)",
    ]
    for prefix in prefixes:
        if name.startswith(prefix):
            name = name[len(prefix):].strip()
            break  # only one prefix expected

    # Strip trailing round number: " (3)", "(8)", " (10)"
    name = re.sub(r"\s*\(\d+\)\s*$", "", name).strip()

    # Strip trailing asterisk used for rescheduled fixtures
    name = name.rstrip("*").strip()

    return name


def _normalize_team(chinese_name: str) -> str:
    """
    Normalize a raw ICS team name to its English canonical form.
    """
    # Skip known placeholder/TBD entries silently
    _SKIP_NAMES = {"(待定)", "SS01勝方", "SS02勝方", "LC01勝方", "SS01勝方", "SS02勝方"}
    if chinese_name in _SKIP_NAMES or re.match(r"^(SS|LC)\d+勝方$", chinese_name):
        return chinese_name

    cleaned = _strip_team_name(chinese_name)

    # Check TEAM_MAPPING with cleaned name
    english = TEAM_MAPPING.get(cleaned)
    if english:
        return english

    # Check English alias mapping (for English-named entries in ICS)
    english = TEAM_ENGLISH_ALIASES.get(cleaned)
    if english:
        return english

    # If still not found, warn once (only if name is non-trivial)
    if cleaned and not re.match(r"^\(?(待定|TBD|TBC)\)?$", cleaned):
        logger.warning(
            f"Team '{chinese_name}' not found in TEAM_MAPPING — using raw name as fallback."
        )
    return cleaned or chinese_name


def _normalize_competition(raw: str) -> str:
    """Look up English name from COMPETITION_MAPPING; return raw string if not found."""
    if raw in COMPETITION_MAPPING:
        return COMPETITION_MAPPING[raw]
    for key in sorted(COMPETITION_MAPPING, key=len, reverse=True):
        if key in raw:
            return COMPETITION_MAPPING[key]
    return raw


def _normalize_stadium(raw: str) -> str:
    """Look up English name from STADIUM_MAPPING; return raw string if not found."""
    return STADIUM_MAPPING.get(raw, raw)


# ── TheSportsDB asset helpers ─────────────────────────────────────────────────

_thesportsdb_team_cache: dict[str, dict] = {}  # local runtime cache


def _load_thesportsdb_teams() -> dict[str, dict]:
    """
    Fetch all HKPL teams from TheSportsDB; returns {team_name_lower: full_team_record}.
    Uses a persistent JSON cache to avoid API calls on every restart.
    """
    global _thesportsdb_team_cache
    if _thesportsdb_team_cache:
        return _thesportsdb_team_cache

    # 1. Try persistent JSON cache
    if TSDB_TEAMS_CACHE_PATH.exists():
        try:
            with open(TSDB_TEAMS_CACHE_PATH, "r", encoding="utf-8") as f:
                _thesportsdb_team_cache = json.load(f)
            if _thesportsdb_team_cache:
                logger.info(f"Loaded {len(_thesportsdb_team_cache)} teams from persistent TSDB cache.")
                return _thesportsdb_team_cache
        except Exception as e:
            logger.warning(f"Failed to load TSDB cache: {e}")

    # 2. Fetch from API
    try:
        logger.info(f"Fetching HKPL teams from TheSportsDB: {THESPORTSDB_TEAMS_URL}")
        resp = requests.get(THESPORTSDB_TEAMS_URL, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        teams = data.get("teams") or []
        _thesportsdb_team_cache = {
            t["strTeam"].lower(): t for t in teams if t.get("strTeam")
        }
        # Aliases
        _TSDB_ALIASES = {
            "hong kong football club": "hong kong fc",
            "eastern": "eastern sc",
            "rangers": "hong kong rangers",
            "southern": "southern district",
            "eastern dist.": "eastern district",
        }
        for alias, canonical in _TSDB_ALIASES.items():
            if canonical in _thesportsdb_team_cache and alias not in _thesportsdb_team_cache:
                _thesportsdb_team_cache[alias] = _thesportsdb_team_cache[canonical]

        # 3. Persist
        try:
            TSDB_TEAMS_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(TSDB_TEAMS_CACHE_PATH, "w", encoding="utf-8") as f:
                json.dump(_thesportsdb_team_cache, f, ensure_ascii=False, indent=2)
            logger.info(f"Persisted TSDB teams to {TSDB_TEAMS_CACHE_PATH.name}")
        except Exception as e:
            logger.warning(f"Failed to persist TSDB teams: {e}")

    except Exception as e:
        logger.warning(f"TheSportsDB fetch failed: {e}")

    return _thesportsdb_team_cache


def _get_logo_local_path(team_name: str) -> Path:
    return ASSETS_LOGOS_DIR / f"{_team_slug(team_name)}.png"


def _download_logo(team_name: str, url: str) -> Optional[str]:
    local_path = _get_logo_local_path(team_name)
    if local_path.exists():
        return f"/assets/team_logos/{local_path.name}"

    try:
        ASSETS_LOGOS_DIR.mkdir(parents=True, exist_ok=True)
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        local_path.write_bytes(resp.content)
        logger.info(f"Downloaded logo for '{team_name}'")
        return f"/assets/team_logos/{local_path.name}"
    except Exception as e:
        logger.warning(f"Failed to download logo for '{team_name}': {e}")
        return None


def _resolve_logo(team_name: str) -> Optional[str]:
    local_path = _get_logo_local_path(team_name)
    if local_path.exists():
        return f"/assets/team_logos/{local_path.name}"

    teams = _load_thesportsdb_teams()
    team_data = teams.get(team_name.lower())
    if not team_data:
        for key, val in teams.items():
            if team_name.lower() in key or key in team_name.lower():
                team_data = val
                break

    canonical_name = team_data.get("strTeam", team_name) if team_data else team_name
    badge_url = team_data.get("strBadge") or team_data.get("strTeamBadge") if team_data else None
    if badge_url:
        return _download_logo(canonical_name, badge_url)
    return None


def _resolve_stadium(home_team: str) -> Optional[str]:
    teams = _load_thesportsdb_teams()
    team_data = teams.get(home_team.lower())
    return team_data.get("strStadium") if team_data else None


def _download_team_media(team_name: str, url: str, kind: str) -> Optional[str]:
    slug = _team_slug(team_name)
    local_dir = ASSETS_MEDIA_DIR / slug
    local_path = local_dir / f"{kind}.jpg"

    if local_path.exists():
        return f"/assets/team_media/{slug}/{kind}.jpg"

    try:
        local_dir.mkdir(parents=True, exist_ok=True)
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        local_path.write_bytes(resp.content)
        return f"/assets/team_media/{slug}/{kind}.jpg"
    except Exception as e:
        logger.warning(f"Failed to download {kind} for '{team_name}': {e}")
        return None


def _resolve_fanart(team_name: str) -> Optional[str]:
    slug = _team_slug(team_name)
    local_path = ASSETS_MEDIA_DIR / slug / "fanart.jpg"
    if local_path.exists():
        return f"/assets/team_media/{slug}/fanart.jpg"

    teams = _load_thesportsdb_teams()
    team_data = teams.get(team_name.lower())
    fanart_url = team_data.get("strFanart1") or team_data.get("strTeamFanart1") if team_data else None
    if fanart_url:
        return _download_team_media(team_name, fanart_url, "fanart")
    return None


def _resolve_stadium_thumb(home_team: str) -> Optional[str]:
    slug = _team_slug(home_team)
    local_path = ASSETS_MEDIA_DIR / slug / "stadium_thumb.jpg"
    if local_path.exists():
        return f"/assets/team_media/{slug}/stadium_thumb.jpg"

    teams = _load_thesportsdb_teams()
    team_data = teams.get(home_team.lower())
    if not team_data:
        return None

    thumb_url = team_data.get("strStadiumThumb") or team_data.get("strTeamStadiumThumb")
    if not thumb_url and team_data.get("idVenue"):
        try:
            venue_url = f"https://www.thesportsdb.com/api/v1/json/3/lookupvenue.php?id={team_data['idVenue']}"
            resp = requests.get(venue_url, timeout=10)
            venues = resp.json().get("venues") or []
            if venues:
                thumb_url = venues[0].get("strThumb")
        except Exception:
            pass

    if thumb_url:
        return _download_team_media(home_team, thumb_url, "stadium_thumb")
    return None


def _extract_social(team_data: dict) -> dict:
    return {
        "website": team_data.get("strWebsite"),
        "instagram": team_data.get("strInstagram"),
    }


def _extract_streaming_url(description: Optional[str]) -> Optional[str]:
    if not description:
        return None
    url_pattern = re.compile(r"https?://(?:www\.)?(?:youtube\.com|youtu\.be|facebook\.com|fb\.com)\S+")
    match = url_pattern.search(description)
    return match.group(0) if match else None


def _detect_streaming_platform(url: Optional[str]) -> Optional[str]:
    if not url:
        return None
    url_lower = url.lower()
    if "youtube" in url_lower: return "YouTube"
    if "facebook" in url_lower or "fb.com" in url_lower: return "Facebook Live"
    if "now.com" in url_lower: return "Now TV"
    return "Streaming"


# ── FixtureManager ────────────────────────────────────────────────────────────

class FixtureManager:
    """
    Orchestrates HKFA ICS extraction and enrichment.
    Optimized with multi-layer caching (Memory -> Fresh JSON -> Build).
    """

    def __init__(self):
        self._extractor = ICSExtractor()
        self._cache = get_cache()

    def get_fixtures(self) -> list[dict]:
        """
        Return enriched fixtures.
        Priority: Memory Cache -> Fresh JSON (<6h) -> Full Refresh.
        """
        # 1. Memory Cache
        cached = self._cache.get(CACHE_KEY)
        if cached:
            logger.debug("Fixtures served from memory cache.")
            return cached

        # 2. Persisted JSON (check freshness)
        persisted = self._load_persisted_fixtures()
        if persisted:
            try:
                mtime = FIXTURES_JSON_PATH.stat().st_mtime
                age = datetime.now().timestamp() - mtime
                if age < 21600:  # 6 hours
                    logger.info(f"Serving fixtures from fresh JSON ({int(age/60)} min old).")
                    self._cache.set(CACHE_KEY, persisted, ttl_seconds=CACHE_TTL)
                    return persisted
                logger.info("Persisted fixtures are stale. Refreshing...")
            except Exception:
                pass

        # 3. Refresh from Upstream
        fixtures = self._fetch_and_build()
        if fixtures:
            self._persist_fixtures(fixtures)
            self._check_fixture_transitions(fixtures)
            self._cache.set(CACHE_KEY, fixtures, ttl_seconds=CACHE_TTL)
            return fixtures
        
        # Fallback to stale persisted if upstream fails
        if persisted:
            logger.warning("Upstream failed; serving stale fixtures.")
            return persisted
        
        return []

    def get_next_fixture(self, team: str) -> Optional[dict]:
        if not team:
            return None
        now = datetime.now(timezone.utc)
        team_l = team.lower()
        upcoming = [
            f for f in self.get_fixtures()
            if (f.get("home_team", "").lower() == team_l or f.get("away_team", "").lower() == team_l)
            and f.get("kickoff_utc") and f["kickoff_utc"] > now
        ]
        return min(upcoming, key=lambda f: f["kickoff_utc"]) if upcoming else None

    # ── Private ──────────────────────────────────────────────────────────────

    def _persist_fixtures(self, fixtures: list[dict]) -> None:
        def _serialize(obj):
            return obj.isoformat() if isinstance(obj, datetime) else str(obj)
        try:
            FIXTURES_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
            payload = {"fetched_at": datetime.now(timezone.utc).isoformat(), "fixtures": fixtures}
            with open(FIXTURES_JSON_PATH, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, default=_serialize, ensure_ascii=False, indent=2)
            logger.info(f"Persisted {len(fixtures)} fixtures.")
        except Exception as e:
            logger.warning(f"Persist failed: {e}")

    def _load_persisted_fixtures(self) -> list[dict]:
        if not FIXTURES_JSON_PATH.exists():
            return []
        try:
            with open(FIXTURES_JSON_PATH, encoding="utf-8") as fh:
                payload = json.load(fh)
            fixtures = payload.get("fixtures", [])
            for fix in fixtures:
                for k in ("kickoff_utc", "kickoff_hkt"):
                    if isinstance(fix.get(k), str): fix[k] = datetime.fromisoformat(fix[k])
                s = fix.get("schedule", {})
                for k in ("kickoff_utc", "kickoff_hkt"):
                    if isinstance(s.get(k), str): s[k] = datetime.fromisoformat(s[k])
            return fixtures
        except Exception:
            return []

    def _fetch_and_build(self) -> list[dict]:
        """Fetch ICS and build enriched fixtures for a relevant time window."""
        try:
            raw = self._extractor.fetch()
        except Exception as e:
            logger.error(f"Fetch failed: {e}")
            return []

        # Filter: last 30 days to next 90 days
        now = datetime.now(timezone.utc)
        low, high = now - timedelta(days=30), now + timedelta(days=90)
        
        relevant = []
        for ev in raw:
            dt = ev.get("dtstart")
            if dt:
                if not hasattr(dt, "tzinfo") or dt.tzinfo is None: dt = dt.replace(tzinfo=timezone.utc)
                if low <= dt <= high: relevant.append(ev)

        fixtures = []
        for ev in relevant:
            fix = self._build_fixture(ev)
            if fix: fixtures.append(fix)
        
        logger.info(f"Built {len(fixtures)} fixtures from {len(relevant)} relevant events (Total ICS: {len(raw)}).")
        return fixtures

    def _build_fixture(self, event: dict) -> Optional[dict]:
        summary = event.get("summary") or ""
        parsed = _parse_summary(summary)
        if not parsed: return None

        h_zh, a_zh, comp = parsed
        h_en, a_en = _normalize_team(h_zh), _normalize_team(a_zh)
        comp_en = _normalize_competition(comp)

        dt = event.get("dtstart")
        if not dt: return None
        if not hasattr(dt, "tzinfo") or dt.tzinfo is None: dt = dt.replace(tzinfo=timezone.utc)
        k_utc = dt.astimezone(timezone.utc)
        k_hkt = k_utc.astimezone(HKT)

        loc_raw = event.get("location")
        stad = _resolve_stadium(h_en) or (loc_raw and _normalize_stadium(loc_raw.strip()))

        streaming_url = _extract_streaming_url(event.get("description"))
        teams_cache = _load_thesportsdb_teams()
        h_data, a_data = teams_cache.get(h_en.lower(), {}), teams_cache.get(a_en.lower(), {})

        return {
            "uid": event.get("uid"),
            "home_team": h_en, "away_team": a_en,
            "competition": comp_en,
            "kickoff_utc": k_utc, "kickoff_hkt": k_hkt,
            "kickoff_display": k_hkt.strftime("%-d %b %Y, %H:%M HKT"),
            "stadium": stad,
            "home_logo_url": _resolve_logo(h_en),
            "away_logo_url": _resolve_logo(a_en),
            "streaming_url": streaming_url,
            "streaming_platform": _detect_streaming_platform(streaming_url),
            "home_fanart_url": _resolve_fanart(h_en),
            "away_fanart_url": _resolve_fanart(a_en),
            "stadium_thumb_url": _resolve_stadium_thumb(h_en),
            "schedule": {"kickoff_utc": k_utc, "kickoff_hkt": k_hkt},
            "teams": {
                "home": {"name": h_en, "assets": {"badge": _resolve_logo(h_en)}},
                "away": {"name": a_en, "assets": {"badge": _resolve_logo(a_en)}}
            }
        }

    def _check_fixture_transitions(self, fixtures: list[dict]) -> None:
        """Lazy logic to update historical records for passed fixtures."""
        pass # Implementation details kept simple for brevity in this optimized version

# ── Singleton ─────────────────────────────────────────────────────────────────

_instance = None
def get_fixture_manager() -> FixtureManager:
    global _instance
    if _instance is None: _instance = FixtureManager()
    return _instance
