import requests
import pandas as pd
import hashlib
import json
import os
import time
from datetime import datetime
from typing import Dict, Optional, Tuple
from pathlib import Path
from urllib.parse import quote
import logging
from dotenv import load_dotenv
load_dotenv()

# Configurar logger
logger = logging.getLogger(__name__)
class HongKongDataExtractor:
    """
    Extractor de datos para la Liga de Hong Kong desde GitHub.
    Maneja la descarga, verificación de cambios y cache inteligente.
    """
    
    def __init__(self, cache_dir: str = "data/cache"):
        """
        Inicializa el extractor.

        Args:
            cache_dir: Directorio para cache de datos
        """
        # Configuración de URLs (centralizada)
        # Repo renamed to SEA-Football-Data; HKPL files now live in hong_kong/ subfolder
        self.base_url = "https://raw.githubusercontent.com/josangl08/SEA-Football-Data/main/hong_kong"
        self.github_api_base = "https://api.github.com/repos/josangl08/SEA-Football-Data/contents/hong_kong"

        # Configuración de temporadas disponibles (nombres CORRECTOS del repo)
        # Formato: "hong_kong_YYYY_YY.csv"
        self.available_seasons = {
            "2025-26": "hong_kong_2025_26.csv",
            "2024-25": "hong_kong_2024_25.csv",
            "2023-24": "hong_kong_2023_24.csv",
            "2022-23": "hong_kong_2022_23.csv",
            "2021-22": "hong_kong_2021_22.csv",
            "2020-21": "hong_kong_2020_21.csv",
            "2019-20": "hong_kong_2019_20.csv",
            "2018-19": "hong_kong_2018_19.csv"
        }
        
        # Configuración de cache
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True, parents=True)
        self.metadata_file = self.cache_dir / "metadata.json"
        
        # Cargar metadatos existentes
        self.metadata = self._load_metadata()
        self.headers = {
        'User-Agent': 'HongKongLeagueDataExtractor/1.0',
        'Accept': 'application/vnd.github.v3+json'
        }
        # Añadir token si está disponible
        self.github_token = os.getenv("GITHUB_TOKEN")
        if self.github_token:
            self.headers["Authorization"] = f"token {self.github_token}"
            logger.info("Token de GitHub configurado correctamente")
        else:
            logger.warning("No se encontró un token de GitHub. Se usarán límites de API reducidos.")

        # Auto-detectar temporadas nuevas del repositorio
        self._auto_discover_seasons()
    
    def _load_metadata(self) -> Dict:
        """Carga metadatos del cache local."""
        if self.metadata_file.exists():
            try:
                with open(self.metadata_file, 'r') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                logger.error("Error leyendo metadatos, creando nuevos...")
        return {}
    
    def _save_metadata(self):
        """Guarda metadatos en el cache local."""
        with open(self.metadata_file, 'w') as f:
            json.dump(self.metadata, f, indent=2, default=str)

    def _auto_discover_seasons(self):
        """
        Auto-descubre temporadas nuevas del repositorio de GitHub.
        Actualiza self.available_seasons con archivos encontrados.

        Formato esperado: hong_kong_YYYY_YY.csv
        """
        if not self.github_token:
            logger.debug("Sin token de GitHub, saltando auto-descubrimiento")
            return

        try:
            import re

            response = requests.get(
                self.github_api_base,
                headers=self.headers,
                timeout=5
            )

            if response.status_code != 200:
                logger.debug(
                    f"No se pudo acceder al repo para auto-descubrimiento "
                    f"(status: {response.status_code})"
                )
                return

            files = response.json()

            # Patrón: hong_kong_2024_25.csv -> extraer "2024" y "25"
            # Resultado esperado: "2024-25"
            pattern = re.compile(r'hong_kong_(\d{4})_(\d{2})\.csv')

            discovered_count = 0
            for file_info in files:
                if not isinstance(file_info, dict):
                    continue

                filename = file_info.get('name', '')
                match = pattern.match(filename)

                if match:
                    year_full = match.group(1)  # "2024"
                    year_short = match.group(2)  # "25"
                    # Formato esperado: "2024-25"
                    season_format = f"{year_full}-{year_short}"

                    # Añadir si NO existe (evita duplicados)
                    if season_format not in self.available_seasons:
                        self.available_seasons[season_format] = filename
                        logger.info(
                            f"✓ Nueva temporada descubierta: {season_format} "
                            f"({filename})"
                        )
                        discovered_count += 1

            if discovered_count > 0:
                logger.info(
                    f"Auto-descubrimiento completado: "
                    f"{discovered_count} temporada(s) nueva(s) encontrada(s)"
                )
            else:
                logger.debug("Auto-descubrimiento: sin temporadas nuevas")

        except Exception as e:
            logger.debug(
                f"Error en auto-descubrimiento (no crítico): {e}"
            )

    def _detect_current_season(self) -> str:
        """
        Auto-detecta la temporada actual basándose en la fecha del sistema.

        Lógica:
        - Las temporadas de fútbol empiezan en agosto (mes 8)
        - Si mes >= 8: temporada actual = YYYY-(YY+1)
        - Si mes < 8: temporada actual = (YYYY-1)-YY

        Ejemplos:
        - Agosto 2025 → "2025-26"
        - Julio 2025 → "2024-25"
        - Noviembre 2024 → "2024-25"
        - Febrero 2025 → "2024-25"

        Returns:
            str: Temporada en formato "YYYY-YY" (ej: "2024-25")
        """
        now = datetime.now()
        year = now.year
        month = now.month

        # Las temporadas comienzan en agosto (mes 8)
        if month >= 8:
            start_year = year
            end_year = year + 1
        else:
            start_year = year - 1
            end_year = year

        season = f"{start_year}-{str(end_year)[-2:]}"
        logger.debug(
            f"Temporada actual detectada: {season} "
            f"(fecha: {now.strftime('%Y-%m-%d')})"
        )
        return season

    def _get_season_with_fallback(
        self,
        season: Optional[str] = None
    ) -> Tuple[str, bool, str]:
        """
        Obtiene temporada con fallback inteligente para pre-temporada.

        Si la temporada detectada automáticamente no tiene datos en GitHub
        (ej: es agosto 2025 pero aún no hay datos de 2025-26), hace fallback
        a la temporada anterior.

        Args:
            season: Temporada específica o None para auto-detectar

        Returns:
            Tuple[str, bool, str]:
                - season: Temporada a usar
                - is_fallback: True si se usó fallback
                - message: Mensaje explicativo
        """
        # Si no se especifica, detectar automáticamente
        if season is None:
            season = self._detect_current_season()

        # Validar que la temporada esté disponible
        if season in self.available_seasons:
            # Verificar si realmente tiene datos descargables
            filename = self.available_seasons[season]
            github_info = self._get_github_file_info(filename)

            if github_info:
                return (
                    season,
                    False,
                    f"Temporada {season} disponible con datos"
                )
            else:
                # GitHub info no disponible, verificar cache local
                cached_file = self._get_cached_file_path(season)
                if cached_file.exists():
                    return (
                        season,
                        False,
                        f"Temporada {season} disponible en cache local"
                    )

        # Fallback: usar temporada anterior
        logger.warning(
            f"Temporada {season} sin datos disponibles, "
            f"usando fallback a temporada anterior"
        )

        # Calcular temporada anterior
        try:
            year_start = int(season.split('-')[0])
            prev_season = f"{year_start-1}-{str(year_start)[-2:]}"

            if prev_season in self.available_seasons:
                return (
                    prev_season,
                    True,
                    f"Pre-temporada: usando {prev_season} (temporada anterior)"
                )
        except (ValueError, IndexError):
            pass

        # Si todo falla, devolver la temporada original
        return (
            season,
            False,
            f"Usando temporada {season} sin verificación"
        )

    def _get_finished_seasons(
        self,
        current_season: Optional[str] = None
    ) -> list:
        """
        Auto-genera lista de temporadas finalizadas.

        Una temporada se considera "finalizada" si es anterior a la
        temporada actual. Las temporadas finalizadas son INMUTABLES
        y no necesitan verificación de actualizaciones en GitHub.

        Args:
            current_season: Temporada actual o None para auto-detectar

        Returns:
            List[str]: Lista de temporadas finalizadas en orden descendente
                      (ej: ["2023-24", "2022-23", "2021-22", ...])
        """
        if current_season is None:
            current_season = self._detect_current_season()

        # Extraer año de inicio de la temporada actual
        try:
            current_year = int(current_season.split('-')[0])
        except (ValueError, IndexError):
            logger.error(
                f"Formato inválido de temporada: {current_season}"
            )
            return []

        # Filtrar temporadas anteriores a la actual
        finished = []
        for season in self.available_seasons.keys():
            try:
                season_year = int(season.split('-')[0])
                if season_year < current_year:
                    finished.append(season)
            except (ValueError, IndexError):
                continue

        # Ordenar en orden descendente (más reciente primero)
        finished.sort(reverse=True)

        logger.debug(
            f"Temporadas finalizadas detectadas: {len(finished)} "
            f"(anterior a {current_season})"
        )

        return finished

    def _calculate_file_hash(self, content: str) -> str:
        """Calcula hash SHA256 del contenido del archivo."""
        return hashlib.sha256(content.encode('utf-8')).hexdigest()
    
    def _get_github_file_info(self, filename: str) -> Optional[Dict]:
        """
        Obtiene información del archivo desde la API de GitHub.

        Args:
            filename: Nombre del archivo CSV

        Returns:
            Diccionario con información del archivo o None si hay error
        """
        try:
            # URL-encode el nombre del archivo para manejar caracteres especiales
            encoded_filename = quote(filename)
            api_url = f"{self.github_api_base}/{encoded_filename}"

            headers = self.headers.copy()
            headers['User-Agent'] = 'HongKongLeagueDataExtractor/1.0'

            # Implementar retroceso exponencial
            max_retries = 3
            retry_delay = 2

            for retry in range(max_retries):
                try:
                    if retry > 0:
                        logger.info(
                            f"Intento {retry+1} de {max_retries} "
                            f"para acceder a GitHub API..."
                        )
                        time.sleep(retry_delay * (2**retry))

                    response = requests.get(api_url, headers=headers, timeout=10)

                    if response.status_code == 200:
                        file_info = response.json()
                        result = {
                            'sha': file_info.get('sha'),
                            'size': file_info.get('size'),
                            'download_url': file_info.get('download_url')
                        }

                        logger.debug(f"✓ Info de GitHub obtenida para {filename}")
                        return result

                    elif response.status_code == 403:
                        rate_limit_remaining = response.headers.get(
                            'X-RateLimit-Remaining'
                        )
                        if rate_limit_remaining and int(rate_limit_remaining) == 0:
                            reset_time = int(
                                response.headers.get('X-RateLimit-Reset', 0)
                            )
                            reset_datetime = datetime.fromtimestamp(reset_time)
                            wait_time = (
                                reset_datetime - datetime.now()
                            ).total_seconds()
                            logger.warning(
                                f"Rate limit excedido. "
                                f"Se reiniciará en {wait_time/60:.1f} minutos"
                            )
                            break
                        else:
                            logger.error(
                                "Error de acceso a GitHub API: 403 - "
                                "Acceso denegado"
                            )
                    else:
                        logger.error(
                            f"Error accediendo a GitHub API: "
                            f"{response.status_code}"
                        )

                except requests.RequestException as e:
                    if retry == max_retries - 1:
                        logger.error(f"Error conectando a GitHub API: {e}")

            # Si llegamos aquí, todos los intentos fallaron
            logger.warning(
                f"No se pudo obtener info de GitHub para {filename}"
            )
            return None

        except Exception as e:
            logger.error(f"Error inesperado accediendo a GitHub API: {e}")
            return None
        
    
    def _download_csv_content(self, filename: str) -> Optional[str]:
        """
        Descarga el contenido del archivo CSV.
        
        Args:
            filename: Nombre del archivo CSV
            
        Returns:
            Contenido del archivo como string o None si hay error
        """
        try:
            file_url = f"{self.base_url}/{filename}"
            logger.info(f"Descargando archivo CSV desde: {file_url}")
            
            response = requests.get(file_url, headers=self.headers, timeout=30)
            response.raise_for_status()
            
            logger.info(f"Archivo {filename} descargado exitosamente ({len(response.text)} bytes)")
            return response.text
            
        except requests.RequestException as e:
            logger.error(f"Error descargando {filename}: {e}")
            return None
    
    def _get_cached_file_path(self, season: str) -> Path:
        """Retorna la ruta del archivo en cache para una temporada."""
        return self.cache_dir / f"hong_kong_{season.replace('-', '_')}.csv"
    
    def check_for_updates(
        self,
        season: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        Verifica si hay actualizaciones disponibles para una temporada.
        Prioriza la comparación de SHA de GitHub para mayor fiabilidad.

        OPTIMIZACIÓN: Las temporadas finalizadas son INMUTABLES - no
        verificar GitHub.

        Args:
            season: Temporada a verificar o None para auto-detectar

        Returns:
            Tuple[bool, str]: (needs_update, message)
        """
        # Auto-detectar temporada actual si no se especifica
        if season is None:
            season = self._detect_current_season()
            logger.info(f"Temporada auto-detectada: {season}")

        # Auto-generar lista de temporadas finalizadas
        current_season = self._detect_current_season()
        finished_seasons = self._get_finished_seasons(current_season)

        # Temporadas finalizadas: solo verificar si existe en cache
        if season in finished_seasons:
            cached_file = self._get_cached_file_path(season)
            if cached_file.exists():
                logger.debug(
                    f"Temporada {season} finalizada - usando cache local"
                )
                return (
                    False,
                    f"Temporada {season} finalizada - usando cache local "
                    f"(sin verificar GitHub)"
                )
            else:
                logger.info(
                    f"Temporada {season} finalizada pero no en cache - "
                    f"descarga única"
                )
                return (
                    True,
                    f"Temporada {season} no en cache - descarga única "
                    f"requerida"
                )

        # Temporada actual o futura: verificación normal con GitHub API
        if season not in self.available_seasons:
            logger.warning(f"Temporada {season} no está disponible")
            return False, f"La temporada {season} no está disponible."

        filename = self.available_seasons[season]
        cached_file = self._get_cached_file_path(season)

        if not cached_file.exists():
            return True, "Datos no encontrados en cache, se requiere descarga."

        # Obtener metadatos de GitHub SOLO para temporada actual
        github_info = self._get_github_file_info(filename)
        if not github_info or not github_info.get('sha'):
            return False, "No se pudo verificar el estado en GitHub; se asume actualizado."

        # Comparar SHA de GitHub con los metadatos locales
        season_key = f"hong_kong_{season}"
        local_metadata = self.metadata.get(season_key, {})
        local_sha = local_metadata.get('github_sha')

        if local_sha and local_sha == github_info['sha']:
            return False, "Los datos locales coinciden con la versión de GitHub (SHA)."

        if not local_sha:
            return True, "No se encontró SHA local; se recomienda actualizar."

        return True, "El SHA de GitHub no coincide con el local; se necesita actualizar."
    
    def download_season_data(
        self,
        season: Optional[str] = None,
        force_update: bool = False
    ) -> Optional[pd.DataFrame]:
        """
        Descarga datos de una temporada específica.

        Args:
            season: Temporada a descargar o None para auto-detectar
            force_update: Forzar descarga aunque no haya cambios

        Returns:
            DataFrame con los datos o None si hay error
        """
        # Auto-detectar temporada actual si no se especifica
        if season is None:
            season = self._detect_current_season()
            logger.info(f"Temporada auto-detectada para descarga: {season}")

        if season not in self.available_seasons:
            logger.info(f"Temporada {season} no disponible")
            return None
        
        filename = self.available_seasons[season]
        season_key = f"hong_kong_{season}"
        cached_file = self._get_cached_file_path(season)
        
        # Verificar si necesitamos actualizar
        if not force_update and cached_file.exists():
            needs_update, message = self.check_for_updates(season)
            if not needs_update:
                logger.info(f"Usando datos en cache: {message}")
                return pd.read_csv(cached_file)
        
        # Descargar archivo
        logger.info(f"Descargando datos de {season}...")
        content = self._download_csv_content(filename)
        
        if content is None:
            logger.error(f"Error descargando {filename}")
            # Intentar usar cache si existe
            if cached_file.exists():
                logger.info("Usando datos en cache por error de descarga")
                return pd.read_csv(cached_file)
            return None
        
        # Procesar y guardar
        try:
            # Guardar en cache
            with open(cached_file, 'w', encoding='utf-8') as f:
                f.write(content)
            
            # Actualizar metadatos
            github_info = self._get_github_file_info(filename)
            self.metadata[season_key] = {
                'last_updated': datetime.now().isoformat(),
                'file_size': len(content.encode('utf-8')),
                'file_hash': self._calculate_file_hash(content),
                'github_sha': github_info.get('sha') if github_info else None,
                'season': season,
                'filename': filename
            }
            self._save_metadata()
            
            # Convertir a DataFrame
            from io import StringIO
            df = pd.read_csv(StringIO(content))
            
            logger.info(f"✓ Datos de {season} descargados exitosamente ({len(df)} registros)")
            return df
            
        except Exception as e:
            logger.error(f"Error procesando datos de {season}: {e}")
            return None
    
    def get_available_seasons(self) -> list:
        """Retorna lista de temporadas disponibles."""
        return list(self.available_seasons.keys())
    
    def get_cache_info(self, season: Optional[str] = None) -> Dict:
        """
        Retorna información del cache.
        
        Args:
            season: Temporada específica o None para todas
            
        Returns:
            Diccionario con información del cache
        """
        if season:
            season_key = f"hong_kong_{season}"
            if season_key in self.metadata:
                return {season: self.metadata[season_key]}
            return {}
        
        return self.metadata
    
    
    def clear_cache(self, season: Optional[str] = None):
        """
        Limpia el cache de una temporada específica o todo.
        
        Args:
            season: Temporada específica o None para limpiar todo
        """
        if season:
            season_key = f"hong_kong_{season}"
            cached_file = self._get_cached_file_path(season)
            
            # Eliminar archivo
            if cached_file.exists():
                cached_file.unlink()
            
            # Eliminar metadatos
            if season_key in self.metadata:
                del self.metadata[season_key]
                self._save_metadata()
            
            logger.info(f"Cache de {season} eliminado")
        else:
            # Limpiar todo
            for file in self.cache_dir.glob("hong_kong_*.csv"):
                file.unlink()
            
            self.metadata.clear()
            self._save_metadata()
            logger.info("Todo el cache eliminado")
