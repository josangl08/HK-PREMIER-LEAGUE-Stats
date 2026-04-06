# ABOUTME: Refactored TransfermarktDataManager using SQLAlchemy for injuries and match history.
# ABOUTME: Maintains compatibility with existing dashboard components by providing required data formats.

import pandas as pd
import logging
import json
from typing import Dict, List, Optional
from datetime import datetime, timezone
from pathlib import Path
from sqlalchemy import select, and_, delete
from sqlalchemy.orm import joinedload

# Importar componentes de base de datos
from models.db_models import Injury, MatchHistory, Player, Team, SystemSyncLog
from utils.db_engine import SessionFactory
from utils.common import get_current_season

# Importar componentes ETL
from data.extractors.transfermarkt_extractor import TransfermarktExtractor
from data.processors.transfermarkt_processor import TransfermarktProcessor
from data.aggregators.transfermarkt_aggregator import TransfermarktStatsAggregator

# Configurar logging
logger = logging.getLogger(__name__)

class TransfermarktDataManager:
    """
    Gestor de datos de Transfermarkt (lesiones e historial) basado en SQL.
    Sustituye la dependencia de archivos JSON por consultas a la base de datos.
    """
    
    def __init__(self, cache_dir: str = "data/cache", auto_load: bool = True):
        self.extractor = TransfermarktExtractor(cache_dir)
        self.processor = TransfermarktProcessor()
        
        # Estado interno (mantener por compatibilidad si es necesario, pero priorizar SQL)
        self.processed_injuries = None
        self.aggregator = None
        
        if auto_load:
            self.refresh_data()

    def refresh_data(self, force_scraping: bool = False) -> bool:
        """
        Refresca los datos de lesiones e historial. 
        Si force_scraping es True, realiza el proceso ETL y guarda en SQL.
        Si es False, carga los datos directamente de SQL al agregador.
        """
        try:
            if force_scraping:
                logger.info("Iniciando proceso ETL forzado para Transfermarkt...")
                self._perform_full_etl()
            
            # Cargar datos desde SQL al agregador para asegurar que siempre estén frescos
            self.processed_injuries = self.get_injuries_data()
            
            if self.processed_injuries:
                self.aggregator = TransfermarktStatsAggregator(self.processed_injuries)
                logger.info(f"✓ Agregador de lesiones listo ({len(self.processed_injuries)} registros)")
                return True
            else:
                logger.warning("No hay datos de lesiones disponibles en SQL.")
                return False
                
        except Exception as e:
            logger.error(f"Error al refrescar datos de Transfermarkt: {e}")
            import traceback; traceback.print_exc()
            return False

    def refresh_player_data(self, player_id: str) -> bool:
        """Sincroniza el historial de un solo jugador para todas las temporadas disponibles."""
        from models.db_models import Season
        session = SessionFactory()
        try:
            player = session.get(Player, player_id)
            if not player or not player.tm_id:
                logger.warning(f"Jugador {player_id} no encontrado o sin tm_id.")
                return False
            
            # Obtener temporadas de forma segura
            seasons_stmt = select(Season.id)
            seasons = session.execute(seasons_stmt).scalars().all()
            
            updated = False
            for season_id in seasons:
                try:
                    logger.info(f"Scraping TM para {player.name} en {season_id}...")
                    raw_matches = self.extractor.get_match_history(str(player.tm_id), season_id)
                    if raw_matches:
                        self._upsert_history_to_sql(player.id, raw_matches)
                        updated = True
                except Exception as e:
                    logger.error(f"Error en refresh_player_data para {player.name} ({season_id}): {e}")
            
            return updated
        finally:
            session.close()

    def _perform_full_etl(self):
        """Ejecuta el ciclo de extracción, procesamiento y carga en DB."""
        # Obtener todos los jugadores representados o vinculados para sincronizar su historial
        session = SessionFactory()
        try:
            # Sincronizar historial para todos los jugadores con tm_id
            players = session.execute(select(Player).where(Player.tm_id.is_not(None))).scalars().all()
            
            # Obtener temporadas disponibles
            from models.db_models import Season
            seasons = session.execute(select(Season.id)).scalars().all()
            
            for player in players:
                logger.info(f"Sincronizando historial TM para: {player.name}...")
                for season_id in seasons:
                    try:
                        raw_matches = self.extractor.get_match_history(str(player.tm_id), season_id)
                        if raw_matches:
                            self._upsert_history_to_sql(player.id, raw_matches)
                    except Exception as e:
                        logger.error(f"Error sincronizando historial para {player.name} en {season_id}: {e}")
        finally:
            session.close()

        # Sincronizar lesiones (proceso existente - silenciado si no hay método en extractor)
        if hasattr(self.extractor, 'extract_all_injuries'):
            try:
                raw_injuries = self.extractor.extract_all_injuries(force_refresh=True)
                if raw_injuries:
                    df_processed = self.processor.process_injuries_data(raw_injuries)
                    if not df_processed.empty:
                        self._upsert_injuries_to_sql(df_processed)
            except Exception as e:
                logger.warning(f"No se pudieron sincronizar lesiones: {e}")
        
        # 4. Registrar éxito
        self._update_sync_log("transfermarkt_full_sync")

    def _upsert_history_to_sql(self, player_id: str, matches: List[Dict]):
        """Inserta o desarrolla el historial de partidos en SQL."""
        session = SessionFactory()
        try:
            for m in matches:
                # Intentar parsear fecha
                match_date = self._parse_date(m.get('date'))
                if not match_date: continue

                # Buscar duplicado por jugador, fecha y oponente
                existing = session.execute(
                    select(MatchHistory).where(
                        MatchHistory.player_id == player_id,
                        MatchHistory.date == match_date,
                        MatchHistory.opponent == m.get('opponent')
                    )
                ).scalar_one_or_none()

                if not existing:
                    history = MatchHistory(
                        player_id=player_id,
                        date=match_date,
                        competition_name=m.get('competition'),
                        competition_logo=m.get('competition_logo'),
                        opponent=m.get('opponent'),
                        result=m.get('result'),
                        minutes_played=m.get('minutes_played', 0),
                        goals=m.get('goals', 0),
                        assists=m.get('assists', 0),
                        yellow_cards=m.get('yellow_cards', 0),
                        red_cards=m.get('red_cards', 0),
                        position=m.get('position'),
                        status=m.get('status', 'Jugado'),
                        raw_data=m
                    )
                    session.add(history)
                else:
                    # Actualizar datos existentes
                    existing.minutes_played = m.get('minutes_played', 0)
                    existing.goals = m.get('goals', 0)
                    existing.assists = m.get('assists', 0)
                    existing.yellow_cards = m.get('yellow_cards', 0)
                    existing.red_cards = m.get('red_cards', 0)
                    existing.position = m.get('position')
                    existing.status = m.get('status', 'Jugado')
                    existing.raw_data = m
            
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Error upserting match history for {player_id}: {e}")
        finally:
            session.close()

    def _upsert_injuries_to_sql(self, df: pd.DataFrame):
        """Inserta o actualiza lesiones en la base de datos."""
        session = SessionFactory()
        try:
            count = 0
            for _, row in df.iterrows():
                # Buscar jugador por nombre o TM ID si estuviera disponible
                player_name = row.get('player_name')
                player = session.execute(select(Player).where(Player.name == player_name)).scalar_one_or_none()
                
                if not player:
                    logger.debug(f"Jugador no encontrado para lesión: {player_name}")
                    continue

                # Intentar parsear fechas
                start_date = self._parse_date(row.get('injury_date'))
                return_date = self._parse_date(row.get('return_date'))

                # UPSERT logic (borrar antiguas del mismo jugador/tipo si son recientes o duplicadas es complejo, 
                # así que por ahora añadimos si no existe una idéntica activa)
                existing = session.execute(
                    select(Injury).where(
                        Injury.player_id == player.id,
                        Injury.injury_type == row.get('injury_type'),
                        Injury.start_date == start_date
                    )
                ).scalar_one_or_none()

                if not existing:
                    injury = Injury(
                        player_id=player.id,
                        injury_type=row.get('injury_type', 'Desconocida'),
                        body_part=row.get('body_part', 'Otros'),
                        severity=row.get('severity', 'Moderada'),
                        start_date=start_date,
                        return_date=return_date,
                        days_out=int(row.get('recovery_days', 0)) if pd.notna(row.get('recovery_days')) else 0,
                        status=row.get('status', 'En tratamiento')
                    )
                    session.add(injury)
                    count += 1
            
            session.commit()
            logger.info(f"✓ {count} lesiones nuevas insertadas en SQL.")
        finally:
            session.close()

    def get_injuries_data(self) -> List[Dict]:
        """Consulta SQL para obtener lesiones con datos de jugador y equipo para el agregador."""
        session = SessionFactory()
        try:
            stmt = (
                select(Injury, Player, Team)
                .join(Player, Injury.player_id == Player.id)
                .outerjoin(Team, Player.current_team_id == Team.id)
            )
            results = session.execute(stmt).all()
            
            injuries_list = []
            for injury_obj, player_obj, team_obj in results:
                injuries_list.append({
                    'id': str(injury_obj.id),
                    'player_name': player_obj.name,
                    'team': team_obj.name if team_obj else "Desconocido",
                    'position': player_obj.position_main or "N/A",
                    'age': player_obj.age or 0,
                    'injury_type': injury_obj.injury_type,
                    'body_part': injury_obj.body_part,
                    'severity': injury_obj.severity,
                    'status': injury_obj.status,
                    'recovery_days': injury_obj.days_out or 0,
                    'injury_date': injury_obj.start_date.strftime('%Y-%m-%d') if injury_obj.start_date else None,
                    'return_date': injury_obj.return_date.strftime('%Y-%m-%d') if injury_obj.return_date else None,
                    'market_value': 0, # Campo pendiente si se añade a la DB
                    'matches_missed': 0 # Calculado dinámicamente si fuera necesario
                })
            return injuries_list
        finally:
            session.close()

    def get_player_match_history(self, player_id: str) -> List[Dict]:
        """Obtiene el historial detallado de partidos de un jugador desde SQL."""
        session = SessionFactory()
        try:
            stmt = (
                select(MatchHistory)
                .where(MatchHistory.player_id == player_id)
                .order_by(MatchHistory.date.desc())
            )
            results = session.execute(stmt).scalars().all()
            
            return [{
                'date': m.date.strftime('%d/%m/%Y'),
                'competition': m.competition_name,
                'competition_logo': m.competition_logo,
                'opponent': m.opponent,
                'result': m.result,
                'minutes_played': m.minutes_played,
                'goals': m.goals,
                'assists': m.assists,
                'yellow_cards': m.yellow_cards,
                'red_cards': m.red_cards,
                'position': m.position,
                'status': m.status
            } for m in results]
        finally:
            session.close()

    # ── Métodos de Compatibilidad Dashboard ──────────────────────────────────────

    def get_teams_with_injuries(self) -> List[str]:
        if not self.aggregator: return []
        return self.aggregator.get_available_teams()

    def get_statistics_summary(self) -> Dict:
        if not self.aggregator: return {}
        return self.aggregator.get_statistics_summary()

    def get_injuries_by_team(self, team_name: str) -> List[Dict]:
        if not self.aggregator: return []
        return self.aggregator.get_filtered_injuries(team=team_name)

    def check_for_updates(self) -> Dict:
        """Verifica el estado de sincronización en la DB."""
        session = SessionFactory()
        try:
            stmt = select(SystemSyncLog).where(SystemSyncLog.task_name == "transfermarkt_injuries")
            log = session.execute(stmt).scalar_one_or_none()
            
            if not log:
                return {'needs_update': True, 'message': 'Nunca sincronizado'}
            
            # Actualizar si han pasado más de 7 días
            needs_update = (datetime.now() - log.last_run).days >= 7
            return {
                'needs_update': needs_update,
                'message': 'Al día' if not needs_update else 'Requiere actualización semanal',
                'last_update': log.last_run.isoformat()
            }
        finally:
            session.close()

    # ── Helpers ──────────────────────────────────────────────────────────────────

    def _parse_date(self, date_val) -> Optional[datetime]:
        if pd.isna(date_val) or not date_val:
            return None
        if isinstance(date_val, datetime):
            return date_val
        try:
            return pd.to_datetime(date_val).to_pydatetime()
        except:
            return None

    def _update_sync_log(self, task: str):
        session = SessionFactory()
        try:
            log = session.get(SystemSyncLog, task)
            if not log:
                log = SystemSyncLog(task_name=task, last_run=datetime.now(), status="SUCCESS")
                session.add(log)
            else:
                log.last_run = datetime.now()
                log.status = "SUCCESS"
            session.commit()
        finally:
            session.close()
