# ABOUTME: Extractor for Sofascore data (granular stats and heatmaps).
# ABOUTME: Queries Sofascore internal API for match-specific player performance.

import random
import time
import logging
import requests
import urllib.parse
from typing import Dict, List, Optional, Any

from utils.proxy_manager import ProxyManager

logger = logging.getLogger(__name__)

class SofascoreExtractor:
    """
    Extractor para Sofascore que recupera estadísticas granulares y heatmaps.
    """
    def __init__(self, proxy_manager: Optional[ProxyManager] = None):
        self.base_api_url = "https://api.sofascore.com/api/v1"
        self.proxy_manager = proxy_manager or ProxyManager()
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
            'Origin': 'https://www.sofascore.com',
            'Referer': 'https://www.sofascore.com/',
        }
        self.last_http_status = None

    def _make_request(self, endpoint: str) -> Optional[Dict]:
        url = f"{self.base_api_url}/{endpoint}"
        proxy_url = self.proxy_manager.get_proxy() if self.proxy_manager.has_proxies else None
        proxies = self.proxy_manager.as_requests_dict(proxy_url) if proxy_url else None
        try:
            # Sofascore API is relatively fast but let's be polite
            time.sleep(random.uniform(0.5, 1.5))
            logger.info(f"Sofascore API Request: {url}")
            response = requests.get(url, headers=self.headers, timeout=15, proxies=proxies)
            self.last_http_status = response.status_code
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error en Sofascore API {url}: {e}")
            return None

    def get_match_player_stats(self, match_id: int, player_id: int) -> Optional[Dict[str, Any]]:
        """
        Obtiene estadísticas detalladas de un jugador en un partido.
        match_id y player_id son los IDs internos de Sofascore.
        """
        endpoint = f"event/{match_id}/player/{player_id}/statistics"
        return self._make_request(endpoint)

    def get_player_last_matches(self, player_id: int, page: int = 0) -> List[Dict]:
        """
        Obtiene los partidos de un jugador por página (20 eventos por página).
        """
        endpoint = f"player/{player_id}/events/last/{page}"
        data = self._make_request(endpoint)
        if not data or 'events' not in data:
            return []
        return data['events']

    def get_all_player_events(self, player_id: int, max_pages: int = 5) -> List[Dict]:
        """
        Recupera todos los eventos disponibles navegando por las páginas.
        """
        all_events = []
        for page in range(max_pages):
            events = self.get_player_last_matches(player_id, page=page)
            if not events:
                break
            all_events.extend(events)
            # Si recibimos menos de 20, es la última página
            if len(events) < 20:
                break
        return all_events

    def search_player(self, name: str) -> Optional[int]:
        """
        Busca un jugador y devuelve su ID interno.
        """
        query = urllib.parse.quote(name)
        endpoint = f"search/all?q={query}&type=player"
        data = self._make_request(endpoint)
        if not data or 'results' not in data:
            return None
        
        # Filtrar resultados de tipo player
        players = [r for r in data['results'] if r.get('type') == 'player']
        if players:
            # Devolver el ID del primer resultado
            return players[0].get('entity', {}).get('id')
        
        return None

    def get_player_attribute_overviews(self, player_id: int) -> Optional[Dict]:
        """
        Obtiene el resumen de atributos (radar chart data) de un jugador.
        """
        endpoint = f"player/{player_id}/attribute-overviews"
        return self._make_request(endpoint)

    def get_player_heatmap(self, match_id: int, player_id: int) -> List[Dict[str, float]]:
        """
        Obtiene las coordenadas del mapa de calor de un jugador en un partido.
        Devuelve una lista de puntos [{x: 0.5, y: 0.2}, ...]
        """
        endpoint = f"event/{match_id}/player/{player_id}/heatmap"
        data = self._make_request(endpoint)
        if not data or 'heatmap' not in data:
            return []
        return data['heatmap']
