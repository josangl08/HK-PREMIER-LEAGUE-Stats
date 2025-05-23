#!/usr/bin/env python3
"""
Script de inicialización para Sports Dashboard
Configura el entorno y verifica que todo esté listo para ejecutar.
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

def print_banner():
    """Imprime el banner de bienvenida."""
    print("""
╔══════════════════════════════════════════════════════════════╗
║            SPORTS DASHBOARD - CONFIGURACIÓN INICIAL          ║
║                   Liga de Hong Kong                         ║
╚══════════════════════════════════════════════════════════════╝
    """)

def check_python_version():
    """Verifica que se esté usando Python 3.8 o superior."""
    if sys.version_info < (3, 8):
        print("❌ Error: Se requiere Python 3.8 o superior")
        print(f"   Versión actual: {sys.version}")
        return False
    else:
        print(f"✓ Python {sys.version.split()[0]} - OK")
        return True

def create_directories():
    """Crea directorios necesarios si no existen."""
    directories = [
        'assets',
        'cache',
        'logs',
        'data/cache',
        'data/exports'
    ]
    
    for directory in directories:
        path = Path(directory)
        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)
            print(f"✓ Directorio creado: {directory}")
        else:
            print(f"✓ Directorio existe: {directory}")

def setup_environment():
    """Configura las variables de entorno."""
    env_file = Path('.env')
    
    if not env_file.exists():
        # Crear un .env básico
        basic_env = """# Configuración básica
APP_NAME="Hong Kong Premier League Dashboard"
APP_VERSION="1.0.0"
DEBUG=True
# Configuración de servidor
HOST=127.0.0.1
PORT=8050
# Configuración de autenticación
ADMIN_USER=admin
ADMIN_PASSWORD=admin
SECRET_KEY=dev-secret-key-change-in-production
# Configuración de cache
CACHE_TYPE=filesystem
CACHE_DIR=./cache
CACHE_DEFAULT_TIMEOUT=300
"""
        with open('.env', 'w') as f:
            f.write(basic_env)
        print("✓ Archivo .env básico creado")
    else:
        print("✓ Archivo .env ya existe")

def install_dependencies():
    """Instala las dependencias del proyecto."""
    if not Path('requirements.txt').exists():
        print("❌ Error: requirements.txt no encontrado")
        return False
    
    try:
        print("📦 Instalando dependencias...")
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt'])
        print("✓ Dependencias instaladas correctamente")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Error instalando dependencias: {e}")
        return False

def main():
    """Función principal del script de inicialización."""
    print_banner()
    
    print("🔍 Verificando entorno...")
    
    # 1. Verificar Python
    if not check_python_version():
        sys.exit(1)
    
    # 2. Crear directorios
    print("\n📁 Configurando directorios...")
    create_directories()
    
    # 3. Configurar entorno
    print("\n⚙️  Configurando entorno...")
    setup_environment()
    
    # 4. Instalar dependencias
    print("\n📦 Configurando dependencias...")
    if not install_dependencies():
        print("❌ Error: No se pudieron instalar todas las dependencias")
        sys.exit(1)
    
    print("""
╔══════════════════════════════════════════════════════════════╗
║                    ✅ CONFIGURACIÓN COMPLETA                 ║
╠══════════════════════════════════════════════════════════════╣
║  Para ejecutar la aplicación:                               ║
║                                                              ║
║  $ python app.py                                            ║
║                                                              ║
║  🌐 URL: http://127.0.0.1:8050                              ║
║  👤 Usuario: admin                                          ║
║  🔑 Contraseña: admin                                       ║
╚══════════════════════════════════════════════════════════════╝
    """)

if __name__ == '__main__':
    main()