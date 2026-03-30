# Diagnostic script for Player Portal loading issue
import sys
import os
sys.path.append(os.getcwd())

import logging
import json
from datetime import datetime, timezone
from data.aggregators.timeline_aggregator import TimelineAggregator
from utils.db_engine import SessionFactory
from models.db_models import Player

# Mock class for User
class MockUser:
    def __init__(self, player_id):
        self.player_id = player_id
        self.is_authenticated = True

def _serialize_milestones(milestones: list) -> list:
    """Copy of the serialization logic from player_portal_callbacks.py"""
    result = []
    for m in milestones:
        entry = dict(m)
        date_obj = entry.get("date")
        if hasattr(date_obj, "isoformat"):
            entry["date"] = date_obj.isoformat()

        m_type = entry.get("type", "unknown")
        date_str = entry["date"][:10] if isinstance(entry["date"], str) else "no-date"
        if m_type == "career":
            date_str = entry.get("payload", {}).get("season", date_str)
        entry["id"] = f"{m_type}-{date_str}"

        payload = dict(entry.get("payload", {}))
        if hasattr(payload.get("date"), "isoformat"):
            payload["date"] = payload["date"].isoformat()
            
        if "matches" in payload:
            serialized_matches = []
            for match in payload["matches"]:
                m_copy = dict(match)
                if hasattr(m_copy.get("date"), "isoformat"):
                    m_copy["date"] = m_copy["date"].isoformat()
                serialized_matches.append(m_copy)
            payload["matches"] = serialized_matches
            
        entry["payload"] = payload
        result.append(entry)
    return result

def diagnose():
    print("=== DIAGNÓSTICO DEL PORTAL DEL JUGADOR ===")
    player_id = "125040" # Manuel Bleda
    
    try:
        # 1. Probar Aggregator
        print(f"1. Recuperando timeline para ID {player_id}...")
        aggregator = TimelineAggregator()
        milestones = aggregator.get_player_timeline(player_id)
        print(f"   ✓ {len(milestones)} hitos recuperados.")
        
        # 2. Probar Serialización (Aquí es donde suele fallar)
        print("2. Probando serialización JSON...")
        serialized = _serialize_milestones(milestones)
        # Intentar convertir a JSON real para asegurar que todo es serializable
        json_data = json.dumps(serialized)
        print(f"   ✓ Serialización completada ({len(json_data)} bytes).")
        
        # 3. Verificar estructura de un hito 'career'
        career_m = next((m for m in serialized if m['type'] == 'career'), None)
        if career_m:
            print(f"3. Verificando hito CAREER: {career_m['id']}")
            payload = career_m['payload']
            stats = payload.get('stats', {})
            print(f"   Stats: MP={stats.get('matches_played')}, G={stats.get('goals')}")
            if not payload.get('matches'):
                print("   ⚠️ ADVERTENCIA: La lista de partidos ('matches') está vacía en Career.")
        
        # 4. Verificar estructura de un hito 'post-match'
        post_m = next((m for m in serialized if m['type'] == 'post-match'), None)
        if post_m:
            print(f"4. Verificando hito POST-MATCH: {post_m['id']}")
            payload = post_m['payload']
            print(f"   Equipos: {payload.get('home_team')} vs {payload.get('away_team')}")
            print(f"   Logos: Home={payload.get('home_logo') is not None}, Away={payload.get('away_logo') is not None}")
            print(f"   Ausencia: {payload.get('absence_reason')}")

    except Exception as e:
        print(f"\n❌ ERROR DETECTADO: {type(e).__name__}: {e}")
        import traceback; traceback.print_exc()

if __name__ == "__main__":
    diagnose()
