# ABOUTME: Central team identity and branding registry for canonical HK football team lookups.
# ABOUTME: Resolves aliases, shared color palettes, and asset keys for cards and media helpers.

from typing import Any

_DEFAULT_COLORS = {
    "badge": ["#1a1a2e", "#16213e", "#ffffff"],
    "kit_home": ["#1a1a2e"],
    "kit_away": ["#16213e"],
    "colour1": "#1a1a2e",
    "colour2": "#16213e",
}

_TEAM_BRANDING = {
    "kitchee": {
        "aliases": {"kitchee", "kitchee sc"},
        "asset_key": "kitchee",
        "colors": {
            "badge": ["#14236b", "#e7b330", "#848cb2"],
            "kit_home": ["#091e47", "#db5d96", "#0a468c"],
            "kit_away": ["#dfdeeb", "#eb4380"],
            "colour1": "#14236b",
            "colour2": "#e7b330",
        },
    },
    "eastern": {
        "aliases": {"eastern", "eastern aa", "eastern sc"},
        "asset_key": "eastern",
        "colors": {
            "badge": ["#224283", "#d3242b", "#e6c8cd"],
            "kit_home": ["#1e407e"],
            "kit_away": ["#d0d0d5"],
            "colour1": "#224283",
            "colour2": "#d3242b",
        },
    },
    "eastern district": {
        "aliases": {"eastern district", "eastern dist.", "eastern_dist.", "eastern_district"},
        "asset_key": "eastern_district",
        "colors": {
            "badge": ["#e1e3e5", "#0d1c35", "#646d78"],
            "kit_home": ["#16233a", "#d5dbe0", "#387287"],
            "kit_away": ["#e9363a", "#f7e4e7", "#e68184"],
            "colour1": "#0d1c35",
            "colour2": "#e1e3e5",
        },
    },
    "lee man": {
        "aliases": {"lee man", "lee man fc", "lee_man"},
        "asset_key": "lee_man",
        "colors": {
            "badge": ["#e7b844", "#1b2180", "#e30513"],
            "kit_home": ["#edcc55"],
            "kit_away": ["#1f2837", "#edcc55"],
            "colour1": "#e7b844",
            "colour2": "#1b2180",
        },
    },
    "southern district": {
        "aliases": {"southern", "southern district", "southern_district"},
        "asset_key": "southern_district",
        "colors": {
            "badge": ["#b91329", "#064276", "#e0cbcd"],
            "kit_home": ["#d81d3b", "#e9d6da", "#632c38"],
            "kit_away": ["#2b3854", "#b8c7e7"],
            "colour1": "#b91329",
            "colour2": "#064276",
        },
    },
    "hk rangers": {
        "aliases": {"rangers", "hk rangers", "bc rangers", "bc_rangers"},
        "asset_key": "rangers",
        "colors": {
            "badge": ["#a7e1fa", "#05a6e8", "#5ac5f1"],
            "kit_home": ["#2179c0", "#c6cedc", "#04266e"],
            "kit_away": ["#b55384", "#d4c4d8", "#2f2142"],
            "colour1": "#05a6e8",
            "colour2": "#a7e1fa",
        },
    },
    "tai po": {
        "aliases": {"tai po", "tai_po"},
        "asset_key": "tai_po",
        "colors": {
            "badge": ["#134726", "#b4bc8e", "#60856e"],
            "kit_home": ["#124b62", "#c0c2c4", "#2191a4"],
            "kit_away": ["#75446b", "#e0d4d4"],
            "colour1": "#134726",
            "colour2": "#b4bc8e",
        },
    },
    "north district": {
        "aliases": {"north district", "north dt.", "north dt", "north_dt", "north_district"},
        "asset_key": "north_dt",
        "colors": {
            "badge": ["#272860", "#cb2220", "#dcc9cb"],
            "kit_home": ["#8f131d", "#251216", "#dfcfd6"],
            "kit_away": ["#ac8616", "#202021", "#c1c7b3"],
            "colour1": "#272860",
            "colour2": "#cb2220",
        },
    },
    "hong kong football club": {
        "aliases": {"hong kong football club", "hkfc", "hong_kong_football_club"},
        "asset_key": "hong_kong_football_club",
        "colors": {
            "badge": ["#d1dee6", "#6182ae", "#06448b"],
            "kit_home": ["#343246"],
            "kit_away": ["#ededec"],
            "colour1": "#06448b",
            "colour2": "#6182ae",
        },
    },
    "kowloon city": {
        "aliases": {"kowloon city", "kowloon_city"},
        "asset_key": "kowloon_city",
        "colors": {
            "badge": ["#c0940c"],
            "kit_home": ["#74171d", "#d8c9b4", "#1f1817"],
            "kit_away": ["#b5ae94", "#151411", "#e7e5dd"],
            "colour1": "#c0940c",
            "colour2": "#1f1817",
        },
    },
    "resources capital": {
        "aliases": {"resources capital", "resources capital fc", "rcfc", "resources_capital"},
        "asset_key": "rcfc",
        "colors": {
            "badge": ["#1f4d37", "#e8f2a5", "#ffffff"],
            "kit_home": ["#1f4d37"],
            "kit_away": ["#f6f6f2"],
            "colour1": "#1f4d37",
            "colour2": "#e8f2a5",
        },
    },
    "happy valley": {
        "aliases": {"happy valley", "happy valley aa", "happy_valley"},
        "asset_key": "happy_valley",
        "colors": dict(_DEFAULT_COLORS),
    },
    "sham shui po": {
        "aliases": {"sham shui po", "sham shui po aa", "sham_shui_po"},
        "asset_key": "sham_shui_po",
        "colors": dict(_DEFAULT_COLORS),
    },
    "yuen long": {
        "aliases": {"yuen long", "yuen long fc", "yueng long", "yuen_long"},
        "asset_key": "yuen_long",
        "colors": dict(_DEFAULT_COLORS),
    },
}

_ALIAS_TO_CANONICAL = {
    alias: canonical
    for canonical, branding in _TEAM_BRANDING.items()
    for alias in branding["aliases"]
}


def canonicalize_team_name(name: str | None) -> str:
    """Resolve known aliases to a canonical team key."""
    if not name:
        return "unknown"

    key = str(name).strip().lower()
    return _ALIAS_TO_CANONICAL.get(key, key)


def get_team_branding(name: str | None) -> dict[str, Any]:
    """Return canonical identity, colors, and asset metadata for a team."""
    canonical = canonicalize_team_name(name)
    branding = _TEAM_BRANDING.get(canonical)

    if not branding:
        return {
            "canonical_name": canonical,
            "asset_key": canonical.replace(" ", "_"),
            "colors": dict(_DEFAULT_COLORS),
        }

    return {
        "canonical_name": canonical,
        "asset_key": branding["asset_key"],
        "colors": dict(branding["colors"]),
    }


def get_team_colors(name: str | None) -> dict[str, Any]:
    """Return the enriched color structure used across cards and portal UI."""
    return get_team_branding(name)["colors"]


def get_team_asset_key(name: str | None) -> str:
    """Return the asset key/prefix used by team media helpers."""
    return get_team_branding(name)["asset_key"]
