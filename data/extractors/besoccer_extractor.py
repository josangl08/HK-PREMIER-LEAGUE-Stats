# ABOUTME: Extractor for BeSoccer data (player ratings and match intelligence).
# ABOUTME: Uses cloudscraper to bypass protections and extracts performance ratings (0-10).

import random
import time
import re
import logging
import urllib.parse
from datetime import datetime
from typing import Dict, List, Optional
from bs4 import BeautifulSoup
import cloudscraper

from utils.proxy_manager import ProxyManager

logger = logging.getLogger(__name__)

_USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
]

class BeSoccerExtractor:
    """
    Extractor para BeSoccer que recupera ratings de jugadores por partido.
    """
    def __init__(self, proxy_manager: Optional[ProxyManager] = None):
        self.base_url = "https://www.besoccer.com"
        self.proxy_manager = proxy_manager or ProxyManager()
        self.session = cloudscraper.create_scraper(
            browser={"browser": "chrome", "platform": "darwin", "mobile": False}
        )
        self.headers = {
            'User-Agent': random.choice(_USER_AGENTS),
            'Accept-Language': 'es-ES,es;q=0.9,en;q=0.8',
        }
        self.session.headers.update(self.headers)
        self.last_http_status = None

    def _make_request(self, url: str) -> Optional[BeautifulSoup]:
        proxy_url = self.proxy_manager.get_proxy() if self.proxy_manager.has_proxies else None
        proxies = self.proxy_manager.as_requests_dict(proxy_url) if proxy_url else None
        try:
            # Random delay
            time.sleep(random.uniform(1, 3))
            logger.info(f"BeSoccer Scraping: {url}")
            response = self.session.get(url, timeout=15, proxies=proxies)
            self.last_http_status = response.status_code
            response.raise_for_status()
            return BeautifulSoup(response.content, 'html.parser')
        except Exception as e:
            logger.error(f"Error en BeSoccer request {url}: {e}")
            return None

    def get_player_ratings(self, besoccer_id: str) -> Dict[str, float]:
        """
        Extrae los ratings de los partidos de un jugador.
        Detecta los encabezados de año (row-head) para resolver fechas correctamente.
        """
        url = f"{self.base_url}/player/matches/{besoccer_id}"
        soup = self._make_request(url)
        if not soup:
            return {}

        ratings = {}
        # Seleccionamos todas las filas para procesar encabezados y cuerpos en orden
        all_rows = soup.select("tr")
        logger.info(f"BeSoccer: Processing {len(all_rows)} total rows for {besoccer_id}")
        
        current_year = datetime.now().year
        
        for row in all_rows:
            try:
                # 1. Detectar cambio de año (row-head)
                if "row-head" in row.get("class", []):
                    ths = row.select("th")
                    if len(ths) >= 2:
                        year_text = ths[1].get_text(strip=True)
                        if re.match(r"^\d{4}$", year_text):
                            current_year = int(year_text)
                            logger.debug(f"BeSoccer Context: Year changed to {current_year}")
                    continue

                # 2. Procesar fila de partido (row-body)
                if "row-body" in row.get("class", []):
                    # Ignorar filas de temporada (career path style in matches page)
                    if "parent_row" in row.get("class", []): continue

                    # Extracción de Fecha (color-box)
                    date_cell = row.select_one("td.color-cell .color-box")
                    if not date_cell: continue
                    
                    spans = date_cell.select("span")
                    if len(spans) < 2: continue
                    
                    day = spans[0].get_text(strip=True)
                    month_text = spans[1].get_text(strip=True)
                    date_str = f"{day} {month_text}"
                    
                    # Extracción de Rating (td.tiny)
                    rating_val = None
                    tiny_cells = row.select("td.tiny")
                    for cell in tiny_cells:
                        text = cell.get_text(strip=True).replace(',', '.')
                        if re.match(r"^(\d(?:\.\d)?)$", text):
                            rating_val = float(text)
                            break
                    
                    if rating_val is None: continue

                    # Parseo con el año detectado en el row-head
                    match_date = self._parse_date(date_str, default_year=current_year)
                    if match_date:
                        ratings[match_date] = rating_val

            except Exception as e:
                logger.debug(f"Error parseando fila en BeSoccer: {e}")
                continue
        
        return ratings

    def get_season_ratings(self, besoccer_id: str) -> Dict[str, float]:
        """
        Extrae el rating medio por temporada desde la página career-path.
        Estructura: tr.row-body.parent_row con celdas data-content-tab="tcdc1".
        Devuelve dict: { '2025/26': 5.6 }
        """
        url = f"{self.base_url}/player/career-path/{besoccer_id}"
        soup = self._make_request(url)
        if not soup:
            return {}

        season_ratings = {}
        # Buscamos las filas de temporada (parent_row suele ser la fila principal del equipo/temporada)
        rows = soup.select("tr.row-body.parent_row")
        
        for row in rows:
            try:
                # 1. Extraer Temporada (ej: "2025/26")
                season_el = row.select_one(".ta-l a.arrow-box")
                if not season_el: continue
                season_text = season_el.get_text(strip=True).replace(" ", "")
                season_text = re.sub(r"[^\d/]", "", season_text)
                if not re.match(r"^\d{4}/\d{2}$", season_text): continue

                # 2. Extraer Rating (celda con data-content-tab="tcdc1" es el rating promedio)
                # Según el HTML provisto por el usuario:
                # <td data-content-tab="tcdc1">5.6</td>
                rating_val = None
                rating_cells = row.select('td[data-content-tab="tcdc1"]')
                for cell in rating_cells:
                    text = cell.get_text(strip=True).replace(',', '.')
                    # El rating suele ser un float X.X
                    if re.match(r"^\d\.\d$", text):
                        rating_val = float(text)
                        break
                
                if rating_val is None:
                    # Fallback: buscar cualquier celda que contenga un rating (X.X)
                    tds = row.select("td")
                    for td in tds:
                        val = td.get_text(strip=True).replace(',', '.')
                        if re.match(r"^\d\.\d$", val):
                            rating_val = float(val)
                            break

                if rating_val is not None:
                    season_ratings[season_text] = rating_val
                    logger.debug(f"✓ Season Rating found: {season_text} -> {rating_val}")

            except Exception as e:
                logger.debug(f"Error parseando temporada en BeSoccer: {e}")
                continue
        
        return season_ratings

    def search_player(self, name: str, team_name: Optional[str] = None) -> Optional[str]:
        """
        Busca un jugador y devuelve su ID (slug).
        Intenta varias rutas de búsqueda si la principal falla, incluyendo Google fallback.
        """
        query = urllib.parse.quote(name)
        search_paths = [
            f"{self.base_url}/search?q={query}",
            f"https://es.besoccer.com/buscar?q={query}",
            f"{self.base_url}/search-player?q={query}",
            f"https://www.besoccer.com/buscar?q={query}"
        ]

        for url in search_paths:
            soup = self._make_request(url)
            if not soup: continue
            
            results = soup.select(".search-item, .item-search, a[href*='/player/']")
            for res in results:
                href = res.get("href") if 'href' in res.attrs else None
                if not href:
                    link = res.select_one("a[href*='/player/']")
                    if link: href = link.get("href")
                
                if not href: continue
                
                match = re.search(r"/player/([^/?]+)", href)
                if match:
                    slug = match.group(1)
                    if team_name and team_name.lower() not in res.get_text().lower():
                        continue
                    return slug
            
            first_player = soup.select_one("a[href*='/player/']")
            if first_player:
                href = first_player.get("href")
                match = re.search(r"/player/([^/?]+)", href)
                if match: return match.group(1)

        # FINAL FALLBACK: Google Search
        logger.info(f"BeSoccer Internal Search failed for {name}. Trying Google fallback...")
        try:
            from googlesearch import search
            google_query = f"site:besoccer.com player {name}"
            if team_name: google_query += f" {team_name}"
            
            for url in search(google_query, num_results=3):
                if "/player/" in url:
                    match = re.search(r"/player/([^/?]+)", url)
                    if match:
                        slug = match.group(1)
                        logger.info(f"✓ BeSoccer slug found via Google: {slug}")
                        return slug
        except Exception as e:
            logger.warning(f"Google fallback search failed: {e}")

        return None

    def _parse_date(self, text: str, default_year: int = 2024) -> Optional[str]:
        if not text: return None
        text = text.strip()
        
        # Formato ISO YYYY-MM-DD
        if re.match(r"^\d{4}-\d{2}-\d{2}$", text):
            return text
            
        # Formato DD/MM/YYYY o DD-MM-YYYY
        m = re.search(r"(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})", text)
        if m:
            d, m, y = m.groups()
            if len(y) == 2: y = "20" + y
            return f"{y}-{m.zfill(2)}-{d.zfill(2)}"
        
        # Formato BeSoccer común: "04 Apr" (requiere inferencia de año)
        months = {
            'Jan': '01', 'Feb': '02', 'Mar': '03', 'Apr': '04', 'May': '05', 'Jun': '06',
            'Jul': '07', 'Aug': '08', 'Sep': '09', 'Oct': '10', 'Nov': '11', 'Dec': '12',
            'Ene': '01', 'Feb': '02', 'Mar': '03', 'Abr': '04', 'May': '05', 'Jun': '06',
            'Jul': '07', 'Ago': '08', 'Sep': '09', 'Oct': '10', 'Nov': '11', 'Dic': '12'
        }
        
        # Caso "04 Apr"
        m = re.search(r"(\d{1,2})\s+([a-zA-Z]{3})", text)
        if m:
            d, mon = m.groups()
            mon_num = months.get(mon.capitalize()[:3], "01")
            # Nota: Esta lógica es simplificada; en un entorno real se ajustaría el año 
            # basándose en si la fecha es futura respecto al "current_run"
            return f"{default_year}-{mon_num}-{d.zfill(2)}"

        # Caso "12 Oct 23"
        m = re.search(r"(\d{1,2})\s+([a-zA-Z]{3})\s+(\d{2,4})", text)
        if m:
            d, mon, y = m.groups()
            mon_num = months.get(mon.capitalize()[:3], "01")
            if len(y) == 2: y = "20" + y
            return f"{y}-{mon_num}-{d.zfill(2)}"

        return None
