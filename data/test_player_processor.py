"""
Script de prueba para el procesador de datos de Hong Kong.
Ejecutar desde la raíz del proyecto: python data/test_processor.py
"""

import sys
from pathlib import Path
import json

# Agregar el directorio raíz al path para imports
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from data.extractors.hong_kong_extractor import HongKongDataExtractor
from data.processors.hong_kong_processor import HongKongDataProcessor

def test_processor():
    """Prueba completa del procesador de datos."""
    
    print("=== Prueba del Procesador de Hong Kong ===\n")
    
    # 1. Cargar datos usando el extractor
    print("1. Cargando datos...")
    extractor = HongKongDataExtractor()
    df_raw = extractor.download_season_data("2024-25")
    
    if df_raw is None:
        print("❌ No se pudieron cargar los datos")
        return
    
    print(f"   ✓ Datos cargados: {len(df_raw)} registros")
    print(f"   ✓ Columnas originales: {df_raw.columns.tolist()}")
    print()
    
    # 2. Procesar datos
    print("2. Procesando datos...")
    processor = HongKongDataProcessor()
    df_processed = processor.process_season_data(df_raw, "2024-25")
    print()
    
    # 3. Mostrar información de los datos procesados
    print("3. Análisis de datos procesados:")
    if not df_processed.empty:
        print(f"   - Registros finales: {len(df_processed)}")
        print(f"   - Columnas finales: {df_processed.columns.tolist()}")
        print()
        
        # Mostrar primeras filas
        print("   Primeras 3 filas:")
        print(df_processed.head(3).to_string(index=False))
        print()
        
        # Mostrar tipos de datos
        print("   Tipos de datos:")
        for col, dtype in df_processed.dtypes.items():
            print(f"     {col}: {dtype}")
        print()
        
        # Verificar valores únicos para campos categóricos
        if 'result' in df_processed.columns:
            print(f"   Distribución de resultados:")
            result_counts = df_processed['result'].value_counts()
            for result, count in result_counts.items():
                print(f"     {result}: {count}")
        print()
        
        # Mostrar equipos únicos
        if 'home_team' in df_processed.columns:
            teams = sorted(set(df_processed['home_team'].unique().tolist() + 
                              df_processed['away_team'].unique().tolist()))
            print(f"   Equipos encontrados ({len(teams)}):")
            for i, team in enumerate(teams, 1):
                print(f"     {i}. {team}")
        print()
    
    # 4. Generar resumen estadístico
    print("4. Resumen estadístico:")
    summary = processor.get_player_summary(df_processed)
    print(json.dumps(summary, indent=2, default=str))
    print()
    
    # 5. Verificar integridad de datos
    print("5. Verificación de integridad:")
    
    # Verificar fechas
    if 'date' in df_processed.columns:
        date_range = df_processed['date'].max() - df_processed['date'].min()
        print(f"   ✓ Rango de fechas: {date_range.days} días")
    
    # Verificar datos faltantes
    missing_data = df_processed.isnull().sum()
    if missing_data.sum() > 0:
        print("   ⚠ Datos faltantes:")
        for col, count in missing_data[missing_data > 0].items():
            print(f"     {col}: {count} valores")
    else:
        print("   ✓ No hay datos faltantes")
    
    # Verificar duplicados
    duplicates = df_processed.duplicated().sum()
    if duplicates > 0:
        print(f"   ⚠ {duplicates} registros duplicados encontrados")
    else:
        print("   ✓ No hay registros duplicados")
    
    print()
    print("=== Prueba completada ===")

def test_edge_cases():
    """Prueba casos límite del procesador."""
    
    print("\n=== Prueba de Casos Límite ===\n")
    
    processor = HongKongDataProcessor()
    
    # 1. DataFrame vacío
    print("1. Probando DataFrame vacío...")
    import pandas as pd
    df_empty = pd.DataFrame()
    df_result = processor.process_season_data(df_empty, "2024-25")
    print(f"   Resultado: {'✓ OK' if df_result.empty else '❌ Error'}")
    
    # 2. DataFrame con datos inválidos
    print("2. Probando datos inválidos...")
    df_invalid = pd.DataFrame({
        'Date': ['2024-01-01', 'invalid_date', '2024-01-02'],
        'Player': ['Player A', 'Player B', ''],  # Cambiado de 'Home' a 'Player'
        'Team': ['Team C', '', 'Team D'],        # Cambiado de 'Away' a 'Team'
        'Goals': [1, 'invalid', -1],             # Cambiado de 'HomeGoals' a 'Goals'
        'Assists': [0, 2, 3]                     # Cambiado de 'AwayGoals' a 'Assists'
    })
    
    df_result = processor.process_season_data(df_invalid, "2024-25")
    print(f"   Registros válidos: {len(df_result)} de 3")
    
    print("\n=== Casos límite completados ===")

if __name__ == "__main__":
    test_processor()
    test_edge_cases()