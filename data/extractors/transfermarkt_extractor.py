"""
Extractor de datos de lesiones desde Transfermarkt.
Maneja el scraping de equipos y lesiones de la Liga Premier de Hong Kong.
"""

import requests
from bs4 import BeautifulSoup, Tag
import pandas as pd
import time
import re
from datetime import datetime, timedelta
import logging
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import json

class TransfermarktExtractor:
    """
    Extractor de datos de Transfermarkt para lesiones de equipos de Hong Kong.
    """
    
    def __init__(self, cache_dir: str = "data/cache"):
        """
        Inicializa el extractor.
        
        Args:
            cache_dir: Directorio para cache de datos
        """
        self.base_url = "https://www.transfermarkt.es"
        self.league_url = f"{self.base_url}/hong-kong-premier-league/startseite/wettbewerb/HGKG/saison_id/2024"
        
        # Headers para evitar bloqueos
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'es-ES,es;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
        # Configuración de rate limiting
        self.delay_between_requests = 2  # segundos
        self.last_request_time = 0
        
        # Cache
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True, parents=True)
        self.teams_cache_file = self.cache_dir / "transfermarkt_teams.json"
        self.injuries_cache_file = self.cache_dir / "transfermarkt_injuries.json"
        
        # Configurar logging
        self.logger = logging.getLogger(__name__)
    
    def _wait_rate_limit(self):
        """Aplica rate limiting entre requests."""
        current_time = time.time()
        elapsed = current_time - self.last_request_time
        if elapsed < self.delay_between_requests:
            time.sleep(self.delay_between_requests - elapsed)
        self.last_request_time = time.time()
    
    def _make_request(self, url: str) -> Optional[BeautifulSoup]:
        """
        Realiza una petición HTTP con manejo de errores.
        
        Args:
            url: URL a consultar
            
        Returns:
            BeautifulSoup object o None si hay error
        """
        try:
            self._wait_rate_limit()
            self.logger.info(f"Solicitando: {url}")
            
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            return soup
            
        except requests.RequestException as e:
            self.logger.error(f"Error solicitando {url}: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Error inesperado procesando {url}: {e}")
            return None
    
    def extract_teams(self, force_refresh: bool = False) -> List[Dict]:
        """
        Extrae la lista de equipos de la liga.
        
        Args:
            force_refresh: Forzar actualización ignorando cache
            
        Returns:
            Lista de diccionarios con información de equipos
        """
        # Verificar cache
        if not force_refresh and self.teams_cache_file.exists():
            try:
                with open(self.teams_cache_file, 'r', encoding='utf-8') as f:
                    cached_data = json.load(f)
                    # Verificar si el cache es reciente (menos de 24 horas)
                    cache_time = datetime.fromisoformat(cached_data.get('timestamp', '2000-01-01'))
                    if datetime.now() - cache_time < timedelta(hours=24):
                        self.logger.info("Usando equipos desde cache")
                        return cached_data['teams']
            except Exception as e:
                self.logger.warning(f"Error leyendo cache de equipos: {e}")
        
        # Scraping de equipos
        soup = self._make_request(self.league_url)
        if not soup:
            return []
        
        teams = []
        
        try:
            # Buscar tabla de equipos
            # Puede estar en diferentes ubicaciones según el layout
            team_links = soup.find_all('a', href=re.compile(r'/[^/]+/startseite/verein/\d+'))
            
            
            for link in team_links:
                if not isinstance(link, Tag):
                    continue
                href = link.get('href', '')
                title = link.get('title', '')
                
                # Extraer ID del equipo de la URL
                if href is not None:
                    href_str = str(href)
                    match = re.search(r'/verein/(\d+)', href_str)
                else:
                    match = None
                if match and title:
                    team_id = match.group(1)
                    
                    # Crear nombre limpio para URL de lesiones
                    team_name_url = href_str.split('/')[1]
                    
                    team_info = {
                        'id': team_id,
                        'name': str(title).strip(),
                        'url_name': team_name_url,
                        'injuries_url': f"{self.base_url}/{team_name_url}/sperrenundverletzungen/verein/{team_id}/plus/1"
                    }
                    
                    teams.append(team_info)
                    self.logger.info(f"Equipo encontrado: {title} (ID: {team_id})")
        
        except Exception as e:
            self.logger.error(f"Error extrayendo equipos: {e}")
            return []
        
        # Guardar en cache
        cache_data = {
            'timestamp': datetime.now().isoformat(),
            'teams': teams
        }
        
        try:
            with open(self.teams_cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
                self.logger.info(f"Equipos guardados en cache: {len(teams)}")
        except Exception as e:
            self.logger.warning(f"Error guardando cache de equipos: {e}")
        
        return teams
    
    def extract_team_injuries(self, team: Dict) -> List[Dict]:
        """
        Extrae las lesiones de un equipo específico.
        
        Args:
            team: Diccionario con información del equipo
            
        Returns:
            Lista de diccionarios con información de lesiones
        """
        soup = self._make_request(team['injuries_url'])
        if not soup:
            return []
        
        injuries = []
        
        try:
            # Buscar tabla de lesiones
            table = soup.find('table', {'class': 'items'})
            if not table:
                self.logger.warning(f"No se encontró tabla de lesiones para {team['name']}")
                return []
            
            # Buscar filas de lesiones (evitar headers y separadores)
            if isinstance(table, Tag):
                tbody = table.find('tbody')
                if isinstance(tbody, Tag):
                    rows = tbody.find_all('tr')
                else:
                    rows = table.find_all('tr')
            else:
                self.logger.warning(f"'table' no es un Tag válido para buscar filas de lesiones en {team['name']}")
                return []
            
            for row in rows:
                # Saltar filas de header y separadores
                if not isinstance(row, Tag):
                    continue
                if (row.find('th') or 
                    row.find('td', {'class': 'extrarow'}) or 
                    len(row.find_all('td')) < 8):
                    continue
                
                cells = row.find_all('td')
                if len(cells) < 8:
                    continue
                
                try:
                    # Extraer información del jugador (primera celda)
                    player_cell = cells[0]
                    inline_table = None
                    if isinstance(player_cell, Tag):
                        inline_table = player_cell.find('table', {'class': 'inline-table'})
                    
                    if not inline_table:
                        continue
                    
                    # Nombre del jugador
                    player_link = None
                    if isinstance(inline_table, Tag):
                        player_link = inline_table.find('a')
                    if isinstance(player_link, Tag):
                        player_title = player_link.get('title', '')
                        player_name = str(player_title).strip() if player_title else 'Desconocido'
                    else:
                        player_name = 'Desconocido'
                    
                    # Posición del jugador
                    position_rows = inline_table.find_all('tr') if isinstance(inline_table, Tag) else []
                    position = 'Desconocida'
                    if len(position_rows) > 1:
                        row = position_rows[1]
                        if isinstance(row, Tag):
                            position_cell = row.find('td')
                            if position_cell:
                                position = position_cell.get_text(strip=True)
                    
                    # Extraer otros campos
                    age = self._extract_text(cells[1])
                    injury_type = self._extract_text(cells[2])
                    date_from = self._extract_text(cells[3])
                    date_until = self._extract_text(cells[4])
                    matches_missed = self._extract_number_from_link(cells[5])
                    days = self._extract_text(cells[6])
                    market_value = self._extract_text(cells[7])
                    
                    # Crear registro de lesión
                    injury = {
                        'player_name': player_name,
                        'team': team['name'],
                        'team_id': team['id'],
                        'position': position,
                        'age': self._parse_age(age),
                        'injury_type': self._clean_injury_type(injury_type),
                        'date_from': self._parse_date(date_from),
                        'date_until': self._parse_date(date_until),
                        'matches_missed': self._parse_number(matches_missed),
                        'days': self._parse_number(days),
                        'market_value': self._parse_market_value(market_value),
                        'extracted_at': datetime.now().isoformat()
                    }
                    
                    injuries.append(injury)
                    self.logger.debug(f"Lesión extraída: {player_name} - {injury_type}")
                
                except Exception as e:
                    self.logger.warning(f"Error procesando fila de lesión: {e}")
                    continue
        
        except Exception as e:
            self.logger.error(f"Error extrayendo lesiones de {team['name']}: {e}")
        
        self.logger.info(f"Lesiones extraídas de {team['name']}: {len(injuries)}")
        return injuries
    
    def extract_all_injuries(self, force_refresh: bool = False) -> List[Dict]:
        """
        Extrae lesiones de todos los equipos de la liga.
        
        Args:
            force_refresh: Forzar actualización ignorando cache
            
        Returns:
            Lista de diccionarios con todas las lesiones
        """
        # Verificar cache
        if not force_refresh and self.injuries_cache_file.exists():
            try:
                with open(self.injuries_cache_file, 'r', encoding='utf-8') as f:
                    cached_data = json.load(f)
                    # Verificar si el cache es reciente (menos de 4 horas)
                    cache_time = datetime.fromisoformat(cached_data.get('timestamp', '2000-01-01'))
                    if datetime.now() - cache_time < timedelta(hours=4):
                        self.logger.info("Usando lesiones desde cache")
                        return cached_data['injuries']
            except Exception as e:
                self.logger.warning(f"Error leyendo cache de lesiones: {e}")
        
        # Obtener lista de equipos
        teams = self.extract_teams(force_refresh=force_refresh)
        if not teams:
            self.logger.error("No se pudieron obtener equipos")
            return []
        
        all_injuries = []
        
        # Extraer lesiones de cada equipo
        for i, team in enumerate(teams, 1):
            self.logger.info(f"Procesando equipo {i}/{len(teams)}: {team['name']}")
            
            team_injuries = self.extract_team_injuries(team)
            all_injuries.extend(team_injuries)
            
            # Pausa entre equipos para ser amigables con el servidor
            if i < len(teams):
                time.sleep(1)
        
        # Guardar en cache
        cache_data = {
            'timestamp': datetime.now().isoformat(),
            'total_teams': len(teams),
            'total_injuries': len(all_injuries),
            'injuries': all_injuries
        }
        
        try:
            with open(self.injuries_cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
                self.logger.info(f"Lesiones guardadas en cache: {len(all_injuries)}")
        except Exception as e:
            self.logger.warning(f"Error guardando cache de lesiones: {e}")
        
        self.logger.info(f"Extracción completada: {len(all_injuries)} lesiones de {len(teams)} equipos")
        return all_injuries
    
    # Métodos auxiliares para limpieza de datos
    
    def _extract_text(self, cell) -> str:
        """Extrae texto limpio de una celda."""
        if not cell:
            return ''
        return cell.get_text(strip=True)
    
    def _extract_number_from_link(self, cell) -> str:
        """Extrae número de un link (para partidos perdidos)."""
        if not cell:
            return '0'
        
        link = cell.find('a')
        if link:
            return link.get_text(strip=True)
        
        return cell.get_text(strip=True)
    
    def _parse_age(self, age_str: str) -> int:
        """Convierte string de edad a entero."""
        try:
            return int(re.findall(r'\d+', age_str)[0]) if age_str else 0
        except:
            return 0
    
    def _parse_number(self, number_str: str) -> int:
        """Convierte string a número entero."""
        try:
            return int(re.findall(r'\d+', number_str)[0]) if number_str else 0
        except:
            return 0
    
    def _parse_date(self, date_str: str) -> Optional[str]:
        """Convierte fecha de formato DD/MM/YYYY a YYYY-MM-DD."""
        if not date_str or date_str.strip() == '':
            return None
        
        try:
            # Formato esperado: DD/MM/YYYY
            if re.match(r'\d{2}/\d{2}/\d{4}', date_str):
                day, month, year = date_str.split('/')
                return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
        except:
            pass
        
        return None
    
    def _parse_market_value(self, value_str: str) -> int:
        """Convierte valor de mercado a entero (euros)."""
        if not value_str:
            return 0
        
        try:
            # Remover moneda y espacios
            clean_value = re.sub(r'[€\s]', '', value_str)
            
            # Convertir mil/millones
            if 'mil' in value_str.lower():
                number = float(re.findall(r'[\d,]+', clean_value)[0].replace(',', '.'))
                return int(number * 1000)
            elif 'millón' in value_str.lower() or 'millones' in value_str.lower():
                number = float(re.findall(r'[\d,]+', clean_value)[0].replace(',', '.'))
                return int(number * 1000000)
            else:
                # Valor directo
                return int(re.findall(r'\d+', clean_value)[0])
        except:
            return 0
    
    def _clean_injury_type(self, injury_str: str) -> str:
        """Limpia y normaliza el tipo de lesión."""
        if not injury_str:
            return 'Desconocida'
        
        # Diccionario de normalización
        injury_mapping = {
            'lesión de rodilla': 'Lesión de rodilla',
            'rotura del ligamento de la rodilla': 'Rotura de ligamento',
            'lesión muscular': 'Lesión muscular',
            'esguince': 'Esguince',
            'fractura': 'Fractura',
            'contusión': 'Contusión',
            'tendinitis': 'Tendinitis',
            'desgarro': 'Desgarro muscular'
        }
        
        injury_lower = injury_str.lower().strip()
        for key, value in injury_mapping.items():
            if key in injury_lower:
                return value
        
        # Si no encuentra coincidencia, capitalizar primera letra
        return injury_str.strip().capitalize()
    
    def get_cache_info(self) -> Dict:
        """Obtiene información sobre el cache."""
        info = {
            'teams_cache_exists': self.teams_cache_file.exists(),
            'injuries_cache_exists': self.injuries_cache_file.exists(),
            'teams_cache_size': 0,
            'injuries_cache_size': 0,
            'teams_cache_modified': None,
            'injuries_cache_modified': None
        }
        
        if info['teams_cache_exists']:
            stat = self.teams_cache_file.stat()
            info['teams_cache_size'] = stat.st_size
            info['teams_cache_modified'] = datetime.fromtimestamp(stat.st_mtime).isoformat()
        
        if info['injuries_cache_exists']:
            stat = self.injuries_cache_file.stat()
            info['injuries_cache_size'] = stat.st_size
            info['injuries_cache_modified'] = datetime.fromtimestamp(stat.st_mtime).isoformat()
        
        return info
    
    def clear_cache(self):
        """Limpia el cache de equipos y lesiones."""
        if self.teams_cache_file.exists():
            self.teams_cache_file.unlink()
            self.logger.info("Cache de equipos eliminado")
        
        if self.injuries_cache_file.exists():
            self.injuries_cache_file.unlink()
            self.logger.info("Cache de lesiones eliminado")