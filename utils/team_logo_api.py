# ABOUTME: Resolves and downloads team logos from TheSportsDB with deterministic local asset slugs.
# ABOUTME: Used as the API-first source before Transfermarkt fallback for club logo acquisition.

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import requests


TSDB_BASE_URL = "https://www.thesportsdb.com/api/v1/json/3"
TSDB_CACHE_PATH = Path("data/managers/tsdb_teams_cache.json")
TEAM_LOGOS_DIR = Path("assets/team_logos")

TEAM_ALIASES: dict[str, list[str]] = {
    "resources_capital": ["Resources Capital FC", "Resources Capital", "RCFC"],
    "resources_capital_fc": ["Resources Capital FC", "Resources Capital", "RCFC"],
    "happy_valley": ["Happy Valley", "Happy Valley AA"],
    "sham_shui_po": ["Sham Shui Po", "Sham Shui Po AA"],
    "yuen_long": ["Yuen Long", "Yuen Long FC", "Yueng Long"],
    "4_25_sc": ["April 25 SC", "4.25 SC", "April 25"],
    "athletic_220": ["Athletic 220"],
    "bali_united": ["Bali United", "Bali United FC"],
    "chiangrai_utd": ["Chiangrai United", "Singha Chiangrai United"],
    "flc_thanh_hoa": ["Thanh Hoa", "FLC Thanh Hoa", "Dong A Thanh Hoa"],
    "gamba_osaka": ["Gamba Osaka"],
    "gz_evergrande": ["Guangzhou Evergrande", "Guangzhou FC"],
    "hang_yuan_fc": ["Taipei Hang Yuen", "Hang Yuan", "Hang Yuen FC", "Hang Yuen"],
    "taipei_hang_yuen": ["Taipei Hang Yuen", "Hang Yuan", "Hang Yuen FC", "Hang Yuen"],
    "kaya_fc": ["Kaya–Iloilo", "Kaya-Iloilo", "Kaya FC-Iloilo", "Kaya FC", "Kaya"],
    "nam_dinh_fc": ["Nam Dinh", "Thep Xanh Nam Dinh", "Nam Dinh FC"],
    "ratchaburi_fc": ["Ratchaburi FC", "Ratchaburi", "Ratchaburi Mitr Phol"],
    "ryomyong_sc": ["Ryomyong SC", "Ryomyong"],
    "sanf_hiroshima": ["Sanfrecce Hiroshima"],
    "suwon_bluewings": ["Suwon Samsung Bluewings", "Suwon Bluewings"],
    "sydney_fc": ["Sydney FC"],
    "tainan_city": ["Tainan City", "Tainan City FC"],
    "tampines_rovers": ["Tampines Rovers", "Tampines Rovers FC"],
    "urawa_reds": ["Urawa Red Diamonds", "Urawa Reds"],
    "vissel_kobe": ["Vissel Kobe"],
    "cahn_fc": ["CAHN FC", "CAHN", "Công An Hà Nội", "Cong An Ha Noi"],
    "hk_u23": ["HK U23", "Hong Kong U23"],
    "macarthur": ["Macarthur", "Macarthur FC"],
    "bangkok_united": ["Bangkok United", "Bangkok Utd.", "Bangkok Utd"],
    "beijing_guoan": ["Beijing Guoan", "BJ Guoan", "Beijing Guoan FC"],
    "kawasaki_frontale": ["Kawasaki Frontale", "Kawasaki Front."],
    "r_f": ["R and F (HK) F.C.", "R&F", "R and F", "R&F (HK) F.C."],
    "pegasus": ["Pegasus HK FC", "Hong Kong Pegasus", "Pegasus FC", "Pegasus"],
}

