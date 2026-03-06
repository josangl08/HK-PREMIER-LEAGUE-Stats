import os
import dash
from dash import html, dcc
import dash_bootstrap_components as dbc
from flask_login import LoginManager, current_user
import logging

# Configurar logging básico
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Cargar variables de entorno
from dotenv import load_dotenv
load_dotenv()

# Importar componentes propios
try:
    from utils.auth import load_user
    from utils.cache import init_cache
    from data.hong_kong_data_manager import HongKongDataManager
    logger.info("✓ Módulos y utilidades importados correctamente")
except ImportError as e:
    logger.error(f"❌ Error importando utilidades: {e}")
    raise

# Inicializar la aplicación Dash con tema Bootstrap
app = dash.Dash(
    __name__,
    suppress_callback_exceptions=True,
    external_stylesheets=[
        dbc.themes.BOOTSTRAP,
        "https://fonts.googleapis.com/css2?family=Roboto:wght@400;500;700&display=swap",
        "https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css"
    ],
    meta_tags=[
        {"name": "viewport", "content": "width=device-width, initial-scale=1"},
        {"name": "description", "content": "Sports Dashboard - Liga de Hong Kong"},
        {"name": "author", "content": "Sports Analytics Team"}
    ],
    title="Sports Dashboard"
)

# Configuraciones básicas de la aplicación
app.title = "Hong Kong Premier League Dashboard"
# app._favicon = "assets/favicon.ico"  # Si tienes un favicon
server = app.server

# Configuración de Flask
server.config.update(
    SECRET_KEY=os.getenv("SECRET_KEY"),
    WTF_CSRF_ENABLED=False  # Deshabilitar CSRF para simplicidad en desarrollo
)

# Inicializar el sistema de caché
try:
    cache = init_cache(app)
    logger.info("✓ El sistema de caché se ha inicializado correctamente")
except Exception as e:
    logger.warning(f"⚠️ Warning: Error en la inicialización de la caché: {e}")

# Configurar autenticación con Flask-Login
login_manager = LoginManager()
login_manager.init_app(server)

# Configurar la vista de login y mensajes
# Nota: algunos linters pueden mostrar warnings sobre login_view, pero es funcional
login_manager.login_view = '/login'  # type: ignore
login_manager.login_message = 'Por favor inicia sesión para acceder a esta página.'
login_manager.login_message_category = 'info'

@login_manager.user_loader
def load_user_from_id(user_id):
    """Callback requerido por Flask-Login para cargar usuarios."""
    return load_user(user_id)

# ==============================================================================
# INICIALIZACIÓN DEL GESTOR DE DATOS
# ==============================================================================
# IMPORTANTE: En modo debug, Flask usa un reloader que crea 2 procesos:
# - Proceso padre: monitorea cambios en archivos
# - Proceso hijo: ejecuta la aplicación real
# Solo debemos inicializar en el proceso hijo (cuando WERKZEUG_RUN_MAIN=true)
# ==============================================================================

def is_werkzeug_reloader_process():
    """Verifica si estamos en el proceso padre del reloader de Werkzeug."""
    return os.environ.get('WERKZEUG_RUN_MAIN') != 'true'

# Solo inicializar si NO estamos en el proceso padre del reloader
if not is_werkzeug_reloader_process():
    logger.info("Inicializando el gestor de datos y refrescando al inicio...")
    try:
        data_manager = HongKongDataManager(auto_load=False)
        if not data_manager.refresh_data():
            logger.warning("No se pudieron refrescar los datos iniciales. La app podría usar datos desactualizados.")
        else:
            logger.info("✓ Datos iniciales refrescados y listos.")
    except Exception as e:
        logger.critical(f"❌ Error fatal al inicializar DataManager: {e}", exc_info=True)
        class DummyDataManager:
            def __getattr__(self, name):
                def method(*args, **kwargs):
                    logger.error(f"Llamada a '{name}' en DataManager dummy debido a un error de inicialización.")
                    return {} if "get" in name or "status" in name else []
                return method
        data_manager = DummyDataManager()

    # ==============================================================================
    # REGISTRO EN APP CONTEXT (evita importaciones circulares)
    # ==============================================================================
    # IMPORTANTE: Esto DEBE hacerse ANTES de importar los callbacks
    # Los callbacks usarán get_hong_kong_data_manager() para obtener esta instancia
    # ==============================================================================
    from utils.app_context import set_hong_kong_data_manager
    set_hong_kong_data_manager(data_manager)
    logger.info("✓ DataManager registrado en app context (singleton pattern)")

    # Sincronizar admin desde .env → data/users.json (Admin Safety Sync)
    from utils.auth import AuthRepository
    try:
        AuthRepository.sync_admin_from_env()
        logger.info("✓ Admin sincronizado desde .env en users.json")
    except Exception as e:
        logger.error(f"❌ Error en Admin Safety Sync: {e}")
