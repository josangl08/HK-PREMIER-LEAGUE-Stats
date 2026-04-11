# ABOUTME: Verification script for intelligence data in the database.
# ABOUTME: Checks for BeSoccer ratings and Sofascore heatmaps/stats in MatchHistory and PlayerSeasonStat.

import logging
import sys
import os
import json
from sqlalchemy import select

# Add root to path
sys.path.append(os.getcwd())

from utils.db_engine import SessionFactory
from models.db_models import Player, UserPlayerLink, MatchHistory, PlayerSeasonStat, agent_player_links

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def verify_data():
    session = SessionFactory()
    try:
        # Identify targeted players
        player_ids = set()
        direct_links = session.query(UserPlayerLink).all()
        for link in direct_links:
            player_ids.add(link.player_id)
        agent_rosters = session.execute(select(agent_player_links.c.player_id)).all()
        for row in agent_rosters:
            player_ids.add(row[0])
            
        print("\n=== VERIFICACIÓN DE DATOS DE INTELIGENCIA ===\n")
        
        for player_id in sorted(list(player_ids)):
            player = session.get(Player, player_id)
            if not player: continue
            
            print(f"JUGADOR: {player.name} (ID: {player_id})")
            
            # 1. Verificar ratings de temporada (BeSoccer)
            stats = session.query(PlayerSeasonStat).filter(PlayerSeasonStat.player_id == player_id).all()
            bs_seasons = [s.season_id for s in stats if s.advanced_stats and "besoccer_season_rating" in s.advanced_stats]
            print(f"  - Ratings de Temporada (BeSoccer): {len(bs_seasons)} temporadas ({', '.join(bs_seasons)})")
            
            # 2. Verificar ratings de partidos (BeSoccer)
            matches = session.query(MatchHistory).filter(MatchHistory.player_id == player_id).all()
            bs_matches = [m for m in matches if m.raw_data and "besoccer_rating" in m.raw_data]
            print(f"  - Ratings de Partido (BeSoccer): {len(bs_matches)} partidos")
            
            # 3. Verificar Inteligencia Continental (Sofascore)
            ss_matches = [m for m in matches if m.raw_data and "sofascore_intelligence" in m.raw_data]
            print(f"  - Inteligencia Continental (Sofascore): {len(ss_matches)} partidos")
            
            if ss_matches:
                print("    Detalle Sofascore (últimos partidos):")
                for m in ss_matches[:3]: # Mostrar solo los 3 primeros
                    intel = m.raw_data.get("sofascore_intelligence", {})
                    has_heatmap = "heatmap" in intel and len(intel["heatmap"]) > 0
                    has_stats = "statistics" in intel
                    rating = m.raw_data.get("sofascore_rating", "N/A")
                    print(f"      * [{m.date.strftime('%Y-%m-%d')}] {m.competition_name}: Rating {rating}, Heatmap: {'SI' if has_heatmap else 'NO'}, Stats: {'SI' if has_stats else 'NO'}")
            
            print("-" * 50)
            
    except Exception as e:
        logger.error(f"Error en verificación: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    verify_data()
