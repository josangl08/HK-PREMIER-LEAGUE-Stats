# ABOUTME: System for multi-user authentication using SQLAlchemy database.
# ABOUTME: Integrates with Flask-Login and handles Users, Roles, and Player/Agent associations.

import logging
from typing import Optional, List, Dict, Any
from werkzeug.security import check_password_hash, generate_password_hash
from sqlalchemy import select
from sqlalchemy.orm import joinedload
from models.db_models import User, Role, UserPlayerLink, Player, Team
from utils.db_engine import Session

# Configurar logging
logger = logging.getLogger(__name__)

class AuthRepository:
    """
    Repositorio para la gestión de usuarios mediante SQLAlchemy.
    Centraliza las consultas de autenticación y permisos.
    """
    
    @staticmethod
    def get_user_by_id(user_id: str) -> Optional[User]:
        """Obtiene un usuario por su ID único con carga ansiosa de relaciones."""
        session = Session()
        try:
            stmt = (
                select(User)
                .options(joinedload(User.role_obj), joinedload(User.player_link))
                .where(User.id == user_id)
            )
            user = session.execute(stmt).unique().scalar_one_or_none()
            return user
        except Exception as e:
            logger.error(f"Error al obtener usuario {user_id}: {e}")
            return None
        finally:
            session.close()

    @staticmethod
    def get_user_by_username(username: str) -> Optional[User]:
        """Obtiene un usuario por su nombre de usuario con carga ansiosa de relaciones."""
        session = Session()
        try:
            stmt = (
                select(User)
                .options(joinedload(User.role_obj), joinedload(User.player_link))
                .where(User.username == username)
            )
            user = session.execute(stmt).unique().scalar_one_or_none()
            return user
        except Exception as e:
            logger.error(f"Error al obtener usuario {username}: {e}")
            return None
        finally:
            session.close()

    @classmethod
    def get_user(cls, username: str) -> Optional[User]:
        """Alias de compatibilidad para buscar por username."""
        return cls.get_user_by_username(username)

    @classmethod
    def validate_credentials(cls, username: str, password: str) -> Optional[User]:
        """
        Valida las credenciales y retorna el objeto User si son correctas.
        Actualiza el campo last_login en caso de éxito.
        """
        user = cls.get_user_by_username(username)
        
        if not user:
            logger.warning(f"Intento de login: Usuario no encontrado: {username}")
            return None
            
        if check_password_hash(user.password_hash, password):
            logger.info(f"Login exitoso para: {username}")
            
            # Actualizar last_login
            session = Session()
            try:
                db_user = session.get(User, user.id)
                if db_user:
                    db_user.last_login = datetime.utcnow()
                    session.commit()
            except Exception as e:
                logger.error(f"Error al actualizar last_login para {username}: {e}")
            finally:
                session.close()
                
            return user
            
        logger.warning(f"Intento de login: Contraseña incorrecta para: {username}")
        return None

    @staticmethod
    def create_user(username: str, password: str, role: str,
                    player_name: Optional[str] = None,
                    managed_players: Optional[List[str]] = None,
                    player_profile: Optional[Dict[str, Any]] = None,
                    player_id: Optional[str] = None,
                    agent_profile: Optional[Dict[str, Any]] = None) -> bool:
        """
        Crea un nuevo usuario en la base de datos (Compatible con callbacks antiguos).
        """
        session = Session()
        try:
            # 1. Obtener el rol
            role_stmt = select(Role).where(Role.name == role.capitalize())
            role_obj = session.execute(role_stmt).scalar_one_or_none()
            if not role_obj:
                logger.error(f"Rol no encontrado: {role}")
                return False

            # 2. Crear el usuario
            new_user = User(
                id=username,
                username=username,
                email=f"{username}@example.com", # Email temporal
                password_hash=generate_password_hash(password),
                role_id=role_obj.id,
                profile_data={
                    "player_profile": player_profile or {},
                    "agent_profile": agent_profile or {}
                }
            )
            session.add(new_user)
            
            # 3. Si es un jugador, verificar/crear el registro Player y crear el vínculo
            if player_id:
                # Ensure the Player entity exists before creating the FK link
                existing_player = session.get(Player, player_id)
                if existing_player is None and player_name:
                    profile = player_profile or {}
                    team_id = None
                    team_name = profile.get("team")
                    if team_name:
                        team_obj = session.execute(
                            select(Team).where(Team.name == team_name)
                        ).scalars().first()
                        if team_obj:
                            team_id = team_obj.id
                    new_player = Player(
                        id=player_id,
                        name=player_name,
                        position_main=profile.get("position"),
                        age=profile.get("age"),
                        foot=profile.get("foot"),
                        height=profile.get("height"),
                        current_team_id=team_id,
                    )
                    session.add(new_player)
                    logger.info(
                        f"Player record created for '{player_name}' (id={player_id}) "
                        f"during user registration."
                    )
                link = UserPlayerLink(user_id=username, player_id=player_id)
                session.add(link)
            
            # 4. Si es un agente y tiene jugadores, vincularlos (Relacional)
            if managed_players:
                for pid in managed_players:
                    player = session.get(Player, pid)
                    if player:
                        new_user.managed_players.append(player)
            
            session.commit()
            logger.info(f"Usuario {username} creado exitosamente en SQL.")
            return True
        except Exception as e:
            session.rollback()
            logger.error(f"Error al crear usuario {username}: {e}")
            return False
        finally:
            session.close()

    @classmethod
    def sync_admin_from_env(cls) -> bool:
        """Sincroniza el usuario admin desde las variables de entorno a SQL."""
        import os
        admin_user = os.getenv("ADMIN_USER")
        admin_password = os.getenv("ADMIN_PASSWORD")
        
        if not admin_user or not admin_password:
            logger.error("ADMIN_USER o ADMIN_PASSWORD no configurados en .env")
            return False
            
        session = Session()
        try:
            # 1. Asegurar que existe el rol Admin
            role_stmt = select(Role).where(Role.name == "Admin")
            role = session.execute(role_stmt).scalar_one_or_none()
            if not role:
                role = Role(name="Admin", description="Administrador del sistema")
                session.add(role)
                session.flush()

            # 2. Buscar o crear el usuario admin
            stmt = select(User).where(User.username == admin_user)
            user = session.execute(stmt).scalar_one_or_none()
            
            if not user:
                user = User(
                    id=admin_user,
                    username=admin_user,
                    email=f"{admin_user}@hkpl.com",
                    password_hash=generate_password_hash(admin_password),
                    role_id=role.id
                )
                session.add(user)
            else:
                # Actualizar contraseña si cambió en el .env
                user.password_hash = generate_password_hash(admin_password)
                user.role_id = role.id
            
            session.commit()
            logger.info(f"Admin '{admin_user}' sincronizado desde .env a la base de datos.")
            return True
        except Exception as e:
            session.rollback()
            logger.error(f"Error en sincronización de admin: {e}")
            return False
        finally:
            session.close()

# ── Flask-Login Integration ──────────────────────────────────────────────────

def load_user(user_id: str) -> Optional[User]:
    """
    Cargador de usuarios requerido por Flask-Login.
    IMPORTANTE: Flask-Login necesita que el objeto User esté 'vivo'. 
    En entornos con Scoped Session, esto funciona bien.
    """
    return AuthRepository.get_user_by_id(user_id)

def validate_credentials(username: str, password: str) -> Optional[User]:
    """Interfaz simplificada para los callbacks de login."""
    return AuthRepository.validate_credentials(username, password)