else:
    logger.info("⏳ Proceso padre del reloader - esperando al proceso hijo...")

# ==============================================================================
# IMPORTACIÓN DE CALLBACKS
# ==============================================================================
# Se importan después de que 'app' y 'data_manager' están definidos y registrados
# Los callbacks ahora usan app_context para evitar crear instancias duplicadas
#
# NOTA: Solo importar callbacks activos. El módulo 'injuries' está deshabilitado
# por configuración (ENABLE_INJURIES=False por defecto)
# ==============================================================================
ENABLE_INJURIES_MODULE = os.getenv("ENABLE_INJURIES", "False").lower() == "true"

import callbacks.auth_callbacks
import callbacks.navigation_callbacks
import callbacks.home_callbacks
import callbacks.performance_callbacks

if ENABLE_INJURIES_MODULE:
    import callbacks.injuries_callbacks
    logger.info("✓ Módulo de lesiones habilitado")
else:
    logger.info("⚠️ Módulo de lesiones deshabilitado (ENABLE_INJURIES=False)")

logger.info("✓ Callbacks importados correctamente.")

# Definir layout principal de la aplicación
app.layout = dbc.Container([
    # Location component para manejar la navegación
    dcc.Location(id='url', refresh=False),
    
    # Container para el navbar (se llena dinámicamente)
    html.Div(id='navbar-container'),
    
    # Container para el contenido de la página, envuelto en el nuevo contenedor principal
    html.Div(
        html.Div(id='page-content', className="fadeIn"),
        className="main-container"
    ),
    
    # Stores globales para la aplicación
    dcc.Store(id='login-status', storage_type='session'),
    # Toggle de tema (claro/oscuro)
    dcc.Store(id='app-theme', storage_type='local', data='light'),
    
    # Componente para downloads
    html.Div(id='download-components')
    
], fluid=True, className="p-0")

def run_app(debug=None, host=None, port=None):
    """
    Función helper para ejecutar la aplicación con configuraciones personalizadas.
    """
    # Configuraciones por defecto
    debug_mode = debug if debug is not None else os.getenv("DEBUG", "True").lower() == "true"
    host_address = host if host is not None else os.getenv("HOST", "127.0.0.1")
    port_number = port if port is not None else int(os.getenv("PORT", "8050"))
    
    logger.info(f"""
╔══════════════════════════════════════════════════════════════╗
║                    SPORTS DASHBOARD                          ║
║                Liga de Hong Kong                             ║
╠══════════════════════════════════════════════════════════════╣
║  🌐 URL: http://{host_address}:{port_number}                 ║
║  🔒 Usuario: admin                                           ║
║  🔑 Contraseña: admin                                        ║
║  🐞 Debug: {'Activado' if debug_mode else 'Desactivado'}     ║
╚══════════════════════════════════════════════════════════════╝
    """)
    
    try:
        app.run(
            debug=debug_mode,
            host=host_address,
            port=port_number,
            dev_tools_ui=debug_mode,
            dev_tools_props_check=debug_mode,
            dev_tools_hot_reload=True,
            use_reloader=True       
        )
    except Exception as e:
        logger.error(f"❌ Error al iniciar la aplicación: {e}")
        logger.info("💡 Consejos:")
        logger.info("  - Verifica que el puerto no esté en uso")
        logger.info("  - Revisa las variables de entorno")
        logger.info("  - Asegúrate de que todas las dependencias están instaladas")

# Punto de entrada principal
if __name__ == '__main__':
    # Verificar que las variables de entorno críticas estén configuradas
    required_env_vars = ['ADMIN_USER', 'ADMIN_PASSWORD']
    missing_vars = [var for var in required_env_vars if not os.getenv(var)]
    
    if missing_vars:
        logger.warning(f"⚠️ Advertencia: Variables de entorno faltantes: {missing_vars}")
        logger.info("📖 Consulta el archivo README.md para configuración inicial")
    
    # Ejecutar la aplicación
    run_app()