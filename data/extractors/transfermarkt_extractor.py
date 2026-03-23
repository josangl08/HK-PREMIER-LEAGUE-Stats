# ABOUTME: Extractor for Transfermarkt data (team injuries and player match history).
# ABOUTME: Provides get_match_history() with detailed match events (including injuries/bench) and continental cups.

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
        """Obtiene el historial de partidos filtrando por equipo de HK o competición de HK."""
        season_key, tm_season_id = self._season_key(season_id)
        
        # Cache histórico (solo si la temporada ya terminó)
        is_completed = self._is_season_completed(season_key)
        if is_completed:
            records = self._read_historical_records(player_id)
            if season_key in records.get("seasons", {}) and records["seasons"][season_key].get("matches"):
                return records["seasons"][season_key]["matches"]

        # Scraping detallado (vista ampliada plus/1)
        url = f"{self.base_url}/x/leistungsdatendetails/spieler/{player_id}/saison/{tm_season_id}/plus/1"
        soup = self._make_request(url)
        if not soup: return []
        
        result = self._parse_detailed_performance(soup)
        
        if is_completed:
            records = self._read_historical_records(player_id)
            records.setdefault("seasons", {})[season_key] = result
            records["last_updated"] = datetime.now().date().isoformat()
            self._write_historical_records(player_id, records)
            
        return result.get("matches", [])

    def _parse_detailed_performance(self, soup: BeautifulSoup) -> Dict:
        matches = []
        summary = {"goals": 0, "assists": 0, "yellow_cards": 0, "red_cards": 0, "minutes_played": 0, "total_matches": 0}
        
        # En la vista detallada, los partidos están en 'boxes' por competición
        boxes = soup.find_all("div", {"class": "box"})
        for box in boxes:
            header = box.find(["h2", "div"], {"class": ["content-box-headline", "table-header"]})
            if not header: continue
            
            comp_name = header.get_text(strip=True)
            # Filtro: ¿Es una competición de HK o internacional asiática?
            if not any(c.lower() in comp_name.lower() for c in self.ALLOWED_COMPETITIONS):
                continue

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
                    # Si la celda 7 (Posición) o la celda 14 (Minutos) tienen texto especial
                    status_text = ""
                    is_played = True
                    
                    # Verificar si hay mensaje de "No convocado", "Lesionado", etc en las celdas finales
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
                        "result": res,
                        "status": status_text if not is_played else "Jugado",
                        "goals": 0, "assists": 0, "yellow_cards": 0, "red_cards": 0, "minutes_played": 0
                    }

                    if is_played:
                        match_entry["position"] = cells[7].get_text(strip=True)
                        match_entry["goals"] = self._parse_number(cells[8].get_text(strip=True))
                        match_entry["assists"] = self._parse_number(cells[9].get_text(strip=True))
                        
                        # Tarjetas: 10 (Amarilla), 11 (Doble), 12 (Roja)
                        match_entry["yellow_cards"] = 1 if cells[10].get_text(strip=True) else 0
                        match_entry["red_cards"] = 1 if (cells[11].get_text(strip=True) or cells[12].get_text(strip=True)) else 0
                        
                        # Minutos (última celda con comilla)
                        for c in reversed(cells):
                            txt = c.get_text(strip=True)
                            if "'" in txt:
                                match_entry["minutes_played"] = self._parse_number(txt.replace("'", ""))
                                break
                        
                        # Actualizar sumario solo si jugó
                        summary["goals"] += match_entry["goals"]
                        summary["assists"] += match_entry["assists"]
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
