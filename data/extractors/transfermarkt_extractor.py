# ABOUTME: Extractor for Transfermarkt data (team injuries, player match history, and player photos).
# ABOUTME: Provides get_match_history(), get_player_photo_url(), fetch_and_store_player_photo() with blob storage in DB.

import random
import requests
import cloudscraper
from bs4 import BeautifulSoup, Tag
import pandas as pd
import time
import re
import difflib
import urllib.parse
from datetime import datetime, timedelta
import logging
from typing import Dict, List, Optional, Tuple, Union, Sequence
from bs4.element import PageElement
from pathlib import Path
import json
from requests.cookies import create_cookie

from utils.proxy_manager import ProxyManager
from utils.common import get_current_season

# Known TM spellings for HKPL team IDs — used to boost club_score when our
# internal name doesn't match TM's exact spelling.
_TEAM_TM_ALIASES: dict[str, list[str]] = {
    "eastern":           ["Eastern AA", "Eastern SC", "Eastern"],
    "eastern_district":  ["Eastern District", "Eastern District AA", "Eastern Dt."],
    "north_district":    ["North District", "North District AA", "North Dt."],
    "southern_district": ["Southern District", "Southern District AA"],
    "hong_kong_fc":      ["Hong Kong FC", "HKFC"],
    "kowloon_city":      ["Kowloon City", "Kowloon City FC"],
    "lee_man":           ["Lee Man", "Lee Man FC"],
    "tai_po":            ["Tai Po", "Tai Po FC", "Wofoo Tai Po"],
    "kitchee":           ["Kitchee", "Kitchee SC"],
    "bc_rangers":        ["BC Rangers", "BC Rangers FC"],
    "sham_shui_po":      ["Sham Shui Po", "Sham Shui Po AA"],
    "yuen_long":         ["Yuen Long", "Yuen Long FC"],
    "wong_tai_sin":      ["Wong Tai Sin", "Wong Tai Sin SA"],
    "resources_capital": ["Resources Capital", "Resources Capital FC", "RCFC"],
}

# TM club IDs for HKPL teams — used to fetch squad pages directly when
# name search fails to surface the player (common for low-profile players).
_TEAM_TM_CLUB_IDS: dict[str, int] = {
    "tai_po":            34329,   # Tai Po
    "kitchee":           15979,   # Kitchee
    "eastern":           15974,   # Eastern SC
    "eastern_district":  48928,   # Eastern District
    "north_district":    62534,   # North District
    "southern_district": 36670,   # Southern District
    "bc_rangers":        15976,   # Hong Kong Rangers (BC Rangers)
    "kowloon_city":      36930,   # Kowloon City
    "lee_man":           61336,   # Lee Man
    "hong_kong_fc":      14413,   # Hong Kong Football Club
    "sham_shui_po":      34332,   # Sham Shui Po
    "yuen_long":         34397,   # Yuen Long
    "resources_capital": 36935,   # Resources Capital
}

_USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
]

