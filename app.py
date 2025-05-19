import os
import dash
from dash import html, dcc
import dash_bootstrap_components as dbc
from flask_login import LoginManager, current_user
from dotenv import load_dotenv
import logging

# Configurar logging básico
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Cargar variables de entorno
load_dotenv()

# Importar componentes propios
try:
    from utils.auth import User, load_user
    from utils.cache import init_cache
    logger.info("✓ Módulos de utilidades importados correctamente")
except ImportError as e:
    logger.error(f"❌ Error importando utilidades: {e}")
    raise

# Importar todos los callbacks - esto registrará los callbacks automáticamente
try:
    import callbacks
    logger.info("✓ Callbacks importados correctamente")
except ImportError as e:
    logger.error(f"❌ Error importando callbacks: {e}")
    raise

# Inicializar la aplicación Dash con tema Bootstrap
app = dash.Dash(
    __name__,
    suppress_callback_exceptions=True,
    external_stylesheets=[
        dbc.themes.BOOTSTRAP,
        "https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap"
    ],
    meta_tags=[
        {"name": "viewport", "content": "width=device-width, initial-scale=1"},
        {"name": "description", "content": "Sports Dashboard - Liga de Hong Kong"},
        {"name": "author", "content": "Sports Analytics Team"}
    ],
    title="Sports Dashboard"
)

# Configuraciones básicas de la aplicación
app.title = "Sports Dashboard - Liga de Hong Kong"
# app._favicon = "assets/favicon.ico"  # Si tienes un favicon
server = app.server

# Configuración de Flask
server.config.update(
    SECRET_KEY=os.getenv("SECRET_KEY", "dev-secret-key-change-in-production"),
    WTF_CSRF_ENABLED=False  # Deshabilitar CSRF para simplicidad en desarrollo
)

# Inicializar el sistema de caché
try:
    cache = init_cache(app)
    print("✓ Cache system initialized successfully")
except Exception as e:
    print(f"⚠️ Warning: Cache initialization failed: {e}")

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

# Definir layout principal de la aplicación
app.layout = dbc.Container([
    # Location component para manejar la navegación
    dcc.Location(id='url', refresh=False),
    
    # Container para el navbar (se llena dinámicamente)
    html.Div(id='navbar-container'),
    
    # Container para el contenido de la página
    html.Div(id='page-content', className="fadeIn"),
    
    # Stores globales para la aplicación
    dcc.Store(id='login-status', storage_type='session'),
    dcc.Store(id='app-theme', storage_type='local', data='light'),
    
    # Componente para downloads
    html.Div(id='download-components')
    
], fluid=True, className="p-0")

# Callback para manejar el tema de la aplicación (opcional)
@app.callback(
    dash.dependencies.Output('app-theme', 'data'),
    [dash.dependencies.Input('url', 'pathname')],
    prevent_initial_call=True
)
def update_theme(pathname):
    """Callback opcional para manejar temas dinámicos."""
    # Por ahora retorna el tema por defecto
    return 'light'

def run_app(debug=None, host=None, port=None):
    """
    Función helper para ejecutar la aplicación con configuraciones personalizadas.
    """
    # Configuraciones por defecto
    debug_mode = debug if debug is not None else os.getenv("DEBUG", "True").lower() == "true"
    host_address = host if host is not None else os.getenv("HOST", "127.0.0.1")
    port_number = port if port is not None else int(os.getenv("PORT", "8050"))
    
    print(f"""
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
            dev_tools_hot_reload=False,  
            use_reloader=False       
        )
    except Exception as e:
        print(f"❌ Error al iniciar la aplicación: {e}")
        print("💡 Consejos:")
        print("  - Verifica que el puerto no esté en uso")
        print("  - Revisa las variables de entorno")
        print("  - Asegúrate de que todas las dependencias están instaladas")

# Punto de entrada principal
if __name__ == '__main__':
    # Verificar que las variables de entorno críticas estén configuradas
    required_env_vars = ['ADMIN_USER', 'ADMIN_PASSWORD']
    missing_vars = [var for var in required_env_vars if not os.getenv(var)]
    
    if missing_vars:
        print(f"⚠️ Advertencia: Variables de entorno faltantes: {missing_vars}")
        print("📖 Consulta el archivo README.md para configuración inicial")
    
    # Ejecutar la aplicación
    run_app()