"""
Extractor de datos de lesiones desde Transfermarkt - VERSIÓN CORREGIDA
Maneja el scraping de equipos y lesiones de la Liga Premier de Hong Kong.
"""

import requests
from bs4 import BeautifulSoup, Tag
import pandas as pd
import time
import re
from datetime import datetime, timedelta
import logging
from typing import Dict, List, Optional, Tuple, Union, Sequence
from bs4 import Tag
from bs4.element import PageElement
from pathlib import Path
import json

class TransfermarktExtractor:
    """
    Extractor de datos de Transfermarkt para lesiones de equipos de Hong Kong.
    VERSIÓN CORREGIDA - Elimina duplicados y mejora el parsing.
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
        
        # Configuración de rate limiting mejorada
        self.delay_between_requests = 3  # Aumentado para evitar bloqueos
        self.last_request_time = 0
        self.max_retries = 2  # Máximo intentos por petición
        
        # Cache
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True, parents=True)
        self.teams_cache_file = self.cache_dir / "transfermarkt_teams.json"
        self.injuries_cache_file = self.cache_dir / "transfermarkt_injuries.json"
        
        # Configurar logging
        self.logger = logging.getLogger(__name__)
        
        # Lista de equipos conocidos para validación
        self.known_teams = {
            'Lee Man', 'Eastern', 'Kitchee', 'Rangers', 'Southern District',
            'Tai Po', 'Kowloon City', 'North District', 'Hong Kong Football Club'
        }
    
    def _wait_rate_limit(self):
        """Aplica rate limiting entre requests."""
        current_time = time.time()
        elapsed = current_time - self.last_request_time
        if elapsed < self.delay_between_requests:
            time.sleep(self.delay_between_requests - elapsed)
        self.last_request_time = time.time()
    
    def _make_request(self, url: str, retries: int = 0) -> Optional[BeautifulSoup]:
        """
        Realiza una petición HTTP con manejo de errores y reintentos.
        
        Args:
            url: URL a consultar
            retries: Número de reintentos realizados
            
        Returns:
            BeautifulSoup object o None si hay error
        """
        try:
            self._wait_rate_limit()
            self.logger.info(f"Solicitando: {url} (intento {retries + 1})")
            
            # Timeout más largo para peticiones complejas
            response = requests.get(url, headers=self.headers, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            return soup
            
        except requests.Timeout as e:
            if retries < self.max_retries:
                self.logger.warning(f"Timeout en {url}, reintentando...")
                time.sleep(5)  # Pausa extra antes de reintentar
                return self._make_request(url, retries + 1)
            else:
                self.logger.error(f"Timeout final en {url}: {e}")
                return None
                
        except requests.RequestException as e:
            if retries < self.max_retries:
                self.logger.warning(f"Error de red en {url}, reintentando...")
                time.sleep(5)
                return self._make_request(url, retries + 1)
            else:
                self.logger.error(f"Error final solicitando {url}: {e}")
                return None
                
        except Exception as e:
            self.logger.error(f"Error inesperado procesando {url}: {e}")
            return None
    
    def extract_teams(self, force_refresh: bool = False) -> List[Dict]:
        """
        Extrae la lista de equipos de la liga - VERSIÓN CORREGIDA.
        
        Args:
            force_refresh: Forzar actualización ignorando cache
            
        Returns:
            Lista de diccionarios con información de equipos (sin duplicados)
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
        seen_team_ids = set()  # Para evitar duplicados
        
        try:
            # Estrategia 1: Buscar en la tabla principal
            self.logger.info("Buscando equipos en tabla principal...")
            
            # Buscar tabla de clasificación o equipos
            table = soup.find('table', {'class': 'items'})
            if table and isinstance(table, Tag):
                rows = table.find_all('tr')
                for row in rows:
                    if not isinstance(row, Tag):
                        continue
                    
                    # Buscar células con enlaces de equipos
                    cells = row.find_all('td')
                    for cell in cells:
                        links = cell.find_all('a', href=re.compile(r'/[^/]+/startseite/verein/\d+')) if isinstance(cell, Tag) else []
                        for link in links:
                            if isinstance(link, Tag):
                                team_info = self._extract_team_from_link(link)
                                if team_info and team_info['id'] not in seen_team_ids:
                                    teams.append(team_info)
                                    seen_team_ids.add(team_info['id'])
            
            # Estrategia 2: Buscar directamente todos los enlaces de equipos
            if len(teams) < 8:  # Si no encontramos suficientes equipos
                self.logger.info("Buscando equipos directamente en toda la página...")
                team_links = soup.find_all('a', href=re.compile(r'/[^/]+/startseite/verein/\d+'))
                
                for link in team_links:
                    team_info = self._extract_team_from_link(link)
                    if team_info and team_info['id'] not in seen_team_ids:
                        teams.append(team_info)
                        seen_team_ids.add(team_info['id'])
                        
                        # Limitar a un número razonable de equipos
                        if len(teams) >= 12:
                            break
            
            # Filtrar equipos conocidos
            filtered_teams = []
            for team in teams:
                # Verificar si es un equipo conocido o contiene palabras clave
                team_name = team['name']
                if (any(known in team_name for known in self.known_teams) or
                    'hong kong' in team_name.lower() or
                    'district' in team_name.lower() or
                    'city' in team_name.lower()):
                    filtered_teams.append(team)
            
            teams = filtered_teams if filtered_teams else teams
                    
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
        
        self.logger.info(f"Equipos extraídos (sin duplicados): {len(teams)}")
        return teams
    def _extract_team_from_link(self, link: Union[Tag, PageElement]) -> Optional[Dict]:
        """
        Extrae información de equipo desde un enlace.
        
        Args:
            link: Tag o PageElement de enlace
            link: Tag de enlace
            
        Returns:
            Diccionario con información del equipo o None
        """
        try:
            if not isinstance(link, Tag):
                return None
                
            href = link.get('href', '')
            title = link.get('title', '') or link.get_text(strip=True)
            
            if not href or not title:
                return None
            
            # Extraer ID del equipo de la URL
            match = re.search(r'/verein/(\d+)', str(href))
            if not match:
                return None
            
            team_id = match.group(1)
            
            # Crear nombre limpio para URL de lesiones
            team_name_url = str(href).split('/')[1] if '/' in str(href) else f"team-{team_id}"
            
            team_info = {
                'id': team_id,
                'name': str(title).strip(),
                'url_name': team_name_url,
                'injuries_url': f"{self.base_url}/{team_name_url}/sperrenundverletzungen/verein/{team_id}/plus/1"
            }
            
            self.logger.debug(f"Equipo extraído: {title} (ID: {team_id})")
            return team_info
            
        except Exception as e:
            self.logger.debug(f"Error extrayendo equipo de enlace: {e}")
            return None
    
    def extract_team_injuries(self, team: Dict) -> List[Dict]:
        """
        Extrae las lesiones de un equipo específico - VERSIÓN MEJORADA.
        
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
            
            # Buscar filas de lesiones
            tbody = table.find('tbody') if isinstance(table, Tag) else None
            rows = []
            if isinstance(tbody, Tag):
                rows = tbody.find_all('tr')
            elif isinstance(table, Tag):
                rows = table.find_all('tr')
            
            for row in rows:
                if not isinstance(row, Tag):
                    continue
                    
                # Saltar filas de header y separadores
                if (row.find('th') or 
                    row.find('td', {'class': 'extrarow'}) or
                    'thead' in str(row.get('class', None))):
                    continue
                
                cells = row.find_all('td')
                if len(cells) < 6:  # Mínimo de columnas esperadas
                    continue
                
                try:
                    # Filter to ensure only Tag objects are passed
                    valid_cells = [cell for cell in cells if isinstance(cell, Tag)]
                    injury = self._parse_injury_row(valid_cells, team)
                    if injury:
                        injuries.append(injury)
                        self.logger.debug(f"Lesión extraída: {injury['player_name']} - {injury['injury_type']}")
                
                except Exception as e:
                    self.logger.warning(f"Error procesando fila de lesión: {e}")
                    continue
        
        except Exception as e:
            self.logger.error(f"Error extrayendo lesiones de {team['name']}: {e}")
        
        self.logger.info(f"Lesiones extraídas de {team['name']}: {len(injuries)}")
        return injuries
    
    def _parse_injury_row(self, cells: Sequence[Tag], team: Dict) -> Optional[Dict]:
        """
        Parsea una fila de lesión para extraer información.
        
        Args:
            cells: Lista de celdas de la fila
            team: Información del equipo
            
        Returns:
            Diccionario con información de la lesión o None
        """
        try:
            # Extraer nombre del jugador (primera celda)
            player_cell = cells[0]
            player_name = 'Desconocido'
            position = 'Desconocida'
            
            if isinstance(player_cell, Tag):
                # Buscar nombre en enlace
                player_link = player_cell.find('a')
                if player_link and isinstance(player_link, Tag):
                    player_name = (player_link.get('title') or 
                        player_link.get_text(strip=True) or 
                        'Desconocido')
                
                # Buscar posición en tabla interna
                inline_table = player_cell.find('table')
                if inline_table and isinstance(inline_table, Tag):
                    rows = inline_table.find_all('tr')
                    if len(rows) > 1:
                        position_row = rows[1]
                        if isinstance(position_row, Tag):
                            position_cell = position_row.find('td')
                            if position_cell:
                                position = position_cell.get_text(strip=True)
            
            # Extraer otros campos con manejo de errores
            field_map = {
                1: 'age',
                2: 'injury_type', 
                3: 'date_from',
                4: 'date_until',
                5: 'days',
                6: 'market_value'
            }
            
            extracted_data = {}
            for i, field in field_map.items():
                if i < len(cells):
                    if field == 'days':
                        # Para días, buscar en enlaces también
                        extracted_data[field] = self._extract_number_from_cell(cells[i])
                    else:
                        extracted_data[field] = self._extract_text(cells[i])
                else:
                    extracted_data[field] = ''
            
            # Crear registro de lesión
            injury = {
                'player_name': str(player_name).strip(),
                'team': team['name'],
                'team_id': team['id'],
                'position': str(position).strip(),
                'age': self._parse_age(extracted_data.get('age', '')),
                'injury_type': self._clean_injury_type(extracted_data.get('injury_type', '')),
                'date_from': extracted_data.get('date_from', ''),
                'date_until': extracted_data.get('date_until', ''),
                'days': self._parse_number(extracted_data.get('days', '')),
                'market_value': self._parse_market_value(extracted_data.get('market_value', '')),
                'extracted_at': datetime.now().isoformat()
            }
            
            # Validar datos mínimos
            if injury['player_name'] == 'Desconocido' and not injury['injury_type']:
                return None
            
            return injury
            
        except Exception as e:
            self.logger.warning(f"Error parseando fila de lesión: {e}")
            return None
    
    # Métodos auxiliares mejorados
    
    def _extract_text(self, cell) -> str:
        """Extrae texto limpio de una celda."""
        if not cell or not isinstance(cell, Tag):
            return ''
        return cell.get_text(strip=True)
    
    def _extract_number_from_cell(self, cell) -> str:
        """Extrae número de una celda, incluyendo enlaces."""
        if not cell or not isinstance(cell, Tag):
            return '0'
        
        # Primero buscar en enlaces
        link = cell.find('a')
        if link:
            link_text = link.get_text(strip=True)
            if link_text and link_text.isdigit():
                return link_text
        
        # Luego buscar en texto general
        cell_text = cell.get_text(strip=True)
        numbers = re.findall(r'\d+', cell_text)
        return numbers[0] if numbers else '0'
    
    def _parse_age(self, age_str: str) -> int:
        """Convierte string de edad a entero."""
        try:
            # Buscar cualquier número en el string
            numbers = re.findall(r'\d+', str(age_str))
            if numbers:
                age = int(numbers[0])
                # Validar rango razonable
                if 15 <= age <= 50:
                    return age
            return 0
        except:
            return 0
    
    def _parse_number(self, number_str: str) -> int:
        """Convierte string a número entero."""
        try:
            numbers = re.findall(r'\d+', str(number_str))
            return int(numbers[0]) if numbers else 0
        except:
            return 0
    
    def _parse_market_value(self, value_str: str) -> int:
        """Convierte valor de mercado a entero (euros)."""
        if not value_str:
            return 0
        
        try:
            # Limpiar string
            clean_value = str(value_str).lower().strip()
            
            # Extraer números y multiplicadores
            if 'mill' in clean_value:
                numbers = re.findall(r'[\d,\.]+', clean_value)
                if numbers:
                    number = float(numbers[0].replace(',', '.'))
                    return int(number * 1000000)
                    
            elif any(word in clean_value for word in ['mil', 'tsd', 'k']):
                numbers = re.findall(r'[\d,\.]+', clean_value)
                if numbers:
                    number = float(numbers[0].replace(',', '.'))
                    return int(number * 1000)
            else:
                # Valor directo
                numbers = re.findall(r'\d+', clean_value)
                return int(numbers[0]) if numbers else 0
                
        except:
            return 0
            
        return 0  # Default return if no other path matches
    
    def _clean_injury_type(self, injury_str: str) -> str:
        """Limpia y normaliza el tipo de lesión."""
        if not injury_str:
            return 'Desconocida'
        
        # Diccionario de normalización más completo
        injury_mapping = {
            'lesión de rodilla': 'Lesión de rodilla',
            'rotura del ligamento': 'Rotura de ligamento',
            'rotura de ligamento': 'Rotura de ligamento',
            'lesión muscular': 'Lesión muscular',
            'desgarro muscular': 'Desgarro muscular',
            'esguince': 'Esguince',
            'fractura': 'Fractura',
            'contusión': 'Contusión',
            'tendinitis': 'Tendinitis',
            'sobrecarga': 'Sobrecarga muscular',
            'rotura fibrilar': 'Rotura fibrilar'
        }
        
        injury_lower = str(injury_str).lower().strip()
        
        # Buscar coincidencias
        for key, value in injury_mapping.items():
            if key in injury_lower:
                return value
        
        # Si no encuentra coincidencia, limpiar y capitalizar
        cleaned = str(injury_str).strip()
        return cleaned.capitalize() if cleaned else 'Desconocida'
    
    def extract_all_injuries(self, force_refresh: bool = False) -> List[Dict]:
        """
        Extrae lesiones de todos los equipos de la liga - VERSIÓN MEJORADA.
        
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
                        self.logger.info(f"Usando lesiones desde cache: {len(cached_data['injuries'])} lesiones")
                        return cached_data['injuries']
            except Exception as e:
                self.logger.warning(f"Error leyendo cache de lesiones: {e}")
        
        # Obtener lista de equipos
        teams = self.extract_teams(force_refresh=force_refresh)
        if not teams:
            self.logger.error("No se pudieron obtener equipos")
            return []
        
        all_injuries = []
        successful_teams = 0
        
        # Extraer lesiones de cada equipo
        for i, team in enumerate(teams, 1):
            self.logger.info(f"Procesando equipo {i}/{len(teams)}: {team['name']}")
            
            try:
                team_injuries = self.extract_team_injuries(team)
                all_injuries.extend(team_injuries)
                
                if team_injuries:
                    successful_teams += 1
                    
            except Exception as e:
                self.logger.error(f"Error procesando equipo {team['name']}: {e}")
                continue
            
            # Pausa entre equipos
            if i < len(teams):
                time.sleep(2)
        
        # Guardar en cache solo si obtuvimos datos
        if all_injuries:
            cache_data = {
                'timestamp': datetime.now().isoformat(),
                'total_teams': len(teams),
                'successful_teams': successful_teams,
                'total_injuries': len(all_injuries),
                'injuries': all_injuries
            }
            
            try:
                with open(self.injuries_cache_file, 'w', encoding='utf-8') as f:
                    json.dump(cache_data, f, ensure_ascii=False, indent=2)
                    self.logger.info(f"Lesiones guardadas en cache: {len(all_injuries)}")
            except Exception as e:
                self.logger.warning(f"Error guardando cache de lesiones: {e}")
        
        self.logger.info(f"Extracción completada: {len(all_injuries)} lesiones de {successful_teams}/{len(teams)} equipos")
        return all_injuries
    
    def get_cache_info(self) -> Dict:
        """Obtiene información sobre el cache."""
        info = {
            'teams_cache_exists': self.teams_cache_file.exists(),
            'injuries_cache_exists': self.injuries_cache_file.exists(),
            'teams_cache_size': 0,
            'injuries_cache_size': 0,
            'teams_cache_modified': None,
            'injuries_cache_modified': None,
            'teams_count': 0,
            'injuries_count': 0
        }
        
        # Información del cache de equipos
        if info['teams_cache_exists']:
            try:
                stat = self.teams_cache_file.stat()
                info['teams_cache_size'] = stat.st_size
                info['teams_cache_modified'] = datetime.fromtimestamp(stat.st_mtime).isoformat()
                
                with open(self.teams_cache_file, 'r', encoding='utf-8') as f:
                    teams_data = json.load(f)
                    info['teams_count'] = len(teams_data.get('teams', []))
            except:
                pass
        
        # Información del cache de lesiones
        if info['injuries_cache_exists']:
            try:
                stat = self.injuries_cache_file.stat()
                info['injuries_cache_size'] = stat.st_size
                info['injuries_cache_modified'] = datetime.fromtimestamp(stat.st_mtime).isoformat()
                
                with open(self.injuries_cache_file, 'r', encoding='utf-8') as f:
                    injuries_data = json.load(f)
                    info['injuries_count'] = len(injuries_data.get('injuries', []))
            except:
                pass
        
        return info
    
    def clear_cache(self):
        """Limpia el cache de equipos y lesiones."""
        cleared = []
        
        if self.teams_cache_file.exists():
            self.teams_cache_file.unlink()
            cleared.append("equipos")
        
        if self.injuries_cache_file.exists():
            self.injuries_cache_file.unlink()
            cleared.append("lesiones")
        
        if cleared:
            self.logger.info(f"Cache eliminado: {', '.join(cleared)}")
        else:
            self.logger.info("No había cache para eliminar")