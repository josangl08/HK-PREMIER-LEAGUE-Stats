# ABOUTME: Refactored DataManager using SQLAlchemy for performance and consistency.
# ABOUTME: Maintains compatibility with existing aggregators by providing DataFrames.

import pandas as pd
import logging
from typing import Dict, List, Optional
from datetime import datetime
from sqlalchemy import select, and_
from sqlalchemy.orm import Session

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
        
        # TTLs del cache
        self.cache_ttl = {
            'league_stats': 1800,
            'team_stats': 1800,
            'player_stats': 1800,
            'chart_data': 900
        }

        if auto_load:
            self.refresh_data()

    def refresh_data(self, season: Optional[str] = None, force_download: bool = False) -> bool:
        """
        Prepara el agregador con los datos de la temporada seleccionada desde SQL.
        """
        target_season = season or self.current_season
        logger.info(f"Refrescando datos para la temporada {target_season} desde SQL...")
        
        try:
            # 1. Obtener datos de la base de datos
            df = self._load_season_dataframe(target_season)
            
            if df.empty:
                logger.warning(f"No hay datos en SQL para la temporada {target_season}")
                return False
            
            # 2. Procesar datos (Normalización y Limpieza)
            # Esto crea las columnas faltantes como Position_Group y Tackles per 90
            df = self.processor.process_season_data(df, target_season)
            
            # 3. Inicializar el agregador usando el DataFrame procesado
            self.aggregator = HongKongStatsAggregator(df)
            self.current_season = target_season
            
            # 4. Limpiar cache de la temporada anterior
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
                select(PlayerSeasonStat, Player.name, Team.name.label("team_name"))
                .join(Player, PlayerSeasonStat.player_id == Player.id)
                .outerjoin(Team, Player.current_team_id == Team.id)
                .where(PlayerSeasonStat.season_id == season_id)
            )
            
            results = session.execute(stmt).all()
            
            data_list = []
            for stat_obj, player_name, team_name in results:
                # Combinar core metrics con advanced metrics del JSON
                row = {
                    "Player": player_name,
                    "Team": team_name or "Unknown",
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
