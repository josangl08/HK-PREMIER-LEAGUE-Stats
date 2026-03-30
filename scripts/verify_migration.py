# Verification script for SQL Migration
import sys
import os
# Añadir el directorio raíz al path para que encuentre los paquetes locales
sys.path.append(os.getcwd())

from sqlalchemy import select, func
from models.db_models import Player, Team, Injury, MatchHistory, PlayerSeasonStat, User, Fixture
from utils.db_engine import SessionFactory
from data.transfermarkt_data_manager import TransfermarktDataManager
from data.hong_kong_data_manager import HongKongDataManager

def verify():
    session = SessionFactory()
    print("=== RECUENTO DE REGISTROS EN SQL ===")
    try:
        tables = [Player, Team, Injury, MatchHistory, PlayerSeasonStat, User]
        for table in tables:
            count = session.query(func.count(table.id)).scalar()
            print(f"Table {table.__tablename__}: {count} records")
        
        print("\n=== PRUEBA DE TRANSFERMARKT DATA MANAGER ===")
        tm_manager = TransfermarktDataManager(auto_load=True)
        injuries = tm_manager.get_injuries_data()
        print(f"Injuries retrieved via Manager: {len(injuries)}")
        if injuries:
            print(f"Sample Injury: {injuries[0]['player_name']} ({injuries[0]['team']}) - {injuries[0]['injury_type']}")
        
        print("\n=== PRUEBA DE HISTORIAL DE PARTIDOS ===")
        # Buscar un jugador que sepamos que tiene historial (ej: Jose Angel)
        player = session.execute(select(Player).where(Player.name.like('%José Ángel%'))).scalar_one_or_none()
        if player:
            history = tm_manager.get_player_match_history(player.id)
            print(f"Match history for {player.name}: {len(history)} matches")
            if history:
                print(f"Latest match: {history[0]['date']} vs {history[0]['opponent']}")

        print("\n=== PRUEBA DE HONG KONG DATA MANAGER ===")
        hk_manager = HongKongDataManager(auto_load=True)
        status = hk_manager.get_data_status()
        print(f"Current Season: {status['current_season']}")
        print(f"Players in 2025-26: {status['data_stats']['total_players']}")

    except Exception as e:
        print(f"ERROR DURANTE LA VERIFICACIÓN: {e}")
        import traceback; traceback.print_exc()
    finally:
        session.close()

if __name__ == "__main__":
    verify()
