# ABOUTME: Interface for player identity resolution using the SQL database.
# ABOUTME: Replaces the old JSON-based index with direct SQLAlchemy queries for better performance and consistency.

import logging
from typing import Dict, List, Optional
from sqlalchemy import select
from models.db_models import Player, PlayerSeasonStat
from utils.db_engine import SessionFactory

logger = logging.getLogger(__name__)

class PlayerIndex:
    """
    Maintains a virtual player ID index backed by SQL.
    Provides backward compatibility with the old JSON-based PlayerIndex API.
    """

    def __init__(self):
        self._loaded = True # Always considered loaded as it proxies to SQL

    # ------------------------------------------------------------------
    # Public API (Backward Compatible)
    # ------------------------------------------------------------------

    def get_player_id(self, name: str) -> Optional[str]:
        """Returns the canonical player ID for a given name from SQL."""
        session = SessionFactory()
        try:
            # Match by name (case insensitive if possible, but title case is standard in DB)
            stmt = select(Player.id).where(Player.name == name)
            result = session.execute(stmt).scalar_one_or_none()
            return str(result) if result else None
        finally:
            session.close()

    def get_player_info(self, player_id: str) -> Optional[Dict]:
        """Returns player metadata and active seasons from SQL."""
        session = SessionFactory()
        try:
            player = session.get(Player, str(player_id))
            if not player:
                return None
            
            # Fetch active seasons from player_season_stats
            stmt = select(PlayerSeasonStat.season_id).where(PlayerSeasonStat.player_id == player_id)
            seasons = session.execute(stmt).scalars().all()

            return {
                "canonical_name": player.name,
                "id_type": "wyscout" if not str(player_id).startswith("hk_") else "generated",
                "seasons": list(seasons),
                "fingerprint": {
                    "birth_country": player.birth_country or "",
                    "foot": player.foot or "",
                    "height": str(player.height) if player.height else "0",
                }
            }
        finally:
            session.close()

    def get_all_player_names(self) -> List[str]:
        """Returns all player names stored in the database."""
        session = SessionFactory()
        try:
            stmt = select(Player.name).order_by(Player.name)
            return list(session.execute(stmt).scalars().all())
        finally:
            session.close()

    def build(self, force: bool = False) -> bool:
        """
        No-op for backward compatibility. 
        In the new system, building is handled by the ETL/Migration process.
        """
        logger.debug("PlayerIndex.build() is now a no-op (data managed in SQL).")
        return True

# Module-level singleton for backward compatibility
_player_index = PlayerIndex()

def get_player_index() -> PlayerIndex:
    """Returns the module-level PlayerIndex singleton."""
    return _player_index
