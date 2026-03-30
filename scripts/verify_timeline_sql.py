# Verification script for Player Portal Timeline SQL Migration
import sys
import os
# Añadir el directorio raíz al path para que encuentre los paquetes locales
sys.path.append(os.getcwd())

import logging
from sqlalchemy import select
from models.db_models import Player, User
from utils.db_engine import SessionFactory
from data.aggregators.timeline_aggregator import TimelineAggregator

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def verify_timeline():
    session = SessionFactory()
    print("=== VERIFICACIÓN DEL TIMELINE (SQL) ===")
    try:
        # 1. Buscar al jugador José Ángel en la DB
        stmt = select(Player).where(Player.name.like('%José Ángel%'))
        player = session.execute(stmt).scalar_one_or_none()
        
        if not player:
            print("❌ Jugador 'José Ángel' no encontrado en la base de datos.")
            return

        print(f"✓ Jugador encontrado: {player.name} (ID: {player.id})")
        print(f"  Equipo actual: {player.current_team_id}")

        # 2. Instanciar el TimelineAggregator
        aggregator = TimelineAggregator()
        
        # 3. Obtener el timeline
        print(f"Recuperando timeline para {player.id}...")
        timeline = aggregator.get_player_timeline(player.id)
        
        print(f"✓ Timeline recuperado: {len(timeline)} hitos encontrados.")
        
        # 4. Analizar tipos de hitos
        stats = {}
        for m in timeline:
            m_type = m['type']
            stats[m_type] = stats.get(m_type, 0) + 1
        
        print("\nDesglose de hitos:")
        for m_type, count in stats.items():
            print(f"  - {m_type}: {count}")
            
        # 5. Mostrar el hito más reciente
        if timeline:
            recent = timeline[0]
            print(f"\nHito más reciente:")
            print(f"  Tipo: {recent['type']}")
            print(f"  Etiqueta: {recent['label']}")
            print(f"  Fecha: {recent['date']}")
            
            if recent['type'] == 'pre-match':
                print(f"  Próximo rival: {recent['payload'].get('opponent')}")
            elif recent['type'] == 'post-match':
                print(f"  Rival: {recent['payload'].get('opponent')} | Resultado: {recent['payload'].get('result')}")

        # 6. Verificar que no haya campos "Unknown" inesperados en los equipos
        if any(m.get('payload', {}).get('opponent') == 'Unknown' for m in timeline if m['type'] in ['pre-match', 'post-match']):
            print("\n⚠️ Advertencia: Se encontraron oponentes 'Unknown' en el timeline.")

    except Exception as e:
        print(f"❌ ERROR DURANTE LA VERIFICACIÓN: {e}")
        import traceback; traceback.print_exc()
    finally:
        session.close()

if __name__ == "__main__":
    verify_timeline()
