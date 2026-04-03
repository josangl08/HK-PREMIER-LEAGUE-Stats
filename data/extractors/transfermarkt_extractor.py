# ABOUTME: Extractor for Transfermarkt data (team injuries, player match history, and player photos).
# ABOUTME: Provides get_match_history(), get_player_photo_url(), fetch_and_store_player_photo() with blob storage in DB.

import requests
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

class TransfermarktExtractor:
    """
    Extractor avanzado de Transfermarkt para rendimiento detallado de jugadores.
    """
    
    def __init__(self, cache_dir: str = "data/cache"):
        self.base_url = "https://www.transfermarkt.es"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept-Language': 'es-ES,es;q=0.9,en;q=0.8',
        }
        self.delay_between_requests = 2
        self.last_request_time = 0
        self.cache_dir = Path(cache_dir)
        self.historical_records_dir = Path("data/historical_records")
        self.competition_logos_dir = Path("assets/competition_logos")
        self.logger = logging.getLogger(__name__)

        # Whitelist ampliada: Todo lo que juegue un equipo de HK
        self.ALLOWED_COMPETITIONS = {
            "Hong Kong Premier League", "Hong Kong FA Cup", "Hong Kong Sapling Cup",
            "Hong Kong Sapling Cup ('15-'25)", "Hong Kong Senior Challenge Shield",
            "Hong Kong Community Cup", "HKPL", "HKFA Cup", "Senior Shield", "Sapling Cup",
            "菁英盃", "足總盃", "銀牌", "香港超級聯賽", "Play-off", "Champions League", 
            "AFC Cup", "ACL Elite", "AFC Champions League Two", "Quali"
        }

    def _wait_rate_limit(self):
        current_time = time.time()
        elapsed = current_time - self.last_request_time
        if elapsed < self.delay_between_requests:
            time.sleep(self.delay_between_requests - elapsed)
        self.last_request_time = time.time()
    
    def _make_request(self, url: str) -> Optional[BeautifulSoup]:
        try:
            self._wait_rate_limit()
            self.logger.info(f"Scraping: {url}")
            response = requests.get(url, headers=self.headers, timeout=15)
            response.raise_for_status()
            self.last_request_time = time.time()
            return BeautifulSoup(response.content, 'html.parser')
        except Exception as e:
            self.logger.error(f"Error en {url}: {e}")
            return None

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

    def search_player_by_name(
        self,
        name: str,
        team: str = "",
        nationality: str = "",
        birth_year: Optional[int] = None,
        position: str = "",
    ) -> Optional[int]:
        """
        Searches Transfermarkt by player name and confirms the match using a
        composite confidence score built from up to 4 signals:

          name         (weight 0.40) — SequenceMatcher ratio on player name
          club/team    (weight 0.35) — SequenceMatcher ratio on club name
          nationality  (weight 0.15) — exact country substring match (0 or 1)
          birth_year   (weight 0.10) — exact year match (0 or 1)

        Only signals that can actually be extracted from TM's search results
        contribute to the score — missing signals are not penalised.
        Returns the tm_id (int) of the best candidate with score ≥ 0.65, or None.

        Abbreviated names (e.g. "A. Agbodzie") are automatically searched by
        last name only, since TM cannot match a single initial.
        """
        # Handle abbreviated names: "A. Agbodzie" → search "Agbodzie"
        search_name = name
        abbrev_match = re.match(r'^[A-Z]\.\s+(.+)$', name)
        if abbrev_match:
            search_name = abbrev_match.group(1)
            self.logger.debug(f"search_player_by_name: abbreviated name '{name}' → searching '{search_name}'")

        encoded = urllib.parse.quote(search_name)
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
                    f"search_player_by_name: '{name}' → tm_id={tm_id} (TM redirect to profile)"
                )
                return tm_id

        # Each candidate: tm_id, player_name_text, club_text, nationality_text, birth_year_int
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
            row = a_tag.find_parent("tr")
            if not row:
                continue

            tds = row.find_all("td")

            # Club: td that contains a team link <a href="/(verein|club)/...">
            club_text = ""
            for td in tds:
                club_link = td.find("a", href=re.compile(r"/(verein|club)/"))
                if club_link:
                    club_text = club_link.get_text(strip=True)
                    break
                club_img = td.find("img", attrs={"class": re.compile(r"(club|vereins|logo)")})
                if club_img and club_img.get("alt"):
                    club_text = club_img["alt"]
                    break

            # Nationality: flag images on TM have "flagge" in their src URL.
            # Avoid picking up player portrait imgs whose title is the player name.
            nat_text = ""
            for img in row.find_all("img"):
                src = img.get("src", "") or img.get("data-src", "")
                if "flagge" not in src:
                    continue
                title = img.get("title", "")
                alt   = img.get("alt", "")
                if title and len(title) > 1:
                    nat_text = title
                    break
                if alt and len(alt) >= 2:
                    nat_text = alt
                    break

            # Birth year: 4-digit year in the row text
            row_text = row.get_text(" ", strip=True)
            by_match = re.search(r"\b(19[5-9]\d|200[0-9]|201[0-9]|202[0-4])\b", row_text)
            cand_birth_year = int(by_match.group(1)) if by_match else None

            candidates.append((tm_id, player_text, club_text, nat_text, cand_birth_year))

        if not candidates:
            self.logger.info(f"search_player_by_name: no results for '{name}'")
            return None

        name_lower = name.lower().strip()
        team_lower = team.lower().strip()
        nat_lower  = nationality.lower().strip()

        best_id: Optional[int] = None
        best_score = 0.0

        for tm_id, p_name, club, nat, by in candidates:
            # Name score — always computed, against original name and search_name
            p_name_lower = p_name.lower()
            name_score = max(
                difflib.SequenceMatcher(None, name_lower, p_name_lower).ratio(),
                difflib.SequenceMatcher(None, search_name.lower(), p_name_lower).ratio(),
            )
            # If we searched by last name (abbreviated), treat a full last-name substring
            # match as a strong hit — the first name we don't have so we can't compare it.
            if abbrev_match:
                last_name_lower = search_name.lower()
                # Check exact last-name word boundary match in TM candidate
                if re.search(r'\b' + re.escape(last_name_lower) + r'\b', p_name_lower):
                    name_score = max(name_score, 0.85)

            # Fixed weights
            w_name = 0.40
            w_club = 0.35
            w_nat  = 0.15
            w_by   = 0.10

            # Only include a signal in the denominator if we could actually verify it.
            # A hint we provided but couldn't extract from TM is NOT counted as a miss.
            active_w     = w_name
            active_score = w_name * name_score

            if team_lower and club:        # hint provided AND extractable from TM
                club_score = difflib.SequenceMatcher(None, team_lower, club.lower()).ratio()
                active_w     += w_club
                active_score += w_club * club_score

            if nat_lower and nat:          # hint provided AND extractable from TM
                nat_cand  = nat.lower()
                nat_score = 1.0 if (nat_lower in nat_cand or nat_cand in nat_lower) else 0.0
                active_w     += w_nat
                active_score += w_nat * nat_score

            if birth_year and by is not None:  # hint provided AND extractable from TM
                by_score  = 1.0 if birth_year == by else 0.0
                active_w     += w_by
                active_score += w_by * by_score

            score = active_score / active_w

            self.logger.debug(
                f"  candidate tm_id={tm_id} name='{p_name}' club='{club}' nat='{nat}' by={by} "
                f"→ score={score:.3f} (name={name_score:.2f} active_w={active_w:.2f})"
            )

            if score > best_score:
                best_score = score
                best_id = tm_id

        CONFIDENCE_THRESHOLD = 0.65
        if best_id and best_score >= CONFIDENCE_THRESHOLD:
            self.logger.info(
                f"search_player_by_name: '{name}' → tm_id={best_id} (score={best_score:.3f})"
            )
            return best_id

        self.logger.info(
            f"search_player_by_name: no confident match for '{name}' "
            f"(best score={best_score:.3f} < {CONFIDENCE_THRESHOLD})"
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
