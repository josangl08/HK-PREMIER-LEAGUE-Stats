"""
Script de prueba para el agregador de estadísticas de Hong Kong.
Ejecutar desde la raíz del proyecto: python data/test_aggregator.py
"""

import sys
from pathlib import Path
import json

# Agregar el directorio raíz al path para imports
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from data.extractors.hong_kong_extractor import HongKongDataExtractor
from data.processors.hong_kong_processor import HongKongDataProcessor
from data.aggregators.hong_kong_aggregator import HongKongStatsAggregator

def test_aggregator():
    """Prueba completa del agregador de estadísticas."""
    
    print("=== Prueba del Agregador de Estadísticas de Hong Kong ===\n")
    
    # 1. Cargar y procesar datos
    print("1. Cargando y procesando datos...")
    extractor = HongKongDataExtractor()
    df_raw = extractor.download_season_data("2024-25")
    
    if df_raw is None:
        print("❌ No se pudieron cargar los datos")
        return
    
    processor = HongKongDataProcessor()
    df_processed = processor.process_season_data(df_raw, "2024-25")
    
    if df_processed.empty:
        print("❌ No se pudieron procesar los datos")
        return
    
    print(f"   ✓ Datos procesados: {len(df_processed)} jugadores")
    
    # 2. Inicializar agregador
    print("\n2. Inicializando agregador...")
    aggregator = HongKongStatsAggregator(df_processed)
    print("   ✓ Agregador inicializado")
    
    # 3. Probar estadísticas de liga
    print("\n3. Probando estadísticas de liga...")
    league_stats = aggregator.get_league_statistics()
    
    print("   Overview de la liga:")
    overview = league_stats['overview']
    print(f"     - Total jugadores: {overview['total_players']}")
    print(f"     - Total equipos: {overview['total_teams']}")
    print(f"     - Temporada: {overview['season']}")
    print(f"     - Total goles: {overview['total_goals']}")
    print(f"     - Total asistencias: {overview['total_assists']}")
    print(f"     - Edad promedio: {overview['average_age']} años")
    
    print("\n   Top 3 goleadores:")
    if 'top_performers' in league_stats and 'top_scorers' in league_stats['top_performers']:
        for i, player in enumerate(league_stats['top_performers']['top_scorers'][:3], 1):
            print(f"     {i}. {player['Player']} ({player['Team']}) - {player['Goals']} goles")
    
    print("\n   Distribución por posición:")
    if 'position_analysis' in league_stats:
        for position, stats in league_stats['position_analysis'].items():
            print(f"     {position}: {stats['player_count']} jugadores, {stats['total_goals']} goles")
    
    # 4. Probar estadísticas de equipo
    print("\n4. Probando estadísticas de equipo...")
    teams = aggregator.get_available_teams()
    if teams:
        test_team = teams[0]
        print(f"   Analizando equipo: {test_team}")
        
        team_stats = aggregator.get_team_statistics(test_team)
        
        print(f"   Overview del equipo:")
        overview = team_stats['overview']
        print(f"     - Jugadores: {overview['total_players']}")
        print(f"     - Edad promedio: {overview['avg_age']} años")
        print(f"     - Total goles: {overview['total_goals']}")
        print(f"     - Total asistencias: {overview['total_assists']}")
        
        print(f"\n   Top players del {test_team}:")
        if 'top_players' in team_stats:
            top_players = team_stats['top_players']
            if 'top_scorer' in top_players:
                scorer = top_players['top_scorer']
                print(f"     Goleador: {scorer['name']} ({scorer['goals']} goles)")
            if 'top_assister' in top_players:
                assister = top_players['top_assister']
                print(f"     Asistente: {assister['name']} ({assister['assists']} asistencias)")
        
        print(f"\n   Distribución por posición en {test_team}:")
        if 'squad_analysis' in team_stats and 'position_distribution' in team_stats['squad_analysis']:
            for position, count in team_stats['squad_analysis']['position_distribution'].items():
                print(f"     {position}: {count} jugadores")
    
    # 5. Probar estadísticas de jugador
    print("\n5. Probando estadísticas de jugador...")
    players = aggregator.get_available_players()
    if players:
        test_player = players[0]
        print(f"   Analizando jugador: {test_player}")
        
        player_stats = aggregator.get_player_statistics(test_player)
        
        print(f"   Información básica:")
        basic_info = player_stats['basic_info']
        print(f"     - Nombre: {basic_info['name']}")
        print(f"     - Equipo: {basic_info['team']}")
        if 'age' in basic_info:
            print(f"     - Edad: {basic_info['age']} años")
        if 'position_group' in basic_info:
            print(f"     - Posición: {basic_info['position_group']}")
        
        print(f"\n   Estadísticas de performance:")
        if 'performance_stats' in player_stats:
            perf_stats = player_stats['performance_stats']
            for key, value in perf_stats.items():
                if isinstance(value, (int, float)):
                    print(f"     {key.replace('_', ' ').title()}: {value}")
        
        print(f"\n   Comparaciones:")
        if 'comparisons' in player_stats:
            comparisons = player_stats['comparisons']
            for metric, values in comparisons.items():
                print(f"     {metric}:")
                print(f"       Jugador: {values['player']}")
                print(f"       Promedio liga: {values['league_avg']}")
                print(f"       Promedio equipo: {values['team_avg']}")
        
        print(f"\n   Percentiles en su posición:")
        if 'percentiles' in player_stats:
            percentiles = player_stats['percentiles']
            for metric, percentile in percentiles.items():
                print(f"     {metric}: {percentile}° percentil")
    
    # 6. Probar datos para gráficos
    print("\n6. Probando datos para gráficos...")
    
    # Datos de liga para gráficos
    league_chart_data = aggregator.get_comparative_data_for_charts('league')
    print("   Datos de liga preparados para gráficos:")
    for chart_type, data in league_chart_data.items():
        print(f"     - {chart_type}: {list(data.keys()) if isinstance(data, dict) else 'disponible'}")
    
    # Datos de equipo para gráficos
    if teams:
        team_chart_data = aggregator.get_comparative_data_for_charts('team', teams[0])
        print(f"\n   Datos de {teams[0]} preparados para gráficos:")
        for chart_type, data in team_chart_data.items():
            print(f"     - {chart_type}: {list(data.keys()) if isinstance(data, dict) else 'disponible'}")
    
    # Datos de jugador para gráficos
    if players:
        player_chart_data = aggregator.get_comparative_data_for_charts('player', players[0])
        print(f"\n   Datos de {players[0]} preparados para gráficos:")
        for chart_type, data in player_chart_data.items():
            print(f"     - {chart_type}: {list(data.keys()) if isinstance(data, dict) else 'disponible'}")
    
    print("\n=== Prueba completada ===")

