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
        Extrae la lista de equipos de la liga
        
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
                rows = table.find_all('tr') if isinstance(table, Tag) else []
                for row in rows:
                    if not isinstance(row, Tag):
                        continue
                    
                    # Buscar células con enlaces de equipos
                    cells = row.find_all('td') if isinstance(row, Tag) else []
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
            self.logger.info(f"URL de lesiones: {team['injuries_url']}")
            
            # Extraer la sección de lesiones
            injuries_section = self._find_injuries_section(soup, team['name'])
            if not injuries_section:
                return []
            
            # Extraer la tabla de lesiones
            injury_table = self._find_injury_table(injuries_section, team['name'])
            if not injury_table:
                return []
            
            # Extraer las filas válidas
            valid_rows = self._extract_valid_rows(injury_table)
            self.logger.info(f"Total de filas encontradas: {len(valid_rows)}")
            
            # Procesar filas válidas
            for cells in valid_rows:
                try:
                    # Filter to ensure only Tag objects are passed
                    valid_cells = [cell for cell in cells if isinstance(cell, Tag)]
                    injury = self._parse_injury_row(valid_cells, team)
                    if injury:
                        injuries.append(injury)
                        self.logger.info(f"Lesión extraída: {injury['player_name']} - {injury['injury_type']}")
                
                except Exception as e:
                    self.logger.warning(f"Error procesando fila de lesión: {e}")
                    continue
            
        except Exception as e:
            self.logger.error(f"Error extrayendo lesiones de {team['name']}: {e}")
        
        self.logger.info(f"Lesiones extraídas de {team['name']}: {len(injuries)}")
        return injuries

    def _find_injuries_section(self, soup, team_name: str) -> Optional[Tag]:
        """Encuentra la sección de lesiones en la página."""
        try:
            # Buscar todos los encabezados de sección
            section_headers = soup.find_all('h2', {'class': 'content-box-headline'})
            
            # Buscar el encabezado de lesiones
            for header in section_headers:
                if 'Sanciones y lesiones' in header.get_text(strip=True):
                    # Encontrar la sección completa
                    return header.find_parent('div', {'class': 'box'})
            
            self.logger.warning(f"No se encontró sección de lesiones para {team_name}")
            return None
        except Exception as e:
            self.logger.error(f"Error buscando sección de lesiones: {e}")
            return None

    def _find_injury_table(self, injuries_section: Tag, team_name: str) -> Optional[Tag]:
        """Encuentra la tabla de lesiones dentro de la sección."""
        try:
            # Verificar si hay mensaje de "No hay datos"
            empty_message = injuries_section.find('span', {'class': 'empty'})
            if empty_message and "No hay datos" in empty_message.get_text(strip=True):
                self.logger.info(f"No hay lesiones para {team_name}")
                return None
            
            # Buscar tabla de lesiones dentro de la sección
            injury_table = injuries_section.find('table', {'class': 'items'})
            if not injury_table or not isinstance(injury_table, Tag):
                self.logger.warning(f"No se encontró tabla de lesiones para {team_name}")
                return None
            
            return injury_table if isinstance(injury_table, Tag) else None
        except Exception as e:
            self.logger.error(f"Error buscando tabla de lesiones: {e}")
            return None

    def _extract_valid_rows(self, injury_table: Tag) -> List[List[Tag]]:
        """Extrae las filas válidas de la tabla de lesiones."""
        try:
            rows = injury_table.find_all('tr')
            self.logger.info(f"Filas en la tabla principal: {len(rows)}")
            
            # Verificar si hay encabezado
            header_row = None
            for row in rows:
                if isinstance(row, Tag) and row.find('th') and len(row.find_all('th')) > 5:
                    header_row = row
                    break
            
            # Si no hay encabezado válido, puede no ser la tabla correcta
            if not header_row:
                self.logger.warning("No se encontró encabezado en la tabla")
                return []
            
            valid_rows = []
            # Procesar filas que no son encabezados
            for row in rows:
                if row == header_row or (isinstance(row, Tag) and row.find('th')):
                    continue
                    
                # Verificar si es la fila de "Lesiones"
                if isinstance(row, Tag) and row.find('td', {'class': 'extrarow'}) and "Lesiones" in row.get_text(strip=True):
                    continue
                
                # Obtener todas las celdas
                cells = row.find_all('td') if isinstance(row, Tag) else []
                if len(cells) >= 7:  # Asegurar que hay suficientes celdas
                    # Verificar que la primera celda tenga una tabla anidada con un jugador
                    first_cell = cells[0]
                    player_table = first_cell.find('table', {'class': 'inline-table'}) if isinstance(first_cell, Tag) else None
                    if isinstance(player_table, Tag) and player_table.find('a'):
                        valid_rows.append(cells)
                        # Log para depuración
                        if len(valid_rows) == 1:
                            self.logger.info(f"Primera fila de datos - Celdas: {len(cells)}")
            
            return valid_rows
        except Exception as e:
            self.logger.error(f"Error extrayendo filas válidas: {e}")
            return []
    
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
            # Extraer nombre del jugador y posición de la primera celda (columna 0)
            player_cell = cells[0]
            player_name = 'Desconocido'
            position = 'Desconocida'
            
            if isinstance(player_cell, Tag):
                # Buscar tabla anidada que contiene el nombre del jugador y posición
                inline_table = player_cell.find('table', {'class': 'inline-table'})
                if inline_table and isinstance(inline_table, Tag):
                    # Buscar el enlace del jugador
                    player_link = inline_table.find('a')
                    if player_link and isinstance(player_link, Tag):
                        player_name = player_link.get_text(strip=True) or 'Desconocido'
                    
                    position_cell = None

                    # Encontrar la celda de posición (segunda fila, única celda)
                    position_row = inline_table.find_all('tr')
                    if len(position_row) > 1:
                        second_row = position_row[1]
                        if isinstance(second_row, Tag):
                            position_cell = second_row.find('td')
                        if position_cell:
                            position = position_cell.get_text(strip=True) or 'Desconocida'
            
            # Extraer edad (columna 4)
            age = self._parse_age(cells[4].get_text(strip=True)) if len(cells) > 4 else 0
            
            # Extraer motivo/tipo de lesión (columna 5)
            injury_type = cells[5].get_text(strip=True) if len(cells) > 5 else 'Desconocida'
            
            # Extraer fecha desde (columna 6)
            date_from = cells[6].get_text(strip=True) if len(cells) > 6 else ''
            
            # Extraer fecha hasta (columna 7)
            date_until = cells[7].get_text(strip=True) if len(cells) > 7 else ''
            
            # Extraer encuentros no jugados (columna 8) - está dentro de un enlace
            matches_missed = 0
            if len(cells) > 8:
                missed_link = cells[8].find('a')
                if missed_link and isinstance(missed_link, Tag):
                    matches_missed = self._parse_number(missed_link.get_text(strip=True))
                else:
                    matches_missed = self._parse_number(cells[8].get_text(strip=True))
            
            # Extraer días (columna 9)
            days = self._parse_number(cells[9].get_text(strip=True)) if len(cells) > 9 else 0
            
            # Extraer valor de mercado (columna 10)
            market_value = self._parse_market_value(cells[10].get_text(strip=True)) if len(cells) > 10 else 0
            
            # Crear registro de lesión
            injury = {
                'player_name': str(player_name).strip(),
                'team': team['name'],
                'team_id': team['id'],
                'position': str(position).strip(),
                'age': age,
                'injury_type': injury_type,
                'date_from': date_from,
                'date_until': date_until,
                'matches_missed': matches_missed,
                'days': days,
                'market_value': market_value,
                'extracted_at': datetime.now().isoformat()
            }
            
            return injury
            
        except Exception as e:
            self.logger.warning(f"Error parseando fila de lesión: {e}")
            return None
    
    # Métodos auxiliar
    
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
    
    
    def extract_all_injuries(self, force_refresh: bool = False) -> List[Dict]:
        """
        Extrae lesiones de todos los equipos de la liga.
        -- DESACTIVADO TEMPORALMENTE --

        Args:
            force_refresh: Forzar actualización ignorando cache

        Returns:
            Lista vacía, ya que la funcionalidad está desactivada.
        """
        self.logger.info("La extracción de lesiones está desactivada. Saltando proceso.")
        return []

        # Código original comentado
        #
        # # 1. Verificar y usar caché si es posible
        # if not force_refresh:
        #     cached_data = self._try_load_from_cache()
        #     if cached_data:
        #         return cached_data
        #
        # # 2. Obtener lista de equipos
        # teams = self.extract_teams(force_refresh=force_refresh)
        # if not teams:
        #     self.logger.error("No se pudieron obtener equipos")
        #     return []
        #
        # # 3. Extraer lesiones de todos los equipos
        # all_injuries, successful_teams = self._extract_injuries_from_teams(teams)
        #
        # # 4. Guardar en caché si hay datos
        # if all_injuries:
        #     self._save_injuries_to_cache(all_injuries, teams, successful_teams)
        #
        # self.logger.info(f"Extracción completada: {len(all_injuries)} lesiones de {successful_teams}/{len(teams)} equipos")
        # return all_injuries

    def _try_load_from_cache(self) -> Optional[List[Dict]]:
        """Intenta cargar lesiones desde el caché."""
        if self.injuries_cache_file.exists():
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
        return None

    def _extract_injuries_from_teams(self, teams: List[Dict]) -> Tuple[List[Dict], int]:
        """Extrae lesiones de todos los equipos en la lista."""
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
        
        return all_injuries, successful_teams

    def _save_injuries_to_cache(self, injuries: List[Dict], teams: List[Dict], successful_teams: int):
        """Guarda las lesiones en el caché."""
        cache_data = {
            'timestamp': datetime.now().isoformat(),
            'total_teams': len(teams),
            'successful_teams': successful_teams,
            'total_injuries': len(injuries),
            'injuries': injuries
        }
        
        try:
            with open(self.injuries_cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
                self.logger.info(f"Lesiones guardadas en cache: {len(injuries)}")
        except Exception as e:
            self.logger.warning(f"Error guardando cache de lesiones: {e}")
    
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