# ABOUTME: Refactored DataManager using SQLAlchemy for performance and consistency.
# ABOUTME: Maintains compatibility with existing aggregators by providing DataFrames.

import json
import logging
import pandas as pd
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional
from sqlalchemy import select

# Importar componentes de base de datos
from models.db_models import Player, Team, Season, PlayerSeasonStat, SystemSyncLog
from utils.db_engine import SessionFactory
from utils.common import get_current_season
from utils.cache_manager import AdvancedCacheManager

# Importar agregador y procesador
from data.processors.hong_kong_processor import HongKongDataProcessor
from data.aggregators.hong_kong_aggregator import HongKongStatsAggregator
from data.managers.fixture_manager import get_fixture_manager

logger = logging.getLogger(__name__)

_PROCESSED_CACHE_DIR = Path("cache/processed")


class HongKongDataManager:
    """
    Gestor de datos de la Liga de Hong Kong basado en SQL.
    Sustituye la dependencia de CSVs por consultas a la base de datos relacional.
    """

    def __init__(self, auto_load: bool = True):
        self.current_season = get_current_season()
        self.aggregator: Optional[HongKongStatsAggregator] = None
        self.advanced_cache = AdvancedCacheManager()
        self.processor = HongKongDataProcessor()
        _PROCESSED_CACHE_DIR.mkdir(parents=True, exist_ok=True)

        # TTLs del cache
        self.cache_ttl = {
            'league_stats': 1800,
            'team_stats': 1800,
            'player_stats': 1800,
            'chart_data': 900
        }

        if auto_load:
            self.refresh_data()

    # ── Processed DataFrame disk cache ────────────────────────────────────────

    def _cache_path(self, season: str) -> Path:
        return _PROCESSED_CACHE_DIR / f"{season}.parquet"

    def _meta_path(self, season: str) -> Path:
        return _PROCESSED_CACHE_DIR / f"{season}.meta.json"

    def _get_db_last_run(self, season: str) -> Optional[str]:
        """Returns the ISO timestamp of the last successful HKPL sync for this season, or None."""
        session = SessionFactory()
        try:
            stmt = (
                select(SystemSyncLog.last_run)
                .where(SystemSyncLog.task_name == f"hkpl_sync_{season}")
                .where(SystemSyncLog.status == "SUCCESS")
            )
            result = session.execute(stmt).scalar_one_or_none()
            return result.isoformat() if result else None
        except Exception:
            return None
        finally:
            session.close()

    def _load_from_cache(self, season: str) -> Optional[pd.DataFrame]:
        """Loads processed DataFrame from disk if the DB data hasn't changed since caching."""
        cache_file = self._cache_path(season)
        meta_file = self._meta_path(season)
        if not cache_file.exists() or not meta_file.exists():
            return None
        try:
            meta = json.loads(meta_file.read_text())
            db_last_run = self._get_db_last_run(season)
            if meta.get("db_last_run") == db_last_run:
                df = pd.read_parquet(cache_file)
                logger.info(f"✓ Datos procesados cargados desde caché de disco para {season} ({len(df)} jugadores)")
                return df
        except Exception as e:
            logger.debug(f"Cache miss for {season}: {e}")
        return None

    def _save_to_cache(self, season: str, df: pd.DataFrame) -> None:
        """Persists processed DataFrame and current DB sync timestamp to disk."""
        try:
            df.to_parquet(self._cache_path(season), index=False)
            meta = {"db_last_run": self._get_db_last_run(season), "cached_at": datetime.now(timezone.utc).isoformat()}
            self._meta_path(season).write_text(json.dumps(meta))
        except Exception as e:
            logger.debug(f"Could not save processed cache for {season}: {e}")

    # ── Main refresh ───────────────────────────────────────────────────────────

    def refresh_data(self, season: Optional[str] = None, force_download: bool = False) -> bool:
        """
        Prepara el agregador con los datos de la temporada seleccionada desde SQL.
        Usa caché de disco si los datos no han cambiado desde el último procesamiento.
        """
        target_season = season or self.current_season

        try:
            # 1. Intentar cargar desde caché de disco (evita reprocesamiento)
            if not force_download:
                df = self._load_from_cache(target_season)
                if df is not None:
                    self.aggregator = HongKongStatsAggregator(df)
                    self.current_season = target_season
                    return True

            logger.info(f"Refrescando datos para la temporada {target_season} desde SQL...")

            # 2. Obtener datos de la base de datos
            df = self._load_season_dataframe(target_season)
            if df.empty:
                logger.warning(f"No hay datos en SQL para la temporada {target_season}")
                return False

            # 3. Procesar datos (Normalización, métricas derivadas)
            df = self.processor.process_season_data(df, target_season)

            # 4. Persistir en caché de disco para el próximo startup
            self._save_to_cache(target_season, df)

            # 5. Inicializar el agregador
            self.aggregator = HongKongStatsAggregator(df)
            self.current_season = target_season

            # 6. Limpiar cache de la temporada anterior
            self.advanced_cache.clear()

            logger.info(f"✓ Agregador listo y normalizado para {target_season} ({len(df)} jugadores)")
            return True

        except Exception as e:
            logger.error(f"Error al refrescar datos desde SQL: {e}")
            import traceback; traceback.print_exc()
            return False

    def _load_season_dataframe(self, season_id: str) -> pd.DataFrame:
        """
        Carga los datos de una temporada desde SQL y los convierte a DataFrame
        con el formato exacto que espera el HongKongStatsAggregator.
        """
        session = SessionFactory()
        try:
            # Consulta: Unir Estadísticas con Jugadores y Equipos
            stmt = (
                select(PlayerSeasonStat, Player.name, Player.position_main, Team.name.label("team_name"))
                .join(Player, PlayerSeasonStat.player_id == Player.id)
                .outerjoin(Team, Player.current_team_id == Team.id)
                .where(PlayerSeasonStat.season_id == season_id)
            )

            results = session.execute(stmt).all()

            data_list = []
            for stat_obj, player_name, position_main, team_name in results:
                # Core metrics
                row = {
                    "Player": player_name,
                    "Season": stat_obj.season_id,
                    "Matches played": stat_obj.matches_played,
                    "Minutes played": stat_obj.minutes_played,
                    "Goals": stat_obj.goals,
                    "Assists": stat_obj.assists,
                    "Yellow cards": stat_obj.yellow_cards,
                    "Red cards": stat_obj.red_cards
                }

                # Añadir métricas avanzadas del campo JSON
                if stat_obj.advanced_stats:
                    row.update(stat_obj.advanced_stats)

                # Robust Team Name Resolution
                # Confirmation: Team within selected timeframe is the team where they started the season.
                # Team is the team at the moment of the CSV.
                json_team = row.get("Team within selected timeframe")
                
                final_team = team_name # From DB join (current team)
                
                # For historical seasons, prioritize the record's team
                if json_team and str(json_team) not in ("0.0", "0", "nan", "None"):
                    final_team = str(json_team)
                elif not final_team or final_team == "Unknown" or final_team == "0.0":
                    final_team = "Unknown Team"
                
                row["Team"] = final_team

                # Posición confirmada (TM o migración): actúa como override cuando la
                # posición del CSV es una lista ambigua de múltiples valores.
                if position_main:
                    row["Position_Confirmed"] = position_main

                data_list.append(row)
            
            return pd.DataFrame(data_list)
            
        finally:
            session.close()

    # ── MÉTODOS DE COMPATIBILIDAD (Delegados al agregador o SQL) ────────────────

    def get_league_statistics(self, position: str = None, age_range: List[int] = None) -> Dict:
        if not self.aggregator: return {}
        return self.aggregator.get_league_statistics(position, age_range)

    def get_team_statistics(self, team_name: str, position: str = None, age_range: List[int] = None) -> Dict:
        if not self.aggregator: return {}
        return self.aggregator.get_team_statistics(team_name, position, age_range)

    def get_player_overview(self, player_name: str, team_name: str = None) -> Dict:
        if not self.aggregator: return {}
        return self.aggregator.get_player_statistics(player_name, team_name)

    def get_chart_data(self, level: str, identifier: Optional[str] = None) -> Dict:
        if not self.aggregator: return {}
        return self.aggregator.get_comparative_data_for_charts(level, identifier)

    def get_available_teams(self) -> List[str]:
        session = SessionFactory()
        try:
            stmt = select(Team.name).order_by(Team.name)
            return [row[0] for row in session.execute(stmt).all()]
        finally:
            session.close()

    def get_available_players(self, team_name: Optional[str] = None) -> List[str]:
        session = SessionFactory()
        try:
            if team_name:
                stmt = select(Player.name).join(Team).where(Team.name == team_name).order_by(Player.name)
            else:
                stmt = select(Player.name).order_by(Player.name)
            return [row[0] for row in session.execute(stmt).all()]
        finally:
            session.close()

    def get_available_seasons(self) -> List[str]:
        session = SessionFactory()
        try:
            stmt = select(Season.id).order_by(Season.id.desc())
            return [row[0] for row in session.execute(stmt).all()]
        finally:
            session.close()

    def get_data_status(self) -> Dict:
        """Devuelve el estado de los datos basado en SQL."""
        session = SessionFactory()
        try:
            # Obtener última sincronización
            stmt = select(SystemSyncLog.last_run).where(SystemSyncLog.task_name.like('%hkpl%')).limit(1)
            last_run = session.execute(stmt).scalar_one_or_none()
            
            # Contar equipos y jugadores en la temporada actual
            player_count = session.query(PlayerSeasonStat).filter(PlayerSeasonStat.season_id == self.current_season).count()
            team_count = session.query(Team).count()
            
            return {
                'current_season': self.current_season,
                'available_seasons': self.get_available_seasons(),
                'last_update': last_run,
                'aggregator_available': self.aggregator is not None,
                'data_stats': {
                    'total_players': player_count,
                    'total_teams': team_count
                },
                'cached_seasons': self.get_available_seasons()
            }
        finally:
            session.close()

    def check_for_updates(self) -> Dict:
        # Por ahora, simplemente devolvemos que está al día
        return {'needs_update': False, 'message': 'Sistema basado en SQL al día'}

    def should_check_for_updates(self) -> bool:
        return False

    def get_next_fixture(self, team: str) -> Optional[dict]:
        return get_fixture_manager().get_next_fixture(team)

    @property
    def processed_data(self) -> Optional[pd.DataFrame]:
        """
        Exposes the processed player DataFrame from the underlying aggregator.
        Returns None if the aggregator has not been initialised (no data in DB).
        """
        return self.aggregator.data if self.aggregator is not None else None