def test_performance_metrics():
    """Prueba métricas específicas de performance."""
    
    print("\n=== Prueba de Métricas de Performance ===\n")
    
    # Cargar datos
    extractor = HongKongDataExtractor()
    df_raw = extractor.download_season_data("2024-25")
    
    if df_raw is None:
        print("❌ No se pudieron cargar los datos")
        return
    
    processor = HongKongDataProcessor()
    df_processed = processor.process_season_data(df_raw, "2024-25")
    aggregator = HongKongStatsAggregator(df_processed)
    
    # 1. Analizar top performers por categoría
    league_stats = aggregator.get_league_statistics()
    
    if 'top_performers' in league_stats:
        performers = league_stats['top_performers']
        
        print("1. Top Performers por categoría:")
        
        categories = [
            ('top_scorers', 'Goleadores'),
            ('top_assisters', 'Asistentes'),
            ('best_passers', 'Pasadores'),
            ('best_dribblers', 'Regateadores')
        ]
        
        for key, title in categories:
            if key in performers:
                print(f"\n   {title}:")
                for i, player in enumerate(performers[key][:5], 1):
                    player_info = f"{player['Player']} ({player['Team']})"
                    if key == 'top_scorers':
                        stat = f"{player['Goals']} goles"
                    elif key == 'top_assisters':
                        stat = f"{player['Assists']} asistencias"
                    elif key == 'best_passers':
                        stat = f"{player['Accurate passes, %']}% precisión"
                    elif key == 'best_dribblers':
                        stat = f"{player['Successful dribbles, %']}% éxito"
                    
                    print(f"     {i}. {player_info} - {stat}")
    
    # 2. Análisis por posición detallado
    print("\n2. Análisis detallado por posición:")
    
    if 'position_analysis' in league_stats:
        for position, stats in league_stats['position_analysis'].items():
            print(f"\n   {position}:")
            print(f"     - Jugadores: {stats['player_count']}")
            print(f"     - Edad promedio: {stats['avg_age']} años")
            print(f"     - Goles totales: {stats['total_goals']}")
            print(f"     - Minutos promedio: {stats['avg_minutes']}")
            
            # Mostrar métricas específicas de la posición
            for key, value in stats.items():
                if key.startswith('avg_') and key not in ['avg_age', 'avg_minutes']:
                    metric_name = key.replace('avg_', '').replace('_', ' ').title()
                    print(f"     - {metric_name}: {value}")
    
    # 3. Comparación entre equipos
    print("\n3. Comparación entre equipos (Top 5 por goles):")
    
    if 'team_comparison' in league_stats and 'teams' in league_stats['team_comparison']:
        teams = league_stats['team_comparison']['teams'][:5]
        
        for i, team in enumerate(teams, 1):
            print(f"\n   {i}. {team['team']}:")
            print(f"     - Jugadores: {team['players']}")
            print(f"     - Goles totales: {team['total_goals']}")
            print(f"     - Goles por jugador: {team.get('goals_per_player', 0)}")
            print(f"     - Edad promedio: {team['avg_age']} años")
    
    print("\n=== Métricas de performance completadas ===")