class TransfermarktExtractor:
    """
    Extractor avanzado de Transfermarkt para rendimiento detallado de jugadores.
    """

    def __init__(self, cache_dir: str = "data/cache", proxy_manager: Optional[ProxyManager] = None):
        self.base_url = "https://www.transfermarkt.com"
        self.headers = {
            'User-Agent': random.choice(_USER_AGENTS),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Upgrade-Insecure-Requests': '1',
        }
        self.delay_min = 10.0
        self.delay_max = 20.0
        self.request_count = 0
        self.last_request_time = 0
        self.proxy_manager = proxy_manager or ProxyManager()
        self.cache_dir = Path(cache_dir)
        self.historical_records_dir = Path("data/historical_records")
        self.competition_logos_dir = Path("assets/competition_logos")
        self.logger = logging.getLogger(__name__)
        self.last_http_status: Optional[int] = None
        self.last_block_type: Optional[str] = None
        self.last_block_reason: Optional[str] = None
        self.last_result_source: Optional[str] = None
        self.last_cache_fresh: bool = False
        self.session = cloudscraper.create_scraper(
            browser={"browser": "chrome", "platform": "darwin", "mobile": False}
        )
        self.session.headers.update(self.headers)

        # Whitelist ampliada: Todo lo que juegue un equipo de HK
        self.ALLOWED_COMPETITIONS = {
            "Hong Kong Premier League", "Hong Kong FA Cup", "Hong Kong Sapling Cup",
            "Hong Kong Sapling Cup ('15-'25)", "Hong Kong Senior Challenge Shield",
            "Hong Kong Community Cup", "HKPL", "HKFA Cup", "Senior Shield", "Sapling Cup",
            "菁英盃", "足總盃", "銀牌", "香港超級聯賽", "Play-off", "Champions League",
            "AFC Cup", "ACL Elite", "AFC Champions League Two", "Quali",
            "Copa de la AFC", "Clasificación", "AFC Champions League", "ACL"
        }
    def _wait_rate_limit(self):
        self.request_count += 1
        # Every 10 requests, take a longer break to look human.
        if self.request_count % 10 == 0:
            pause = random.uniform(20, 35)
            self.logger.debug("Rate limit long pause: %.1fs after %d requests", pause, self.request_count)
            time.sleep(pause)
        else:
            delay = random.uniform(self.delay_min, self.delay_max)
            elapsed = time.time() - self.last_request_time
            remaining = delay - elapsed
            if remaining > 0:
                time.sleep(remaining)
        # Rotate User-Agent every 5 requests.
        if self.request_count % 5 == 0:
            self.session.headers.update({'User-Agent': random.choice(_USER_AGENTS)})
        self.last_request_time = time.time()
    
    def _make_request(self, url: str) -> Optional[BeautifulSoup]:
        proxy_url = self.proxy_manager.get_proxy() if self.proxy_manager.has_proxies else None
        proxies = self.proxy_manager.as_requests_dict(proxy_url) if proxy_url else None
        try:
            self._wait_rate_limit()
            self.logger.info("Scraping: %s%s", url, f" [proxy]" if proxy_url else "")
            self.last_block_type = None
            self.last_block_reason = None
            self.last_result_source = "network"
            self.last_cache_fresh = False
            response = self.session.get(url, timeout=15, proxies=proxies)
            self.last_http_status = response.status_code
            self.last_request_time = time.time()
            protection_reason = self._detect_protection_page(response.text)
            if protection_reason:
                self.last_block_type = "AWS_WAF_HUMAN_VERIFICATION"
                self.last_block_reason = protection_reason
                self.logger.warning("Transfermarkt protection page detected for %s: %s", url, protection_reason)
                if proxy_url:
                    self.proxy_manager.mark_failure(proxy_url)
                return None
            response.raise_for_status()
            if proxy_url:
                self.proxy_manager.mark_success(proxy_url)
            return BeautifulSoup(response.content, 'html.parser')
        except requests.HTTPError as e:
            self.last_http_status = e.response.status_code if e.response is not None else None
            self.logger.error("Error en %s: %s", url, e)
            if proxy_url:
                self.proxy_manager.mark_failure(proxy_url)
            return None
        except Exception as e:
            self.last_http_status = None
            self.logger.error("Error en %s: %s", url, e)
            if proxy_url:
                self.proxy_manager.mark_failure(proxy_url)
            return None

    def _detect_protection_page(self, html: str) -> Optional[str]:
        text = (html or "").lower()
        if not text:
            return None
        
        # AWS WAF suele poner estos textos en el <title> o en encabezados h1/h2 muy específicos
        # Evitamos falsos positivos buscando combinaciones más estrictas
        if "human verification" in text and "awswaf" in text and "show details" in text:
            return "Human Verification (AWS WAF challenge)"
        
        if "captcha" in text and "bot" in text and "verification" in text and len(text) < 5000:
            # Las páginas de captcha suelen ser cortas (< 5KB). Una página real pesa > 100KB.
            return "Captcha / bot challenge"
            
        return None

    def load_cookie_jar(self, cookie_items: Sequence[Dict]) -> None:
        if not cookie_items:
            return
        for item in cookie_items:
            name = item.get("name")
            value = item.get("value")
            if not name or value is None:
                continue
            domain = item.get("domain") or ".transfermarkt.com"
            path = item.get("path") or "/"
            secure = bool(item.get("secure", True))
            cookie = create_cookie(name=name, value=value, domain=domain, path=path, secure=secure)
            self.session.cookies.set_cookie(cookie)

    def get_match_history(self, player_id: str, season_id: str) -> List[Dict]:
        """
        Obtiene el historial de partidos filtrando por equipo de HK o competición de HK.
        Usa cache persistente para evitar scraping redundante (TTL diario para temporadas activas).
        """
        season_key, tm_season_id = self._season_key(season_id)
        
        # 1. Intentar cargar desde cache local
        records = self._read_historical_records(player_id)
        is_completed = self._is_season_completed(season_key)
        
        if season_key in records.get("seasons", {}):
            last_updated_str = records.get("last_updated", "")
            if last_updated_str:
                try:
                    # Soportar tanto formato ISO date como datetime
                    last_updated = datetime.fromisoformat(last_updated_str).date()
                    
                    # Si la temporada ya terminó, o si se actualizó HOY, usar cache
                    if is_completed or last_updated == datetime.now().date():
                        self.last_result_source = "cache"
                        self.last_cache_fresh = True
                        self.last_http_status = 200
                        self.last_block_type = None
                        self.last_block_reason = None
                        self.logger.info(f"✓ Usando cache de Transfermarkt para {player_id} ({season_key}) - Actualizado: {last_updated}")
                        return records["seasons"][season_key].get("matches", [])
                except Exception as e:
                    self.logger.debug(f"Error parseando timestamp de cache: {e}")

        # 2. Scraping detallado (vista ampliada plus/1) si no hay cache válido
        url = f"{self.base_url}/x/leistungsdatendetails/spieler/{player_id}/saison/{tm_season_id}/plus/1"
        soup = self._make_request(url)
        if not soup:
            # Fallback a cache aunque sea viejo si falla la red
            return records.get("seasons", {}).get(season_key, {}).get("matches", []) if records else []
        
        result = self._parse_detailed_performance(soup)
        
        # 3. Persistir en registros históricos
        records.setdefault("seasons", {})[season_key] = result
        records["last_updated"] = datetime.now().isoformat()
        self._write_historical_records(player_id, records)
            
        return result.get("matches", [])

    def _download_competition_logo(self, comp_name: str, img_url: str) -> Optional[str]:
        """Download competition logo from Transfermarkt CDN. Returns local web path or None."""
        slug = re.sub(r"[^a-z0-9]", "_", comp_name.lower()).strip("_")
        self.competition_logos_dir.mkdir(parents=True, exist_ok=True)
        local_path = self.competition_logos_dir / f"{slug}.png"
        if local_path.exists():
            return f"/assets/competition_logos/{slug}.png"
        try:
            r = requests.get(img_url, headers=self.headers, timeout=10)
            r.raise_for_status()
            local_path.write_bytes(r.content)
            self.logger.info(f"Downloaded competition logo: {comp_name} → {local_path.name}")
            return f"/assets/competition_logos/{slug}.png"
        except Exception as e:
            self.logger.warning(f"Failed to download logo for '{comp_name}': {e}")
            return None

    def _parse_detailed_performance(self, soup: BeautifulSoup) -> Dict:
        matches = []
        summary = {"goals": 0, "assists": 0, "yellow_cards": 0, "red_cards": 0, "minutes_played": 0, "total_matches": 0, "own_goals": 0}

        # En la vista detallada, los partidos están en 'boxes' por competición
        boxes = soup.find_all("div", {"class": "box"})
        for box in boxes:
            header = box.find(["h2", "div"], {"class": ["content-box-headline", "table-header"]})
            if not header: continue

            comp_name = header.get_text(strip=True)
            # Filtro: ¿Es una competición de HK o internacional asiática?
            if not any(c.lower() in comp_name.lower() for c in self.ALLOWED_COMPETITIONS):
                continue

            # Extract and download competition logo from header image
            comp_logo_url = None
            logo_img = header.find("img")
            if logo_img:
                img_src = logo_img.get("src") or logo_img.get("data-src")
                if img_src:
                    comp_logo_url = self._download_competition_logo(comp_name, img_src)

            table = box.find("table")
            if not table: continue

            rows = table.find_all("tr")
            for row in rows:
                cells = row.find_all("td")
                # Las filas de partido en vista 'plus/1' tienen muchas celdas
                if len(cells) < 8: continue

                try:
                    # Celda 0: Jornada / Ronda
                    # Celda 1: Fecha
                    date_txt = cells[1].get_text(strip=True)
                    if not date_txt or len(date_txt) < 5: continue # Cabeceras o filas vacías

                    # Identificar estado (Jugado vs No Jugado)
                    status_text = ""
                    is_played = True

                    potential_status = row.get_text()
                    if "No convocado" in potential_status:
                        status_text = "No convocado"
                        is_played = False
                    elif "En el banquillo" in potential_status:
                        status_text = "En el banquillo"
                        is_played = False
                    elif "Lesión" in potential_status or "Lesionado" in potential_status:
                        status_text = "Lesionado"
                        is_played = False
                    elif "Sancionado" in potential_status:
                        status_text = "Sancionado"
                        is_played = False

                    home = cells[3].get_text(strip=True)
                    away = cells[5].get_text(strip=True)
                    res = cells[6].get_text(strip=True)

                    match_entry = {
                        "date": date_txt,
                        "opponent": f"{home} vs {away}",
                        "competition": comp_name,
                        "competition_logo": comp_logo_url,
                        "result": res,
                        "status": status_text if not is_played else "Jugado",
                        "goals": 0, "assists": 0, "yellow_cards": 0, "red_cards": 0, "minutes_played": 0,
                        "own_goals": 0, "subbed_in": None, "subbed_out": None
                    }

                    if is_played:
                        # Vista 'plus/1' indices (0-based):
                        # 7: Posición, 8: Goles, 9: Asistencias, 10: Propia puerta,
                        # 11: TA, 12: TR Doble, 13: TR, 14: Entró, 15: Salió, 16: Minutos
                        if len(cells) > 7: match_entry["position"] = cells[7].get_text(strip=True)
                        if len(cells) > 8: match_entry["goals"] = self._parse_number(cells[8].get_text(strip=True))
                        if len(cells) > 9: match_entry["assists"] = self._parse_number(cells[9].get_text(strip=True))
                        if len(cells) > 10: match_entry["own_goals"] = self._parse_number(cells[10].get_text(strip=True))
                        
                        if len(cells) > 11: match_entry["yellow_cards"] = 1 if cells[11].get_text(strip=True) else 0
                        if len(cells) > 13: 
                            match_entry["red_cards"] = 1 if (cells[12].get_text(strip=True) or cells[13].get_text(strip=True)) else 0
                        
                        if len(cells) > 14:
                            match_entry["subbed_in"] = self._parse_number(cells[14].get_text(strip=True).replace("'", "")) or None
                        if len(cells) > 15:
                            match_entry["subbed_out"] = self._parse_number(cells[15].get_text(strip=True).replace("'", "")) or None

                        # Minutos (última celda siempre es minutos en esta vista)
                        match_entry["minutes_played"] = self._parse_number(cells[-1].get_text(strip=True).replace("'", ""))
                        
                        # Actualizar sumario solo si jugó
                        summary["goals"] += match_entry["goals"]
                        summary["assists"] += match_entry["assists"]
                        summary["own_goals"] += match_entry["own_goals"]
                        summary["yellow_cards"] += match_entry["yellow_cards"]
                        summary["red_cards"] += match_entry["red_cards"]
                        summary["minutes_played"] += match_entry["minutes_played"]
                        summary["total_matches"] += 1

                    matches.append(match_entry)
                except: continue

        # Ordenar por fecha descendente
        try:
            matches.sort(key=lambda x: datetime.strptime(x["date"], "%d/%m/%Y") if '/' in x["date"] else x["date"], reverse=True)
        except: pass
        
        return {"matches": matches, "summary": summary}

    def _parse_number(self, txt: str) -> int:
        try:
            num = re.sub(r'[^\d]', '', txt)
            return int(num) if num else 0
        except: return 0

    def _is_season_completed(self, season_id: str) -> bool:
        try:
            start_year = int(season_id.split('-')[0])
            return datetime.now() > datetime(start_year + 1, 7, 31)
        except: return False

    def _read_historical_records(self, player_id: str) -> dict:
        record_file = self.historical_records_dir / f"{player_id}.json"
        if not record_file.exists(): return {}
        with open(record_file, "r", encoding="utf-8") as f: return json.load(f)

    def _write_historical_records(self, player_id: str, data: dict) -> None:
        self.historical_records_dir.mkdir(parents=True, exist_ok=True)
        with open(self.historical_records_dir / f"{player_id}.json", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _season_key(self, season_id: str) -> tuple:
        if '-' in season_id: return season_id, str(season_id.split('-')[0])
        else:
            s = int(season_id)
            return f"{s}-{str(s+1)[-2:]}", str(s)

    def get_player_photo_url(self, tm_player_id: str) -> Optional[str]:
        """
        Scrapes the profile photo URL for a player from Transfermarkt.
        Returns the image URL or None if not found.
        """
        url = f"{self.base_url}/player/profil/spieler/{tm_player_id}"
        soup = self._make_request(url)
        if soup is None:
            return None
        try:
            # 1. og:image meta tag — most reliable, layout-change-proof
            og = soup.select_one('meta[property="og:image"]')
            if og and og.get("content"):
                return og["content"]

            # 2. Fallback: any img whose src contains the portrait CDN path
            for img in soup.find_all("img"):
                src = img.get("src") or img.get("data-src") or ""
                if "portrait" in src and "transfermarkt" in src:
                    return src

            # 3. Legacy selector (kept in case TM reverts to old markup)
            img = soup.select_one(".data-header__profile-image img")
            if img:
                return img.get("src") or img.get("data-src")
        except Exception as e:
            self.logger.debug(f"get_player_photo_url error for {tm_player_id}: {e}")
        return None

    def get_player_full_profile(self, tm_player_id: str) -> Dict:
        """
        Scrapes a complete player profile from Transfermarkt in a single request.
        Returns a dictionary with keys: height, foot, birth_country, position, age, birth_date.
        """
        url = f"{self.base_url}/player/profil/spieler/{tm_player_id}"
        soup = self._make_request(url)
        if soup is None:
            return {}

        details = {
            "height": None,
            "foot": None,
            "birth_country": None,
            "position": None,
            "age": None,
            "birth_date": None
        }

        try:
            # Strategy A — og:description meta tag (layout-independent).
            # TM typically includes: "... | Position: Centre-Forward | ..."
            og_desc = soup.find("meta", property="og:description")
            if og_desc and og_desc.get("content"):
                desc = og_desc["content"]
                m = re.search(
                    r'(?:Posici[oó]n|Position)\s*[:\|]\s*([^|\n,]+)',
                    desc, re.IGNORECASE
                )
                if m:
                    details["position"] = m.group(1).strip()

            # Strategy B — info-table spans (classic TM layout, may still appear)
            if not details["position"]:
                for row in soup.select("span.info-table__content--label"):
                    label = row.get_text(strip=True).lower()
                    value_el = row.find_next_sibling("span", class_="info-table__content--bold")
                    if not value_el:
                        continue
                    value = value_el.get_text(strip=True)

                    if "altura" in label or "height" in label:
                        m = re.search(r"(\d)[,.](\d{2})", value)
                        if m:
                            details["height"] = int(m.group(1)) * 100 + int(m.group(2))
                    elif "pie" in label or "foot" in label:
                        details["foot"] = value.lower()
                    elif "nacionalidad" in label or "citizenship" in label:
                        img = value_el.find("img")
                        details["birth_country"] = img.get("title") if img and img.get("title") else value
                    elif "edad" in label or "age" in label:
                        m = re.search(r"(\d+)", value)
                        if m:
                            details["age"] = int(m.group(1))
                    elif "nacimiento" in label or "date of birth" in label:
                        details["birth_date"] = value
                    elif "posici" in label or "position" in label:
                        details["position"] = value

            # Strategy C — data-header label/value pairs (newer TM layout)
            if not details["position"]:
                _bad_sibling = re.compile(
                    r'\b(selecci[oó]n|exjugador|internac|goles|agente|altura|pie:|nacimiento|fecha)\b',
                    re.I,
                )
                for label_el in soup.find_all(
                    True,
                    class_=re.compile(r"data-header__(label|item)", re.I)
                ):
                    label_text = label_el.get_text(strip=True).lower()
                    if "posici" in label_text or "position" in label_text:
                        # Try extracting position directly from the label (e.g. "posición:centre-forward")
                        m_label = re.search(
                            r'm?posici[oó]n\s*:\s*'
                            r'([A-Za-záéíóúüñÁÉÍÓÚÜÑ][A-Za-záéíóúüñÁÉÍÓÚÜÑ\s\-]{1,30}?)'
                            r'(?=agente|altura|pie|nacimiento|ciudad|equipo|fecha|\s*$)',
                            label_text, re.IGNORECASE
                        )
                        if m_label:
                            details["position"] = m_label.group(1).strip().title()
                            break
                        # Fall back to next sibling, rejecting non-position values
                        nxt = label_el.find_next_sibling()
                        if nxt:
                            val = nxt.get_text(strip=True)
                            if not _bad_sibling.search(val) and ":" not in val:
                                details["position"] = val
                                break

            # Strategy D — search page text for "Posición: <value>" pattern.
            # The value must end before a newline, colon, pipe, or digit.
            # This avoids grabbing national-team or other adjacent fields.
            if not details["position"]:
                page_text = soup.get_text("\n")
                m = re.search(
                    r'(?:Posici[oó]n|Main\s+position|Position)\s*:\s*'
                    r'([A-Za-záéíóúüñÁÉÍÓÚÜÑ][A-Za-záéíóúüñÁÉÍÓÚÜÑ\s\-]{1,30}?)'
                    r'(?=\s*[\n\|\:\d]|$)',
                    page_text, re.IGNORECASE
                )
                if m:
                    val = m.group(1).strip()
                    # Reject if it looks like a section header or contains suspicious words
                    if val and not re.search(r'\b(selecci[oó]n|exjugador|internac|goles)\b', val, re.I):
                        details["position"] = val

            # Strategy E — table th/td fallback
            if not details["position"]:
                for th in soup.find_all(["th", "dt"]):
                    if re.search(r'posici[oó]n|position', th.get_text(), re.I):
                        sib = th.find_next_sibling(["td", "dd"])
                        if sib:
                            details["position"] = sib.get_text(strip=True)
                            break

        except Exception as e:
            self.logger.debug(f"get_player_full_profile error for tm_id={tm_player_id}: {e}")

        return details

    def get_player_main_position(self, tm_player_id: str) -> Optional[str]:
        """Legacy wrapper for backward compatibility."""
        profile = self.get_player_full_profile(tm_player_id)
        return profile.get("position")

    def get_player_injuries(self, tm_player_id: str) -> List[Dict]:
        """
        Scrapes the historical injuries list for a player from Transfermarkt.
        Returns a list of dictionaries with keys: season, injury_type, date_from, date_until, days, matches_missed.
        """
        url = f"{self.base_url}/x/verletzungen/spieler/{tm_player_id}"
        soup = self._make_request(url)
        if soup is None:
            return []

        injuries = []
        try:
            # The injuries table is typically in a div with class 'box'
            table = soup.select_one(".items") or soup.find("table")
            if not table:
                return []

            rows = table.find_all("tr", class_=["odd", "even"])
            for row in rows:
                cells = row.find_all("td")
                if len(cells) < 5:
                    continue

                # Indices (may vary slightly but usually):
                # 0: Season, 1: Injury, 2: From, 3: Until, 4: Days, 5: Games missed
                injury_entry = {
                    "season": cells[0].get_text(strip=True),
                    "injury_type": cells[1].get_text(strip=True),
                    "date_from": cells[2].get_text(strip=True),
                    "date_until": cells[3].get_text(strip=True),
                    "days": cells[4].get_text(strip=True),
                }
                if len(cells) > 5:
                    injury_entry["matches_missed"] = cells[5].get_text(strip=True)
                
                injuries.append(injury_entry)
        except Exception as e:
            self.logger.error(f"get_player_injuries error for tm_id={tm_player_id}: {e}")

        return injuries

    def get_team_injuries(self, tm_club_id: Union[str, int], season_id: Optional[str] = None) -> List[Dict]:
        """
        Scrapes current or historical injuries for a specific team with fuzzy column detection.
        """
        team_slug = "team"
        for k, v in _TEAM_TM_CLUB_IDS.items():
            if str(v) == str(tm_club_id):
                team_slug = k.replace("_", "-")
                break

        url = f"{self.base_url}/{team_slug}/sperrenundverletzungen/verein/{tm_club_id}/plus/1"
        if season_id:
            year = season_id.split("-")[0] if "-" in season_id else season_id
            url += f"?saison_id={year}"
            
        soup = self._make_request(url)
        if soup is None:
            return []

        team_injuries = []
        try:
            # Buscar todos los contenedores 'box' que tienen una tabla y un encabezado
            boxes = soup.find_all("div", class_="box")
            if not boxes:
                return []

            for box in boxes:
                # Verificar el encabezado de la caja para saber si es de lesiones
                header = box.find(["h2", "div"], class_=["table-header", "content-box-headline"])
                header_text = header.get_text(strip=True).lower() if header else ""
                
                # Solo procesar si el encabezado menciona lesiones (en inglés o alemán)
                # Ignoramos "suspensions", "sperren", "sanciones"
                if not any(word in header_text for word in ["injury", "verletzung", "lesion", "lesión"]):
                    continue
                
                table = box.find("table", class_="items")
                if not table:
                    continue

                rows = table.find_all("tr", class_=["odd", "even"])
                for row in rows:
                    cells = row.find_all("td")
                    if len(cells) < 5: continue

                    # --- INTELLIGENT COLUMN DETECTION ---
                    # Instead of fixed indices, we scan the cells for patterns
                    
                    player_data = {"name": None, "tm_id": None}
                    injury_type = None
                    dates = [] # Collect any DD/MM/YYYY strings
                    missed_matches = 0
                    days_out = 0

                    for i, cell in enumerate(cells):
                        txt = cell.get_text(strip=True)
                        
                        # 1. Look for Player Name & ID (usually the cell with table.inline-table)
                        if not player_data["name"] and cell.find("table", class_="inline-table"):
                            a_link = cell.find("a", href=re.compile(r"/spieler/"))
                            if a_link:
                                player_data["name"] = a_link.get_text(strip=True)
                                m = re.search(r"/spieler/(\d+)", a_link.get("href", ""))
                                if m: player_data["tm_id"] = m.group(1)

                        # 2. Look for Dates (format DD/MM/YYYY)
                        date_matches = re.findall(r'(\d{1,2}/\d{1,2}/\d{2,4})', txt)
                        if date_matches:
                            dates.extend(date_matches)
                        
                        # 3. Look for Missed Matches (cell with a link to fixtures)
                        if cell.find("a", href=re.compile(r"/spielplandatum/")):
                            missed_matches = self._parse_number(txt)
                            # FIX: In the provided HTML, 'Days' is the IMMEDIATE NEXT cell after 'Missed Matches'
                            if i + 1 < len(cells):
                                days_out = self._parse_number(cells[i+1].get_text(strip=True))
                        
                        # 4. If we haven't found injury_type yet, and it's a 'links' cell with text
                        if not injury_type and "links" in (cell.get("class") or []) and len(txt) > 3:
                            if not any(char.isdigit() for char in txt): # Injury text doesn't usually have digits
                                injury_type = txt

                    # Assign dates based on position (usually first is since, second is until)
                    date_from = dates[0] if len(dates) > 0 else None
                    date_until = dates[1] if len(dates) > 1 else None
                    
                    # Emergency fallback for days_out if it's still 0
                    if days_out == 0 and len(cells) > 6:
                        # Sometimes 'Days' is in cell index 6 or the one before 'rechts' (market value)
                        # We'll take the highest number in the last 3 cells
                        last_numeric_vals = [self._parse_number(c.get_text(strip=True)) for c in cells[-3:]]
                        if last_numeric_vals: days_out = max(last_numeric_vals)

                    if player_data["name"]:
                        injury_data = {
                            "player_name": player_data["name"],
                            "tm_id": player_data["tm_id"],
                            "injury_type": injury_type or "unknown injury",
                            "date_from": date_from,
                            "date_until": date_until,
                            "missed_matches": missed_matches,
                            "days_out": days_out,
                            "season": season_id or get_current_season()
                        }
                        team_injuries.append(injury_data)
                
            self.logger.info(f"Extracted {len(team_injuries)} injuries for team {tm_club_id}")
        except Exception as e:
            self.logger.error(f"get_team_injuries error for club_id={tm_club_id}: {e}")

        return team_injuries

    def extract_all_injuries(self, league_id: str = "HKL1", force_refresh: bool = False, historical: bool = False) -> List[Dict]:
        """
        Scrapes current (and optionally historical) injuries by iterating over HKPL teams.
        """
        all_injuries = []
        
        # Decide which seasons to scrape
        seasons_to_scrape = [get_current_season()]
        if historical:
            # We can expand this list to past years if needed
            seasons_to_scrape = ["2024-25", "2023-24", "2022-23", "2021-22", "2020-21", "2019-20", "2018-19"]

        for season in seasons_to_scrape:
            self.logger.info(f"--- Starting scraping for season: {season} ---")
            for team_key, tm_club_id in _TEAM_TM_CLUB_IDS.items():
                self.logger.info(f"Scraping injuries for: {team_key} ({season})")
                team_data = self.get_team_injuries(tm_club_id, season_id=season)
                for entry in team_data:
                    entry["team_key"] = team_key
                    all_injuries.append(entry)
                
                # VERY LONG DELAY to simulate human reading time (15-40 seconds)
                if len(_TEAM_TM_CLUB_IDS) > 1:
                    wait_time = random.uniform(15, 40)
                    self.logger.info(f"Human pause: {wait_time:.1f}s...")
                    time.sleep(wait_time)
                
        self.logger.info(f"Extracted {len(all_injuries)} total injuries from team-specific pages.")
        return all_injuries

    def _search_player_in_squad(
        self,
        name: str,
        tm_club_id: int,
        birth_year: Optional[int] = None,
    ) -> Optional[int]:
        """
        Fetches TM's squad page for a club and finds the player by name matching.
        Used as a last-resort fallback when name-only search buries the player
        behind higher-profile namesakes (common for HKPL players).
        Returns tm_id or None.
        """
        import unicodedata as _ud

        def _strip(s: str) -> str:
            return "".join(
                c for c in _ud.normalize("NFD", s.lower())
                if _ud.category(c) != "Mn"
            )

        url = f"{self.base_url}/x/kader/verein/{tm_club_id}"
        soup = self._make_request(url)
        if soup is None:
            return None

        name_stripped = _strip(name)
        # Build name alternatives (original order + reversed for East-Asian)
        tokens = name.lower().split()
        name_alts = [name.lower(), name_stripped]
        if len(tokens) >= 2:
            rev = " ".join(tokens[1:]) + " " + tokens[0]
            name_alts += [rev, _strip(rev)]

        # Detect abbreviated name pattern: "X. Surname" or "X. Middle Surname"
        # Extract (initial, surname) for special abbreviated matching
        _abbr_match = re.match(r"^([a-zA-Z])\.\s+(.+)$", name.strip())
        abbr_initial: Optional[str] = _abbr_match.group(1).lower() if _abbr_match else None
        abbr_surname: Optional[str] = _strip(_abbr_match.group(2)) if _abbr_match else None

        best_id: Optional[int] = None
        best_score = 0.0
        best_via_initial: Optional[int] = None  # unambiguous initial+surname match

        # Collect all squad members for initial-matching
        initial_candidates: list[tuple[int, str]] = []

        for a_tag in soup.find_all("a", href=re.compile(r"/profil/spieler/\d+")):
            href = a_tag.get("href", "")
            m = re.search(r"/spieler/(\d+)", href)
            if not m:
                continue
            tm_id = int(m.group(1))
            candidate_name = a_tag.get_text(strip=True)
            if not candidate_name:
                continue
            cand_stripped = _strip(candidate_name)
            score = max(
                difflib.SequenceMatcher(None, alt, cand_stripped).ratio()
                for alt in name_alts
            )
            if score > best_score:
                best_score = score
                best_id = tm_id

            # Build list for initial-match pass
            if abbr_initial:
                initial_candidates.append((tm_id, candidate_name))

        # Abbreviated name fallback: "X. Surname" → find TM players where
        # surname matches and first name starts with X (unambiguous → 1 hit only)
        if abbr_initial and abbr_surname and best_score < 0.80:
            surname_matches: list[tuple[int, str, float]] = []
            seen_ids: set[int] = set()
            for tid, cname in initial_candidates:
                if tid in seen_ids:
                    continue
                seen_ids.add(tid)
                parts = cname.split()
                if len(parts) < 2:
                    continue
                # TM names: either "Firstname Surname" or "Surname Firstname"
                # Try both orderings: surname = last token or first token
                cand_stripped = _strip(cname)
                cand_parts_stripped = [_strip(p) for p in parts]
                for i, possible_surname in enumerate(cand_parts_stripped):
                    if difflib.SequenceMatcher(None, abbr_surname, possible_surname).ratio() >= 0.85:
                        # Surname matches — check if any other part starts with abbr_initial
                        other_parts = cand_parts_stripped[:i] + cand_parts_stripped[i+1:]
                        if any(p.startswith(abbr_initial) for p in other_parts):
                            surn_score = difflib.SequenceMatcher(None, abbr_surname, possible_surname).ratio()
                            surname_matches.append((tid, cname, surn_score))
                            break

            if len(surname_matches) == 1:
                # Exactly one unambiguous candidate — accept it
                best_via_initial, cname_matched, surn_score = surname_matches[0]
                self.logger.info(
                    f"_search_player_in_squad: '{name}' → tm_id={best_via_initial} "
                    f"(initial+surname match: '{cname_matched}', surname_score={surn_score:.3f})"
                )
                return best_via_initial
            elif len(surname_matches) > 1:
                self.logger.debug(
                    f"_search_player_in_squad: '{name}' ambiguous initial+surname matches: "
                    + ", ".join(f"{tid}:{cn}" for tid, cn, _ in surname_matches)
                )

        if best_id and best_score >= 0.80:
            self.logger.info(
                f"_search_player_in_squad: '{name}' → tm_id={best_id} "
                f"(squad page club={tm_club_id}, name_score={best_score:.3f})"
            )
            return best_id

        self.logger.debug(
            f"_search_player_in_squad: no match for '{name}' in club={tm_club_id} "
            f"(best={best_score:.3f})"
        )
        return None

    def search_player_by_name(
        self,
        name: str,
        team: str = "",
        nationality: str = "",
        birth_year: Optional[int] = None,
        position: str = "",
        team_id: str = "",
    ) -> Optional[int]:
        """
        Searches Transfermarkt by player name and confirms the match using a
        composite confidence score built from up to 4 signals:

          name         (weight 0.40) — SequenceMatcher ratio on player name
          club/team    (weight 0.35) — best ratio across known TM aliases for the team
          nationality  (weight 0.15) — exact country substring match (0 or 1)
          birth_year   (weight 0.10) — exact year match (0 or 1)

        Only signals that can actually be extracted from TM's search results
        contribute to the score — missing signals are not penalised.
        Returns the tm_id (int) of the best candidate with score ≥ 0.65, or None.

        Multi-fallback strategy (stops as soon as a confident match is found):
          1. Search by full name (or last name if abbreviated "A. Smith")
          2. Search by accent-stripped name (handles "Adrián" → "Adrian")
          3. Search by reversed name order (handles "Chan Ka Ho" → "Ka Ho Chan")
          4. Search by first token of hyphenated name ("Ku Ja-Ryong" → "Ku")
        """
        CONFIDENCE_THRESHOLD = 0.65

        import unicodedata

        # Squad-page fast path: when the team is a known HKPL club, search its
        # TM squad page FIRST. This is the most reliable approach for low-profile
        # players who rank below the top search results in the general name search.
        if team_id and team_id in _TEAM_TM_CLUB_IDS:
            squad_result = self._search_player_in_squad(
                name, _TEAM_TM_CLUB_IDS[team_id], birth_year=birth_year
            )
            if squad_result:
                return squad_result
            self.logger.debug(
                f"search_player_by_name: squad-page fast path found no match for '{name}' "
                f"in {team_id} — continuing with name search."
            )

        # Resolve team aliases early — needed to build search attempts.
        # (Full alias list is also rebuilt below for scoring.)
        _team_hints: list[str] = []
        if team:
            _team_hints.append(team.strip())
        if team_id and team_id in _TEAM_TM_ALIASES:
            for _alias in _TEAM_TM_ALIASES[team_id]:
                if _alias.lower() not in [t.lower() for t in _team_hints]:
                    _team_hints.append(_alias)

        # Accent-stripped name (used in several attempts below).
        stripped = unicodedata.normalize("NFD", name)
        stripped = "".join(c for c in stripped if unicodedata.category(c) != "Mn")

        # Build the list of (search_term, is_abbrev) attempts to try in order.
        # Strategy: specific (name+team) searches come FIRST.
        # TM sorts results by market value, so a little-known HKPL player is buried
        # behind higher-profile namesakes when searching by name alone. The combined
        # query "Marcão Tai Po" typically surfaces the correct player immediately.
        search_attempts: list[tuple[str, bool]] = []

        # Attempts 1–2: name + team (most specific — run before name-only).
        for _th in _team_hints[:2]:
            _combined = f"{name} {_th}"
            if _combined not in [a[0] for a in search_attempts]:
                search_attempts.append((_combined, False))

        # Attempt 3: full name only (or last name if abbreviated "A. Smith")
        abbrev_match = re.match(r'^[A-Z]\.\s+(.+)$', name)
        if abbrev_match:
            search_attempts.append((abbrev_match.group(1), True))
        else:
            search_attempts.append((name, False))

        # Attempt 4: accent-stripped name (e.g. "Adrián" → "Adrian")
        if stripped != name:
            stripped_abbrev = re.match(r'^[A-Z]\.\s+(.+)$', stripped)
            if stripped_abbrev:
                search_attempts.append((stripped_abbrev.group(1), True))
            else:
                search_attempts.append((stripped, False))

        # Attempt 5: reversed token order for East-Asian names ("Chan Ka Ho" → "Ka Ho Chan")
        tokens = name.split()
        if len(tokens) >= 2:
            reversed_name = " ".join(tokens[1:]) + " " + tokens[0]
            if reversed_name not in [a[0] for a in search_attempts]:
                search_attempts.append((reversed_name, False))

        # Attempt 6: first token of hyphenated surname ("Ku Ja-Ryong" → "Ku")
        if "-" in name:
            first_token = name.split()[0]
            if len(first_token) > 2 and first_token not in [a[0] for a in search_attempts]:
                search_attempts.append((first_token, False))

        # Resolve team aliases: build a list of lowercase TM-known club names.
        team_aliases: list[str] = []
        if team_id and team_id in _TEAM_TM_ALIASES:
            team_aliases = [a.lower() for a in _TEAM_TM_ALIASES[team_id]]
        if team:
            team_aliases.insert(0, team.lower().strip())
        # Deduplicate while preserving order
        seen_aliases: set[str] = set()
        unique_aliases: list[str] = []
        for a in team_aliases:
            if a not in seen_aliases:
                seen_aliases.add(a)
                unique_aliases.append(a)
        team_aliases = unique_aliases

        nat_lower = nationality.lower().strip()

        for search_term, is_abbrev in search_attempts:
            encoded = urllib.parse.quote(search_term)
            url = f"{self.base_url}/schnellsuche/ergebnis/schnellsuche?query={encoded}"
            soup = self._make_request(url)
            if soup is None:
                return None

            # Handle TM redirect to a single player profile page
            og_url = soup.find("meta", property="og:url")
            if og_url and og_url.get("content"):
                m_redirect = re.search(r"/spieler/(\d+)", og_url["content"])
                if m_redirect:
                    tm_id = int(m_redirect.group(1))
                    self.logger.info(
                        f"search_player_by_name: '{name}' → tm_id={tm_id} "
                        f"(TM redirect, search='{search_term}')"
                    )
                    return tm_id

            # Pre-scan: build tm_id → nationality by correlating portrait imgs
            # (which embed tm_id in their URL) with the nearest subsequent
            # flaggenrahmen img. This works regardless of table nesting depth.
            tm_nat_map: dict[int, str] = {}
            _last_portrait_id: Optional[int] = None
            for _img in soup.find_all("img"):
                _src = _img.get("src", "") or _img.get("data-src", "")
                _m = re.search(r"/portrait/[^/]+/(\d+)-", _src)
                if _m:
                    _last_portrait_id = int(_m.group(1))
                elif "flaggenrahmen" in (_img.get("class") or []) and _last_portrait_id:
                    _title = _img.get("title", "") or _img.get("alt", "")
                    if _title and len(_title) > 1 and _last_portrait_id not in tm_nat_map:
                        tm_nat_map[_last_portrait_id] = _title
                        _last_portrait_id = None  # consumed

            # Each candidate: tm_id, player_name_text, club_text, nationality_text, birth_year_int
            #
            # TM search result HTML structure (as of 2025):
            #   <tr class="odd/even">                         ← OUTER row (all signal columns)
            #     <td>
            #       <table class="inline-table">             ← inner table
            #         <tr><td rowspan=2><img portrait/></td>
            #             <td class="hauptlink"><a /profil/spieler/ID>Name</a></td></tr>
            #         <tr><td><a /verein/ID>Club</a></td></tr>
            #       </table>
            #     </td>
            #     <td class="zentriert">CB</td>              ← position
            #     <td class="zentriert"><img tiny_wappen/></td> ← club logo
            #     <td class="zentriert">37</td>              ← AGE ← this is what we extract
            #     <td class="zentriert"><img flaggenrahmen/></td> ← nationality flag
            #     <td class="rechts hauptlink">-</td>        ← market value
            #     <td ...><a>Agent</a></td>                  ← agent
            #   </tr>
            #
            # We must walk up from the <a> link to the OUTER <tr> to get age and nationality.
            candidates: list[tuple] = []
            seen_ids: set[int] = set()

            for a_tag in soup.find_all("a", href=re.compile(r"/profil/spieler/\d+")):
                href = a_tag.get("href", "")
                m = re.search(r"/spieler/(\d+)", href)
                if not m:
                    continue
                tm_id = int(m.group(1))
                if tm_id in seen_ids:
                    continue
                seen_ids.add(tm_id)

                player_text = a_tag.get_text(strip=True)

                # Navigate to the outer <tr>: a_tag → inner tr → inline-table → outer td → outer tr
                inline_table = a_tag.find_parent("table", class_="inline-table")
                if inline_table:
                    outer_tr = inline_table.find_parent("td") and inline_table.find_parent("td").find_parent("tr")
                else:
                    outer_tr = a_tag.find_parent("tr")
                if not outer_tr:
                    continue

                # Club: prefer the text link from the inline-table (has full name).
                club_text = ""
                if inline_table:
                    club_link = inline_table.find("a", href=re.compile(r"/(verein|startseite|club)/"))
                    if club_link:
                        club_text = club_link.get_text(strip=True)
                if not club_text:
                    club_link = outer_tr.find("a", href=re.compile(r"/(verein|startseite|club)/"))
                    if club_link:
                        club_text = club_link.get_text(strip=True)

                # Nationality: flaggenrahmen img in the outer tr (or from pre-scan map).
                nat_text = tm_nat_map.get(tm_id, "")
                if not nat_text:
                    flag_img = outer_tr.find("img", class_="flaggenrahmen")
                    if flag_img:
                        nat_text = flag_img.get("title", "") or flag_img.get("alt", "")

                # Age → birth year: the outer tr has a plain-number <td class="zentriert">
                # containing the player's age (e.g. "37"). Convert to approximate birth year.
                cand_birth_year = None
                for td in outer_tr.find_all("td", class_="zentriert"):
                    td_text = td.get_text(strip=True)
                    # Age cell is a bare integer 14–50; skip cells that contain links or imgs
                    if td.find(["a", "img"]):
                        continue
                    age_m = re.fullmatch(r"([1-4]\d|50)", td_text)
                    if age_m:
                        cand_birth_year = datetime.now().year - int(age_m.group(1))
                        break

                candidates.append((tm_id, player_text, club_text, nat_text, cand_birth_year))

            if not candidates:
                self.logger.debug(f"search_player_by_name: no results for search='{search_term}'")
                continue

            name_lower = name.lower().strip()

            # Build alternative name forms for East-Asian names stored as "Surname Given"
            name_tokens = name_lower.split()
            name_alternatives = [name_lower]
            if len(name_tokens) >= 2:
                western = " ".join(name_tokens[1:]) + " " + name_tokens[0]
                western_hyphen = "-".join(name_tokens[1:]) + " " + name_tokens[0]
                name_alternatives += [western, western_hyphen]
            # Also include accent-stripped forms
            name_alternatives_stripped = [
                unicodedata.normalize("NFD", a)
                for a in name_alternatives
            ]
            name_alternatives_stripped = [
                "".join(c for c in a if unicodedata.category(c) != "Mn")
                for a in name_alternatives_stripped
            ]
            all_name_forms = list(dict.fromkeys(name_alternatives + name_alternatives_stripped))

            best_id: Optional[int] = None
            best_score = 0.0

            for tm_id, p_name, club, nat, by in candidates:
                p_name_lower = p_name.lower().replace("-", " ")
                name_score = max(
                    difflib.SequenceMatcher(None, alt, p_name_lower).ratio()
                    for alt in all_name_forms + [search_term.lower()]
                )
                # Abbreviated name: boost score if last name is a word-boundary match
                if is_abbrev:
                    last_name_lower = search_term.lower()
                    if re.search(r'\b' + re.escape(last_name_lower) + r'\b', p_name_lower):
                        name_score = max(name_score, 0.85)

                w_name = 0.40
                w_club = 0.35
                w_nat  = 0.15
                w_by   = 0.10

                active_w     = w_name
                active_score = w_name * name_score

                if team_aliases and club:
                    # Use the best-matching alias instead of raw team string
                    club_lower = club.lower()
                    club_score = max(
                        difflib.SequenceMatcher(None, alias, club_lower).ratio()
                        for alias in team_aliases
                    )
                    active_w     += w_club
                    active_score += w_club * club_score

                if nat_lower and nat:
                    nat_cand = nat.lower()
                    # Strip accents for comparison (handles España→espana, etc.)
                    def _strip(s: str) -> str:
                        import unicodedata as _ud
                        return "".join(
                            c for c in _ud.normalize("NFD", s)
                            if _ud.category(c) != "Mn"
                        )
                    nat_lower_s = _strip(nat_lower)
                    nat_cand_s  = _strip(nat_cand)
                    # Substring match OR fuzzy ≥ 0.80 (catches Brazil/Brasil, etc.)
                    nat_score = 1.0 if (
                        nat_lower_s in nat_cand_s
                        or nat_cand_s in nat_lower_s
                        or difflib.SequenceMatcher(None, nat_lower_s, nat_cand_s).ratio() >= 0.80
                    ) else 0.0
                    active_w     += w_nat
                    active_score += w_nat * nat_score

                if birth_year and by is not None:
                    # Allow ±1 year tolerance: age→birth_year conversion is imprecise
                    # (depends on whether birthday has passed this year).
                    by_score  = 1.0 if abs(birth_year - by) <= 1 else 0.0
                    active_w     += w_by
                    active_score += w_by * by_score

                score = active_score / active_w

                # Penalise candidates that provided no verifiable signals when
                # we had hints available. A name-only match (active_w=0.40) while
                # team/nationality hints were given suggests a retired/unknown player
                # with no TM context — require a stricter threshold for those.
                hints_provided = bool(team_aliases or nat_lower or birth_year)
                name_only = active_w <= w_name + 0.001  # only name weight active
                effective_threshold = (CONFIDENCE_THRESHOLD + 0.20) if (hints_provided and name_only) else CONFIDENCE_THRESHOLD

                self.logger.debug(
                    f"  candidate tm_id={tm_id} name='{p_name}' club='{club}' nat='{nat}' by={by} "
                    f"→ score={score:.3f} (name={name_score:.2f} active_w={active_w:.2f} "
                    f"thresh={effective_threshold:.2f})"
                )

                if score > best_score and score >= effective_threshold:
                    best_score = score
                    best_id = tm_id

            if best_id and best_score >= CONFIDENCE_THRESHOLD:
                # Ambiguity check: if the winner is name-only (active_w=0.40)
                # and there are other name-only candidates with score ≥ 0.90,
                # the name is too common to pick one confidently → skip.
                winner_name_only = not any(
                    (c[2] or c[3])  # club or nat present for winner
                    for c in candidates if c[0] == best_id
                )
                if winner_name_only:
                    rival_name_only_count = sum(
                        1 for c in candidates
                        if c[0] != best_id
                        and not c[2]   # no club
                        and not c[3]   # no nat
                    )
                    if rival_name_only_count >= 1:
                        self.logger.info(
                            f"search_player_by_name: '{name}' — ambiguous name-only match "
                            f"(tm_id={best_id} competes with {rival_name_only_count} other "
                            f"name-only candidates). Skipping."
                        )
                        continue  # try next fallback search

                self.logger.info(
                    f"search_player_by_name: '{name}' → tm_id={best_id} "
                    f"(score={best_score:.3f}, search='{search_term}')"
                )
                return best_id

            self.logger.debug(
                f"search_player_by_name: no confident match for '{name}' "
                f"with search='{search_term}' (best={best_score:.3f})"
            )

        # Squad-page fallback: all name searches failed (or were ambiguous).
        # Fetch the club's TM squad page directly and match by name.
        # This reliably finds low-profile HKPL players who rank below the top
        # search results for common names.
        if team_id and team_id in _TEAM_TM_CLUB_IDS:
            tm_club_id = _TEAM_TM_CLUB_IDS[team_id]
            self.logger.info(
                f"search_player_by_name: trying squad-page fallback for '{name}' "
                f"(club={team_id}, tm_club_id={tm_club_id})"
            )
            squad_result = self._search_player_in_squad(name, tm_club_id, birth_year=birth_year)
            if squad_result:
                return squad_result

        self.logger.info(
            f"search_player_by_name: all fallbacks exhausted for '{name}' "
            f"(best score across attempts < {CONFIDENCE_THRESHOLD})"
        )
        return None

    def fetch_and_store_player_photo(self, player_id: str, tm_player_id: str, session) -> bool:
        """
        Descarga la foto de perfil de Transfermarkt y la almacena como BLOB en la BD.
        Crea o actualiza el registro PlayerPhoto con is_primary=True.
        No escribe ningún archivo en disco.
        Devuelve True si la foto se guardó correctamente, False en caso contrario.
        """
        from sqlalchemy import select
        from models.db_models import PlayerPhoto

        photo_url = self.get_player_photo_url(tm_player_id)
        if not photo_url:
            self.logger.warning(f"fetch_and_store_player_photo: no URL for tm_id={tm_player_id}")
            return False

        try:
            resp = requests.get(photo_url, headers=self.headers, timeout=15)
            resp.raise_for_status()
            photo_bytes = resp.content
        except Exception as e:
            self.logger.warning(f"fetch_and_store_player_photo: download failed for {player_id}: {e}")
            return False

        try:
            stmt = select(PlayerPhoto).where(
                PlayerPhoto.player_id == player_id,
                PlayerPhoto.is_primary == True,
            )
            record = session.execute(stmt).scalars().first()
            if record:
                record.photo_data = photo_bytes
            else:
                record = PlayerPhoto(
                    player_id=player_id,
                    photo_data=photo_bytes,
                    is_primary=True,
                )
                session.add(record)
            session.commit()
            self.logger.info(f"fetch_and_store_player_photo: blob guardado para {player_id}")
            return True
        except Exception as e:
            session.rollback()
            self.logger.error(f"fetch_and_store_player_photo: DB error for {player_id}: {e}")
            return False
