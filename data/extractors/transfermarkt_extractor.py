# ABOUTME: Extractor for Transfermarkt data (team injuries and player match history).
# ABOUTME: Provides get_match_history() with competition logo download and detailed match events.

import requests
from bs4 import BeautifulSoup, Tag
import pandas as pd
import time
import re
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
