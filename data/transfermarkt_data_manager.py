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
from data.extractors.transfermarkt_playwright_extractor import TransfermarktPlaywrightExtractor
from data.processors.transfermarkt_processor import TransfermarktProcessor
from data.aggregators.transfermarkt_aggregator import TransfermarktStatsAggregator

# Configurar logging
logger = logging.getLogger(__name__)

class TransfermarktDataManager:
    """
    Gestor de datos de Transfermarkt (lesiones e historial) basado en SQL.
    Sustituye la dependencia de archivos JSON por consultas a la base de datos.
    """
    
    def __init__(self, cache_dir: str = "data/cache", auto_load: bool = True, use_playwright: bool = True):
        if use_playwright:
            self.extractor = TransfermarktPlaywrightExtractor(cache_dir)
        else:
            self.extractor = TransfermarktExtractor(cache_dir)
            
        self.processor = TransfermarktProcessor()
        
        # Estado interno (mantener por compatibilidad si es necesario, pero priorizar SQL)
        self.processed_injuries = None
        self.aggregator = None
        
        if auto_load:
            self.refresh_data()

    def refresh_data(self, force_scraping: bool = False, sync_history: bool = False, historical: bool = False) -> bool:
        """
        Refresca los datos de lesiones e historial. 
        Si force_scraping es True, realiza el proceso ETL y guarda en SQL.
        Si es False, carga los datos directamente de SQL al agregador.
        """
        try:
            if force_scraping:
                logger.info(f"Iniciando proceso ETL forzado para Transfermarkt (histórico={historical})...")
                self._perform_full_etl(sync_history=sync_history, historical=historical)
            
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

    def supports_injuries_scraping(self) -> bool:
        return hasattr(self.extractor, "extract_all_injuries")

    def get_injuries_runtime_status(self) -> Dict:
        """Returns truthful injuries-system status for admin/home."""
        session = SessionFactory()
        try:
            injuries_count = session.execute(select(Injury)).scalars().all()
            injury_total = len(injuries_count)
            log = session.get(SystemSyncLog, "transfermarkt_injuries")
            supported = self.supports_injuries_scraping()
            return {
                "supported": supported,
                "available": injury_total > 0,
                "records": injury_total,
                "last_update": log.last_run.isoformat() if log else None,
                "sync_status": log.status if log else None,
                "message": (
                    "Transfermarkt injuries scraper is not implemented in the current extractor."
                    if not supported
                    else ("Injuries data available." if injury_total > 0 else "No injuries stored yet.")
                ),
            }
        finally:
            session.close()

    def _should_update_data(self) -> bool:
        """Legacy compatibility for home callbacks."""
        if not self.supports_injuries_scraping():
            return False
        status = self.get_injuries_runtime_status()
        last_update = status.get("last_update")
        if not last_update:
            return True
        try:
            last_dt = datetime.fromisoformat(last_update)
        except Exception:
            return True
        return (datetime.now() - last_dt).days >= 7

    def _save_manual_update_timestamp(self, dt: datetime) -> None:
        """Legacy compatibility hook used by home callbacks."""
        session = SessionFactory()
        try:
            log = session.get(SystemSyncLog, "transfermarkt_injuries")
            if not log:
                log = SystemSyncLog(task_name="transfermarkt_injuries", last_run=dt, status="MANUAL_REQUEST")
                session.add(log)
            else:
                log.last_run = dt
                log.status = "MANUAL_REQUEST"
            session.commit()
        finally:
            session.close()

    def refresh_player_data(self, player_id: str) -> bool:
        """Legacy wrapper. Prefer TransfermarktRefreshManager for scoped refresh policies."""
        return self.refresh_player_data_for_seasons(player_id, self._get_valid_season_ids())

    def _get_valid_season_ids(self, min_start_year: int = 2018) -> List[str]:
        from models.db_models import Season
        current_season = get_current_season()
        try:
            current_start = int(str(current_season).split("-")[0])
        except Exception:
            current_start = datetime.now().year
        session = SessionFactory()
        try:
            seasons_stmt = select(Season.id)
            seasons = session.execute(seasons_stmt).scalars().all()
            valid = []
            for season_id in seasons:
                try:
                    start_year = int(str(season_id).split("-")[0])
                except Exception:
                    continue
                if min_start_year <= start_year <= current_start + 1:
                    valid.append(season_id)
            return sorted(set(valid))
        finally:
            session.close()

    def refresh_player_data_for_seasons(self, player_id: str, season_ids: List[str]) -> bool:
        from models.db_models import Player
        session = SessionFactory()
        try:
            player = session.get(Player, player_id)
            if not player or not player.tm_id:
                logger.warning(f"Jugador {player_id} no encontrado o sin tm_id.")
                return False

            updated = False
            for season_id in season_ids:
                try:
                    logger.info(f"Scraping TM para {player.name} en {season_id}...")
                    raw_matches = self.extractor.get_match_history(str(player.tm_id), season_id)
                    if self.extractor.last_http_status == 405:
                        logger.warning(f"TM returned 405 for {player.name} ({season_id}); stopping early.")
                        break
                    if raw_matches:
                        self._upsert_history_to_sql(player.id, raw_matches)
                        updated = True
                except Exception as e:
                    logger.error(f"Error en refresh_player_data para {player.name} ({season_id}): {e}")

            return updated
        finally:
            session.close()

    def _perform_full_etl(self, sync_history: bool = False, historical: bool = False):
        """Ejecuta el ciclo de extracción, procesamiento y carga en DB."""
        session = SessionFactory()
        try:
            if sync_history:
                # Sincronizar historial para todos los jugadores con tm_id
                players = session.execute(select(Player).where(Player.tm_id.is_not(None))).scalars().all()
                seasons = self._get_valid_season_ids()
                
                for player in players:
                    logger.info(f"Sincronizando historial TM para: {player.name}...")
                    for season_id in seasons:
                        try:
                            raw_matches = self.extractor.get_match_history(str(player.tm_id), season_id)
                            if raw_matches:
                                self._upsert_history_to_sql(player.id, raw_matches)
                        except Exception as e:
                            logger.error(f"Error sincronizando historial para {player.name} en {season_id}: {e}")
            
            # Sincronizar lesiones (Proceso principal)
            if hasattr(self.extractor, 'get_team_injuries'):
                if not historical:
                    logger.info("Iniciando extracción de lesiones ACTUALES equipo por equipo...")
                    from data.extractors.transfermarkt_extractor import _TEAM_TM_CLUB_IDS
                    for team_key, tm_club_id in _TEAM_TM_CLUB_IDS.items():
                        try:
                            logger.info(f"Procesando equipo: {team_key}...")
                            team_raw = self.extractor.get_team_injuries(tm_club_id)
                            if team_raw:
                                for entry in team_raw: entry["team_key"] = team_key
                                df_team = self.processor.process_injuries_data(team_raw)
                                if not df_team.empty:
                                    self._upsert_injuries_to_sql(df_team)
                        except Exception as e:
                            logger.error(f"Error procesando equipo {team_key}: {e}")
                else:
                    logger.info("Iniciando extracción de lesiones HISTÓRICAS jugador por jugador...")
                    # Obtener todos los jugadores con tm_id de la DB
                    players = session.execute(select(Player).where(Player.tm_id.is_not(None))).scalars().all()
                    logger.info(f"Se procesarán {len(players)} jugadores para su historial médico.")
                    
                    for player in players:
                        try:
                            logger.info(f"Extrayendo historial médico de: {player.name} (TM: {player.tm_id})...")
                            player_injuries = self.extractor.get_player_injuries(str(player.tm_id))
                            
                            if player_injuries:
                                # Adaptar formato para el procesador
                                formatted_injuries = []
                                for inj in player_injuries:
                                    formatted_injuries.append({
                                        'player_name': player.name,
                                        'tm_id': str(player.tm_id),
                                        'injury_type': inj.get('injury_type'),
                                        'date_from': inj.get('date_from'),
                                        'date_until': inj.get('date_until'),
                                        'missed_matches': inj.get('matches_missed'),
                                        'days_out': inj.get('days'),
                                        'season': inj.get('season')
                                    })
                                
                                df_player = self.processor.process_injuries_data(formatted_injuries)
                                if not df_player.empty:
                                    self._upsert_injuries_to_sql(df_player)
                            
                            # Delay para no ser bloqueados (scraping individual es más lento pero seguro)
                            import time, random
                            time.sleep(random.uniform(2, 5))
                            
                        except Exception as e:
                            logger.error(f"Error procesando historial de {player.name}: {e}")
            
            self._update_sync_log("transfermarkt_full_sync")
        finally:
            session.close()

    def _upsert_injuries_to_sql(self, df: pd.DataFrame):
        """Inserta o actualiza lesiones en la base de datos con asociación precisa."""
        session = SessionFactory()
        try:
            count = 0
            for _, row in df.iterrows():
                # 1. Intentar buscar por TM ID (lo más preciso)
                tm_id = row.get('tm_id')
                player = None
                if tm_id:
                    player = session.execute(select(Player).where(Player.tm_id == int(tm_id))).scalars().first()
                
                # 2. Fallback por nombre si no se encontró por ID
                if not player:
                    player_name = row.get('player_name')
                    # Usar .first() para evitar error si hay duplicados de nombre
                    player = session.execute(select(Player).where(Player.name == player_name)).scalars().first()
                
                if not player:
                    logger.debug(f"Jugador no encontrado para lesión: {row.get('player_name')} (TM ID: {tm_id})")
                    continue

                # Intentar parsear fechas
                start_date = self._parse_date(row.get('injury_date'))
                return_date = self._parse_date(row.get('return_date'))

                if not start_date:
                    logger.warning(f"Omitiendo lesión para {player.name}: fecha de inicio inválida ({row.get('injury_date')})")
                    continue

                # UPSERT logic: Evitar duplicados exactos
                existing = session.execute(
                    select(Injury).where(
                        Injury.player_id == player.id,
                        Injury.injury_type == row.get('injury_type'),
                        Injury.start_date == start_date
                    )
                ).scalars().first()

                if not existing:
                    injury = Injury(
                        player_id=player.id,
                        injury_type=row.get('injury_type', 'Desconocida'),
                        body_part=row.get('body_part', 'Otros'),
                        severity=row.get('severity', 'Moderada'),
                        start_date=start_date,
                        return_date=return_date,
                        days_out=int(row.get('recovery_days', 0)) if pd.notna(row.get('recovery_days')) else 0,
                        missed_matches=int(row.get('missed_matches', 0)) if pd.notna(row.get('missed_matches')) else 0,
                        status=row.get('status', 'En tratamiento')
                    )
                    session.add(injury)
                    count += 1
                else:
                    # Actualizar status y fecha de retorno si ha cambiado
                    existing.status = row.get('status', existing.status)
                    existing.return_date = return_date
                    existing.days_out = int(row.get('recovery_days', 0)) if pd.notna(row.get('recovery_days')) else existing.days_out
                    existing.missed_matches = int(row.get('missed_matches', existing.missed_matches)) if pd.notna(row.get('missed_matches')) else existing.missed_matches
            
            session.commit()
            logger.info(f"✓ {count} lesiones procesadas/actualizadas en SQL.")
        except Exception as e:
            session.rollback()
            logger.error(f"Error al guardar lesiones en SQL: {e}")
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
                    'missed_matches': injury_obj.missed_matches or 0,
                    'injury_date': injury_obj.start_date.strftime('%Y-%m-%d') if injury_obj.start_date else None,
                    'return_date': injury_obj.return_date.strftime('%Y-%m-%d') if injury_obj.return_date else None,
                    'market_value': 0, # Campo pendiente si se añade a la DB
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
        if not date_val:
            return None
        if isinstance(date_val, float) and pd.isna(date_val):
            return None
        if isinstance(date_val, datetime):
            return date_val
        s = str(date_val).strip()
        # Primary: all Transfermarkt dates are DD/MM/YYYY
        try:
            return datetime.strptime(s, "%d/%m/%Y")
        except ValueError:
            pass
        # Fallback: ISO or other unambiguous formats
        try:
            return datetime.fromisoformat(s)
        except ValueError:
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

    def _is_national_team_competition(self, competition_name: str | None) -> bool:
        text = str(competition_name or "").lower()
        national_tokens = [
            "asian cup",
            "world cup",
            "qualification",
            "qualifier",
            "nations cup",
            "friendly international",
            "u17",
            "u20",
            "u23",
            "u-17",
            "u-20",
            "u-23",
        ]
        return any(token in text for token in national_tokens)

    def _upsert_history_to_sql(self, player_id: str, raw_matches: List[Dict]):
        """Helper to upsert match history data."""
        session = SessionFactory()
        try:
            for m in raw_matches:
                if self._is_national_team_competition(m.get("competition")):
                    continue
                dt = self._parse_date(m.get('date'))
                if not dt: continue
                
                existing = session.execute(
                    select(MatchHistory).where(
                        MatchHistory.player_id == player_id,
                        MatchHistory.date == dt,
                        MatchHistory.opponent == m.get('opponent')
                    )
                ).scalar_one_or_none()
                merged_raw = dict(existing.raw_data or {}) if existing and existing.raw_data else {}
                merged_raw.update(m)
                
                if not existing:
                    history = MatchHistory(
                        player_id=player_id,
                        date=dt,
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
                        raw_data=merged_raw,
                    )
                    session.add(history)
                else:
                    existing.competition_name = m.get('competition') or existing.competition_name
                    existing.competition_logo = m.get('competition_logo') or existing.competition_logo
                    existing.result = m.get('result') or existing.result
                    existing.minutes_played = m.get('minutes_played', existing.minutes_played or 0)
                    existing.goals = m.get('goals', existing.goals or 0)
                    existing.assists = m.get('assists', existing.assists or 0)
                    existing.yellow_cards = m.get('yellow_cards', existing.yellow_cards or 0)
                    existing.red_cards = m.get('red_cards', existing.red_cards or 0)
                    existing.position = m.get('position') or existing.position
                    existing.status = m.get('status') or existing.status
                    existing.raw_data = merged_raw
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Error in _upsert_history_to_sql: {e}")
        finally:
            session.close()
