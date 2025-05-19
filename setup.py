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
    env_example = Path('.env.example')
    
    if not env_file.exists():
        if env_example.exists():
            shutil.copy('.env.example', '.env')
            print("✓ Archivo .env creado desde .env.example")
            print("⚠️  IMPORTANTE: Revisa y ajusta las configuraciones en .env")
        else:
            # Crear un .env básico
            basic_env = """# Configuración básica
ADMIN_USER=admin
ADMIN_PASSWORD=admin
SECRET_KEY=dev-secret-key-change-in-production
DEBUG=True
CACHE_TYPE=filesystem
CACHE_DIR=./cache
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

def verify_installation():
    """Verifica que las dependencias principales estén instaladas."""
    required_packages = [
        'dash',
        'plotly',
        'pandas',
        'flask_login',
        'dash_bootstrap_components'
    ]
    
    missing_packages = []
    for package in required_packages:
        try:
            __import__(package)
            print(f"✓ {package} - OK")
        except ImportError:
            missing_packages.append(package)
            print(f"❌ {package} - FALTA")
    
    return len(missing_packages) == 0

def create_sample_data():
    """Crea archivos de datos de muestra si es necesario."""
    # Este paso es opcional ya que nuestro sistema genera datos automáticamente
    print("✓ Datos de muestra: Se generarán automáticamente")

def run_tests():
    """Ejecuta pruebas básicas del sistema."""
    print("\n🧪 Ejecutando pruebas básicas...")
    
    try:
        # Prueba de importación de módulos principales
        from data import HongKongDataManager
        from utils.auth import User
        from utils.cache import init_cache
        print("✓ Módulos principales - OK")
        
        # Prueba de inicialización del gestor de datos
        data_manager = HongKongDataManager(auto_load=False)
        print("✓ Gestor de datos - OK")
        
        return True
    except Exception as e:
        print(f"❌ Error en pruebas: {e}")
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
    
    # 5. Verificar instalación
    print("\n🔍 Verificando instalación...")
    if not verify_installation():
        print("❌ Error: Faltan dependencias importantes")
        sys.exit(1)
    
    # 6. Crear datos de muestra
    print("\n📊 Configurando datos...")
    create_sample_data()
    
    # 7. Ejecutar pruebas
    if not run_tests():
        print("⚠️  Advertencia: Algunas pruebas fallaron")
    
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