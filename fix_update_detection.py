#!/usr/bin/env python3
"""
Script para resetear el estado de detección de actualizaciones.
Usar cuando el sistema detecta cambios incorrectamente.
"""

import json
import os
from pathlib import Path
from datetime import datetime

def reset_update_detection():
    """Resetea completamente el estado de detección de actualizaciones."""
    
    cache_dir = Path("data/cache")
    
    # 1. Eliminar metadatos del extractor
    metadata_file = cache_dir / "metadata.json"
    if metadata_file.exists():
        print("🗑️ Eliminando metadata.json...")
        metadata_file.unlink()
    
    # 2. Limpiar timestamps problemáticos
    timestamp_file = cache_dir / "update_timestamps.json"
    if timestamp_file.exists():
        try:
            with open(timestamp_file, 'r') as f:
                timestamps = json.load(f)
            
            # Eliminar timestamps manuales problemáticos
            keys_to_remove = []
            for key in timestamps.keys():
                if 'manual' in key or '2024-25' in key:
                    keys_to_remove.append(key)
            
            for key in keys_to_remove:
                del timestamps[key]
                print(f"🗑️ Eliminado timestamp: {key}")
            
            # Guardar timestamps limpios
            with open(timestamp_file, 'w') as f:
                json.dump(timestamps, f, indent=2)
                
        except Exception as e:
            print(f"Error procesando timestamps: {e}")
    
    # 3. Eliminar cache de info de GitHub
    for file in cache_dir.glob("file_info_*.json"):
        print(f"🗑️ Eliminando cache de GitHub: {file.name}")
        file.unlink()
    
    print("✅ Estado de detección de actualizaciones reseteado")
    print("🔄 La próxima vez que ejecutes la app, se verificará el estado real desde GitHub")

if __name__ == "__main__":
    print("🔧 Reseteando estado de detección de actualizaciones...")
    reset_update_detection()