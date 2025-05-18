"""
Script de prueba para el extractor de datos de Hong Kong.
Ejecutar desde la raíz del proyecto: python data/test_extractor.py
"""

import sys
from pathlib import Path

# Agregar el directorio raíz al path para imports
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from data.extractors.hong_kong_extractor import HongKongDataExtractor

def test_extractor():
    """Prueba básica del extractor."""
    
    print("=== Prueba del Extractor de Hong Kong ===\n")
    
    # Inicializar extractor
    extractor = HongKongDataExtractor()
    
    # 1. Verificar temporadas disponibles
    print("1. Temporadas disponibles:")
    seasons = extractor.get_available_seasons()
    for season in seasons:
        print(f"   - {season}")
    print()
    
    # 2. Verificar si hay actualizaciones
    current_season = "2024-25"
    print(f"2. Verificando actualizaciones para {current_season}:")
    needs_update, message = extractor.check_for_updates(current_season)
    print(f"   Necesita actualización: {needs_update}")
    print(f"   Mensaje: {message}")
    print()
    
    # 3. Descargar datos de la temporada actual
    print(f"3. Descargando datos de {current_season}:")
    df = extractor.download_season_data(current_season)
    
    if df is not None:
        print(f"   ✓ Descarga exitosa")
        print(f"   - Registros: {len(df)}")
        print(f"   - Columnas: {df.columns.tolist()}")
        print(f"   - Primeras 3 filas:")
        print(df.head(3).to_string(index=False))
    else:
        print("   ❌ Error en la descarga")
    print()
    
    # 4. Verificar información del cache
    print("4. Información del cache:")
    cache_info = extractor.get_cache_info()
    for season_key, info in cache_info.items():
        print(f"   {season_key}:")
        print(f"     - Última actualización: {info.get('last_updated', 'N/A')}")
        print(f"     - Tamaño: {info.get('file_size', 'N/A')} bytes")
        print(f"     - Archivo: {info.get('filename', 'N/A')}")
    print()
    
    # 5. Segunda descarga (debería usar cache)
    print(f"5. Segunda descarga (debería usar cache):")
    df2 = extractor.download_season_data(current_season)
    if df2 is not None:
        print(f"   ✓ Datos obtenidos del cache")
    print()
    
    print("=== Prueba completada ===")

if __name__ == "__main__":
    test_extractor()