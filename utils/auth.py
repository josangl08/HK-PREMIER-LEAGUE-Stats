# ABOUTME: Repository for multi-user authentication with JSON persistence and hashing.
# ABOUTME: Implements AuthRepository, User model, and Flask-Login integration.

import os
import json
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv

# Configurar logging
logger = logging.getLogger(__name__)

# Cargar variables de entorno
load_dotenv()

# Ruta al archivo de persistencia
USERS_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'users.json')

class User(UserMixin):
    """
    Clase User para Flask-Login con soporte para roles.
    """
    
    def __init__(self, username: str, role: str, player_name: Optional[str] = None, managed_players: Optional[List[str]] = None):
        """
        Inicializa un usuario.
        
        Args:
            username: Nombre de usuario (ID único)
            role: Rol del usuario (admin, player, agent)
            player_name: Nombre del jugador asociado (si aplica)
            managed_players: Lista de jugadores gestionados (si aplica)
        """
        self.id = username
        self.username = username
        self.role = role
        self.player_name = player_name
        self.managed_players = managed_players or []
        
    def get_id(self):
        """Retorna el ID del usuario para Flask-Login."""
        return self.id
    
    @property
    def is_authenticated(self):
        return True
    
    @property
    def is_active(self):
        return True
    
    @property
    def is_anonymous(self):
        return False

class AuthRepository:
    """
    Repositorio para la gestión de usuarios en data/users.json.
    Sigue el patrón Repository para aislar el I/O.
    """
    
    @staticmethod
    def _load_all_users() -> Dict[str, Any]:
        """Carga todos los usuarios desde el archivo JSON."""
        if not os.path.exists(USERS_FILE):
            return {}
        try:
            with open(USERS_FILE, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Error al cargar usuarios desde {USERS_FILE}: {e}")
            return {}

    @staticmethod
    def _save_all_users(users: Dict[str, Any]) -> bool:
        """Guarda todos los usuarios en el archivo JSON de forma atómica."""
        temp_file = USERS_FILE + '.tmp'
        try:
            # Asegurar que el directorio data existe
            os.makedirs(os.path.dirname(USERS_FILE), exist_ok=True)
            
            with open(temp_file, 'w') as f:
                json.dump(users, f, indent=4)
            
            # Escritura atómica (write-then-rename)
            os.replace(temp_file, USERS_FILE)
            return True
        except Exception as e:
            logger.error(f"Error al guardar usuarios en {USERS_FILE}: {e}")
            if os.path.exists(temp_file):
                os.remove(temp_file)
            return False

    @classmethod
    def get_user(cls, username: str) -> Optional[User]:
        """Obtiene un usuario por su username."""
        users = cls._load_all_users()
        user_data = users.get(username)
        
        if not user_data:
            return None
            
        return User(
            username=username,
            role=user_data.get('role', 'player'),
            player_name=user_data.get('player_name'),
            managed_players=user_data.get('managed_players', [])
        )

    @classmethod
    def create_user(cls, username: str, password: str, role: str, 
                    player_name: Optional[str] = None, 
                    managed_players: Optional[List[str]] = None) -> bool:
        """Crea un nuevo usuario con contraseña hasheada."""
        users = cls._load_all_users()
        
        if username in users:
            logger.warning(f"Intento de crear usuario existente: {username}")
            return False
            
        users[username] = {
            'role': role,
            'password_hash': generate_password_hash(password),
            'player_name': player_name,
            'managed_players': managed_players or [],
            'created_at': datetime.now(timezone.utc).isoformat()
        }
        
        return cls._save_all_users(users)

    @classmethod
    def validate_credentials(cls, username: str, password: str) -> Optional[User]:
        """Valida las credenciales de un usuario contra el hash almacenado."""
        users = cls._load_all_users()
        user_data = users.get(username)
        
        if not user_data:
            logger.warning(f"Usuario no encontrado: {username}")
            return None
            
        if check_password_hash(user_data.get('password_hash', ''), password):
            logger.info(f"Login exitoso para usuario: {username}")
            return cls.get_user(username)
            
        logger.warning(f"Contraseña incorrecta para usuario: {username}")
        return None

    @classmethod
    def sync_admin_from_env(cls) -> bool:
        """Sincroniza el usuario admin desde las variables de entorno."""
        admin_user = os.getenv("ADMIN_USER")
        admin_password = os.getenv("ADMIN_PASSWORD")
        
        if not admin_user or not admin_password:
            logger.error("ADMIN_USER o ADMIN_PASSWORD no configurados en .env")
            return False
            
        users = cls._load_all_users()
        
        # Si el admin no existe o cambió, lo actualizamos/creamos
        # Nota: Siempre generamos un nuevo hash si viene de .env para asegurar 
        # que el .env sea el "root of trust"
        users[admin_user] = {
            'role': 'admin',
            'password_hash': generate_password_hash(admin_password),
            'player_name': None,
            'managed_players': [],
            'created_at': users.get(admin_user, {}).get('created_at', datetime.now(timezone.utc).isoformat()),
            'synced_at': datetime.now(timezone.utc).isoformat()
        }
        
        logger.info(f"Admin '{admin_user}' sincronizado desde .env")
        return cls._save_all_users(users)

def load_user(user_id: str) -> Optional[User]:
    """Cargador de usuarios para Flask-Login delegado al repositorio."""
    return AuthRepository.get_user(user_id)

def validate_credentials(username: str, password: str) -> Optional[User]:
    """Validador de credenciales delegado al repositorio."""
    return AuthRepository.validate_credentials(username, password)
