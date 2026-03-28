# ABOUTME: Real-world agentic query to test the Elite Multi-Model Tier 1 setup.
# ABOUTME: Asks for a technical efficiency analysis of HK League players.

import os
import sys
import logging
from pathlib import Path
from dotenv import load_dotenv

# Path setup
_ROOT = str(Path(__file__).parent.parent)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

def run_scouting_test():
    try:
        from data.hong_kong_data_manager import HongKongDataManager
        from utils.app_context import set_hong_kong_data_manager
        
        print("\n--- 🏟️ CONSULTA DE SCOUTING ÉLITE (HK PREMIER LEAGUE) ---")
        
        # Initialize and register data manager
        print("📊 Cargando datos de la liga...")
        dm = HongKongDataManager(auto_load=True)
        set_hong_kong_data_manager(dm)
        print(f"✓ Datos cargados para la temporada {dm.current_season}")

        from ai_models.agent import create_agent, run_agent
        
        # El agente usará Gemini 3.1 Pro para razonar y 3 Flash para las herramientas
        agent = create_agent(flow="scouting")
        
        query = (
            "Analiza la base de datos de la liga de Hong Kong 2024-25 y dime quiénes "
            "son los 3 delanteros con mejor eficiencia goleadora. Compara sus goles "
            "anotados contra su xG (Expected Goals) y explica por qué son los más letales."
        )
        
        print(f"\nPregunta al Agente: {query}\n")
        
        result = run_agent(agent, query)
        
        if result.get("error"):
            print(f"❌ ERROR: {result['error']}")
        else:
            print(f"🤖 RESPUESTA DEL AGENTE PRO:\n")
            print(result["output"])
            
            if result.get("steps"):
                print("\n🛠️ PASOS TÉCNICOS REALIZADOS:")
                for step in result["steps"]:
                    print(f"- {step}")
            
    except Exception as e:
        print(f"❌ ERROR CRÍTICO: {e}")

if __name__ == "__main__":
    run_scouting_test()