OUTPUT_SLUGS: dict[str, str] = {
    "resources_capital_fc": "resources_capital",
    "rcfc": "resources_capital",
    "eastern_dist": "eastern_district",
    "eastern_dt": "eastern_district",
    "hk_u23": "hk_u23",
    "hong_kong_u23": "hk_u23",
    "north_district": "north_dt",
    "pegasus_hk_fc": "pegasus",
    "chiangrai_united": "chiangrai_utd",
    "thanh_hoa": "flc_thanh_hoa",
    "dong_a_thanh_hoa": "flc_thanh_hoa",
    "guangzhou_evergrande": "gz_evergrande",
    "nam_dinh": "nam_dinh_fc",
    "southern": "southern_district",
    "sanfrecce_hiroshima": "sanf_hiroshima",
    "suwon_samsung_bluewings": "suwon_bluewings",
    "urawa_red_diamonds": "urawa_reds",
    "taipei_hang_yuen": "hang_yuan_fc",
    "hang_yuan": "hang_yuan_fc",
    "kaya_iloilo": "kaya_fc",
    "kaya_iloilo_fc": "kaya_fc",
    "c_ng_an_h_n_i": "cahn_fc",
    "cong_an_ha_noi": "cahn_fc",
    "cahn": "cahn_fc",
    "r_and_f_hk_f_c": "r_f",
}


def slugify_team_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value or "").strip().lower()).strip("_")


def clean_team_name(value: str | None) -> str:
    cleaned = re.sub(r"\(\d+\.\)", "", str(value or "")).strip()
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _load_cache() -> dict[str, dict[str, Any]]:
    if not TSDB_CACHE_PATH.exists():
        return {}
    raw = json.loads(TSDB_CACHE_PATH.read_text())
    if isinstance(raw, dict):
        return {str(k).lower(): v for k, v in raw.items() if isinstance(v, dict)}
    return {}


def _collect_candidates(team_name: str) -> list[str]:
    cleaned_name = clean_team_name(team_name)
    slug = slugify_team_name(cleaned_name)
    candidates = [cleaned_name]
    candidates.extend(TEAM_ALIASES.get(slug, []))
    if slug == "rcfc":
        candidates.extend(TEAM_ALIASES["resources_capital"])
    return list(dict.fromkeys([c for c in candidates if c]))


def _pick_image_url(team_data: dict[str, Any]) -> str | None:
    return team_data.get("strBadge") or team_data.get("strTeamBadge") or team_data.get("strLogo")


def _search_cache(cache: dict[str, dict[str, Any]], team_name: str) -> dict[str, Any] | None:
    for candidate in _collect_candidates(team_name):
        lowered = candidate.lower()
        if lowered in cache:
            return cache[lowered]
        for value in cache.values():
            haystack = " ".join(
                str(value.get(field) or "") for field in ("strTeam", "strTeamAlternate", "strLeague")
            ).lower()
            if lowered in haystack:
                return value
    return None


def _search_api(team_name: str) -> dict[str, Any] | None:
    for candidate in _collect_candidates(team_name):
        try:
            response = requests.get(f"{TSDB_BASE_URL}/searchteams.php", params={"t": candidate}, timeout=15)
            response.raise_for_status()
            teams = response.json().get("teams") or []
        except Exception:
            return None
        if not teams:
            continue
        candidate_l = candidate.lower()
        for team in teams:
            if str(team.get("strTeam") or "").lower() == candidate_l:
                return team
        return teams[0]
    return None


def resolve_output_slug(team_name: str) -> str:
    cleaned_name = clean_team_name(team_name)
    return OUTPUT_SLUGS.get(slugify_team_name(cleaned_name), slugify_team_name(cleaned_name))


def fetch_team_logo_from_api(team_name: str, overwrite: bool = False) -> str | None:
    cache = _load_cache()
    team_data = _search_cache(cache, team_name) or _search_api(team_name)
    if not team_data:
        return None
    image_url = _pick_image_url(team_data)
    if not image_url:
        return None

    TEAM_LOGOS_DIR.mkdir(parents=True, exist_ok=True)
    output_slug = resolve_output_slug(team_name)
    output_path = TEAM_LOGOS_DIR / f"{output_slug}.png"
    if output_path.exists() and not overwrite:
        return f"/assets/team_logos/{output_path.name}"

    try:
        response = requests.get(image_url, timeout=20)
        response.raise_for_status()
        output_path.write_bytes(response.content)
        return f"/assets/team_logos/{output_path.name}"
    except Exception:
        return None
