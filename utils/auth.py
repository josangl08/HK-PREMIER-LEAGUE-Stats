import os
from flask_login import UserMixin
from dotenv import load_dotenv
import logging

# Configurar logging
logger = logging.getLogger(__name__)

# Cargar variables de entorno
load_dotenv()

class User(UserMixin):
    """
    Clase User para Flask-Login.
    Representa un usuario autenticado en el sistema.
    """
    
    def __init__(self, user_id: str):
        """
        Inicializa un usuario.
        
        Args:
            user_id: ID único del usuario
        """
        self.id = user_id
        self.name = user_id  # Más flexible que hardcodear "admin"
        self.password = os.getenv("ADMIN_PASSWORD")
        
    def get_id(self):
        """Retorna el ID del usuario para Flask-Login."""
        return self.id
    
    @property
    def is_authenticated(self):
        """Usuario siempre autenticado si existe la instancia."""
        return True
    
    @property
    def is_active(self):
        """Usuario siempre activo si existe la instancia."""
        return True
    
    @property
    def is_anonymous(self):
        """Usuario nunca es anónimo si existe la instancia."""
        return False

from typing import Optional

def load_user(user_id: str) -> Optional[User]:
    """
    Función requerida por Flask-Login para cargar un usuario.
    
    Args:
        user_id: ID del usuario a cargar
        
    Returns:
        Instancia de User si es válido, None si no
    """
    admin_user = os.getenv("ADMIN_USER")
    
    if not admin_user:
        logger.warning("ADMIN_USER no está configurado en variables de entorno")
        return None
    
    if user_id == admin_user:
        return User(user_id)
    
    return None

def validate_credentials(username: str, password: str) -> Optional[User]:
    """
    Valida las credenciales de un usuario.
    
    Args:
        username: Nombre de usuario
        password: Contraseña
        
    Returns:
        Instancia de User si las credenciales son válidas, None si no
    """
    # Validar entrada
    if not username or not password:
        logger.warning("Intento de login con credenciales vacías")
        return None
    
    admin_user = os.getenv("ADMIN_USER")
    admin_password = os.getenv("ADMIN_PASSWORD")
    
    # Verificar que las variables de entorno estén configuradas
    if not admin_user or not admin_password:
        logger.error("Variables de entorno de autenticación no configuradas")
        return None
    
    # Validar credenciales
    if username == admin_user and password == admin_password:
        logger.info(f"Login exitoso para usuario: {username}")
        return User(username)
    
    logger.warning(f"Intento de login fallido para usuario: {username}")
    return None