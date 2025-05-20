import requests
import pandas as pd
import hashlib
import json
import os
import time
from datetime import datetime
from typing import Dict, Optional, Tuple
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()


class HongKongDataExtractor:
    """
    Extractor de datos para la Liga de Hong Kong desde GitHub.
    Maneja la descarga, verificación de cambios y cache inteligente.
    """
    
    def __init__(self, cache_dir: str = "data/cache"):
        self.base_url = "https://raw.githubusercontent.com/griffisben/Wyscout_Prospect_Research/adabd2a3f30e739aa8a048aaf51c08cda248e5fe/Main%20App"
        self.github_api_base = "https://api.github.com/repos/griffisben/Wyscout_Prospect_Research/contents/Main%20App"
        
        # Configuración de temporadas disponibles
        self.available_seasons = {
            "2024-25": "Hong Kong Premier League 24-25.csv",
            "2023-24": "Hong Kong Premier League 23-24.csv", 
            "2022-23": "Hong Kong Premier League 22-23.csv",
            "2021-22": "Hong Kong Premier League 21-22.csv",
            "2020-21": "Hong Kong Premier League 20-21.csv",
            "2019-20": "Hong Kong Premier League 19-20.csv",
            "2018-19": "Hong Kong Premier League 18-19.csv"
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
            print("✅ Token de GitHub configurado correctamente")
        else:
            print("⚠️ No se encontró un token de GitHub. Se usarán límites de API reducidos.")
    
    def _load_metadata(self) -> Dict:
        """Carga metadatos del cache local."""
        if self.metadata_file.exists():
            try:
                with open(self.metadata_file, 'r') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                print("Error leyendo metadatos, creando nuevos...")
        return {}
    
    def _save_metadata(self):
        """Guarda metadatos en el cache local."""
        with open(self.metadata_file, 'w') as f:
            json.dump(self.metadata, f, indent=2, default=str)
    
    def _calculate_file_hash(self, content: str) -> str:
        """Calcula hash SHA256 del contenido del archivo."""
        return hashlib.sha256(content.encode('utf-8')).hexdigest()
    
    def _get_github_file_info(self, filename: str) -> Optional[Dict]:
        """
        Obtiene información del archivo desde la API de GitHub.
        Versión mejorada con mejor manejo de errores y caché.
        
        Args:
            filename: Nombre del archivo CSV
            
        Returns:
            Diccionario con información del archivo o None si hay error
        """
        # Verificar si tenemos esta información en caché
        cache_key = f"file_info_{filename}"
        cached_info_file = Path(self.cache_dir) / f"{cache_key}.json"
        
        # Usar caché si existe y no tiene más de 24 horas
        if cached_info_file.exists():
            try:
                file_age = datetime.now() - datetime.fromtimestamp(cached_info_file.stat().st_mtime)
                if file_age.total_seconds() < 24 * 3600:  # Menos de 24 horas
                    with open(cached_info_file, 'r') as f:
                        return json.load(f)
            except Exception:
                pass  # Si hay error leyendo el caché, intentar API
        
        try:
            api_url = f"{self.github_api_base}/{filename}"
            
            # Añadir encabezado User-Agent para evitar algunos bloqueos
            headers = self.headers.copy()
            headers['User-Agent'] = 'HongKongLeagueDataExtractor/1.0'
            
            # Implementar retroceso exponencial
            max_retries = 3
            retry_delay = 2  # segundos
            
            for retry in range(max_retries):
                try:
                    if retry > 0:
                        print(f"Intento {retry+1} de {max_retries} para acceder a GitHub API...")
                        time.sleep(retry_delay * (2**retry))  # Retroceso exponencial
                    
                    response = requests.get(api_url, headers=headers, timeout=10)
                    
                    if response.status_code == 200:
                        file_info = response.json()
                        result = {
                            'sha': file_info.get('sha'),
                            'size': file_info.get('size'),
                            'download_url': file_info.get('download_url'),
                            'last_modified': file_info.get('git_url')
                        }
                        
                        # Guardar en caché
                        with open(cached_info_file, 'w') as f:
                            json.dump(result, f)
                        
                        return result
                    elif response.status_code == 403:
                        rate_limit_remaining = response.headers.get('X-RateLimit-Remaining')
                        if rate_limit_remaining and int(rate_limit_remaining) == 0:
                            reset_time = int(response.headers.get('X-RateLimit-Reset', 0))
                            reset_datetime = datetime.fromtimestamp(reset_time)
                            wait_time = (reset_datetime - datetime.now()).total_seconds()
                            print(f"Rate limit excedido. Se reiniciará en {wait_time/60:.1f} minutos")
                            break  # No reintentar si es un problema de límite de tasa
                        else:
                            print(f"Error de acceso a GitHub API: 403 - Acceso denegado")
                    else:
                        print(f"Error accediendo a GitHub API: {response.status_code}")
                except requests.RequestException as e:
                    if retry == max_retries - 1:  # Último intento
                        print(f"Error conectando a GitHub API: {e}")
                    # Si no es el último intento, simplemente continuará con el siguiente
            
            # Si llegamos aquí, todos los intentos fallaron. Usar caché antiguo si existe
            if cached_info_file.exists():
                try:
                    with open(cached_info_file, 'r') as f:
                        print("Usando información en caché aunque sea antigua")
                        return json.load(f)
                except Exception:
                    pass
                    
            return None
                    
        except Exception as e:
            print(f"Error inesperado accediendo a GitHub API: {e}")
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
            response = requests.get(file_url, timeout=30)
            response.raise_for_status()
            
            return response.text
            
        except requests.RequestException as e:
            print(f"Error downloading {filename}: {e}")
            return None
    
    def _get_cached_file_path(self, season: str) -> Path:
        """Retorna la ruta del archivo en cache para una temporada."""
        return self.cache_dir / f"hong_kong_{season.replace('-', '_')}.csv"
    
    def check_for_updates(self, season: str = "2024-25") -> Tuple[bool, str]:
        """
        Verifica si hay actualizaciones disponibles para una temporada.
        
        Args:
            season: Temporada a verificar
            
        Returns:
            Tupla (needs_update: bool, message: str)
        """
        current_season = "2024-25"
        if season != current_season:
            return False, f"Temporada {season} archivada (no se actualizan temporadas anteriores)"
        
        if season not in self.available_seasons:
            return False, f"Temporada {season} no disponible"
        
        filename = self.available_seasons[season]
        season_key = f"hong_kong_{season}"
        
        # Obtener información actual del archivo en GitHub
        github_info = self._get_github_file_info(filename)
        if not github_info:
            return False, "No se pudo verificar el estado en GitHub"
        
        # Verificar si tenemos metadatos locales
        if season_key not in self.metadata:
            return True, "Primera descarga de la temporada"
        
        local_metadata = self.metadata[season_key]
        
        # Comparar SHA (más confiable)
        if 'github_sha' in local_metadata:
            if local_metadata['github_sha'] != github_info['sha']:
                return True, "Archivo actualizado en GitHub"
        
        # Comparar tamaño como verificación adicional
        if 'file_size' in local_metadata:
            if local_metadata['file_size'] != github_info['size']:
                return True, "Tamaño de archivo modificado"
        
        return False, "Archivo actualizado"
    
    def download_season_data(self, season: str = "2024-25", force_update: bool = False) -> Optional[pd.DataFrame]:
        """
        Descarga datos de una temporada específica.
        
        Args:
            season: Temporada a descargar
            force_update: Forzar descarga aunque no haya cambios
            
        Returns:
            DataFrame con los datos o None si hay error
        """
        if season not in self.available_seasons:
            print(f"Temporada {season} no disponible")
            return None
        
        filename = self.available_seasons[season]
        season_key = f"hong_kong_{season}"
        cached_file = self._get_cached_file_path(season)
        
        # Verificar si necesitamos actualizar
        if not force_update and cached_file.exists():
            needs_update, message = self.check_for_updates(season)
            if not needs_update:
                print(f"Usando datos en cache: {message}")
                return pd.read_csv(cached_file)
        
        # Descargar archivo
        print(f"Descargando datos de {season}...")
        content = self._download_csv_content(filename)
        
        if content is None:
            print(f"Error descargando {filename}")
            # Intentar usar cache si existe
            if cached_file.exists():
                print("Usando datos en cache por error de descarga")
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
            
            print(f"✓ Datos de {season} descargados exitosamente ({len(df)} registros)")
            return df
            
        except Exception as e:
            print(f"Error procesando datos de {season}: {e}")
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
            
            print(f"Cache de {season} eliminado")
        else:
            # Limpiar todo
            for file in self.cache_dir.glob("hong_kong_*.csv"):
                file.unlink()
            
            self.metadata.clear()
            self._save_metadata()
            print("Todo el cache eliminado")