def test_cache_performance():
    """Prueba el rendimiento del cache."""
    
    print("\n=== Prueba de Performance del Cache ===\n")
    
    import time
    
    # Cargar datos
    extractor = HongKongDataExtractor()
    df_raw = extractor.download_season_data("2024-25")
    if df_raw is None:
        print("❌ No se pudieron cargar los datos")
        return
    processor = HongKongDataProcessor()
    df_processed = processor.process_season_data(df_raw, "2024-25")
    aggregator = HongKongStatsAggregator(df_processed)
    
    # Medir tiempo sin cache
    print("1. Midiendo tiempo sin cache...")
    start_time = time.time()
    league_stats1 = aggregator.get_league_statistics()
    first_call_time = time.time() - start_time
    print(f"   Primera llamada: {first_call_time:.3f} segundos")
    
    # Medir tiempo con cache
    print("\n2. Midiendo tiempo con cache...")
    start_time = time.time()
    league_stats2 = aggregator.get_league_statistics()
    cached_call_time = time.time() - start_time
    print(f"   Segunda llamada (con cache): {cached_call_time:.3f} segundos")
    
    # Calcular mejora
    speedup = first_call_time / cached_call_time if cached_call_time > 0 else float('inf')
    print(f"   Mejora de velocidad: {speedup:.1f}x más rápido")
    
    # Verificar que los datos son idénticos
    print("\n3. Verificando integridad del cache...")
    stats_match = league_stats1 == league_stats2
    print(f"   Los datos del cache coinciden: {'✓' if stats_match else '❌'}")
    
    # Limpiar cache y verificar
    print("\n4. Probando limpieza de cache...")
    aggregator.clear_cache()
    start_time = time.time()
    league_stats3 = aggregator.get_league_statistics()
    after_clear_time = time.time() - start_time
    print(f"   Tiempo después de limpiar cache: {after_clear_time:.3f} segundos")
    print(f"   Cache limpiado correctamente: {'✓' if after_clear_time > cached_call_time else '❌'}")
    
    print("\n=== Prueba de cache completada ===")

if __name__ == "__main__":
    test_aggregator()
    test_performance_metrics()
    test_cache_performance()