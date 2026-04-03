# ABOUTME: Database models for SQLAlchemy matching the entire application data architecture.
# ABOUTME: Includes Identity, Core entities, Performance, Design, and System metadata.

from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy import String, Integer, Float, Boolean, DateTime, ForeignKey, Text, JSON, Table, Column, LargeBinary
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from flask_login import UserMixin

class Base(DeclarativeBase):
    pass

# Tabla intermedia para Agentes y los Jugadores que representan
agent_player_links = Table(
    "agent_player_links",
    Base.metadata,
    Column("agent_id", String(50), ForeignKey("users.id"), primary_key=True),
    Column("player_id", String(100), ForeignKey("players.id"), primary_key=True),
)

# ==============================================================================
# 1. IDENTIDAD Y ACCESO
# ==============================================================================

class Role(Base):
    __tablename__ = "roles"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False) # Admin, Player, Agent
    description: Mapped[Optional[str]] = mapped_column(String(200))
    
    users: Mapped[List["User"]] = relationship(back_populates="role_obj")


class User(Base, UserMixin):
    __tablename__ = "users"
    
    id: Mapped[str] = mapped_column(String(50), primary_key=True) # UUID or standard ID
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id"), nullable=False)
    
    # Datos flexibles (Perfil de agente, preferencias, etc.)
    profile_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime)
    
    role_obj: Mapped["Role"] = relationship(back_populates="users")
    
    # Vínculo si es un usuario de tipo "Player" (1 a 1)
    player_link: Mapped[Optional["UserPlayerLink"]] = relationship(back_populates="user")
    
    # Vínculo si es un usuario de tipo "Agent" (1 a N)
    managed_players: Mapped[List["Player"]] = relationship(
        secondary=agent_player_links, back_populates="agents"
    )

    # Propiedades de compatibilidad con el sistema antiguo
    @property
    def role_name(self) -> str:
        return self.role_obj.name.lower() if self.role_obj else "player"

    @property
    def role(self) -> str:
        """Alias para compatibilidad con callbacks antiguos."""
        return self.role_name

    @property
    def player_id(self) -> Optional[str]:
        return self.player_link.player_id if self.player_link else None

    @property
    def player_name(self) -> Optional[str]:
        return self.player_link.player.name if self.player_link and self.player_link.player else None


# ==============================================================================
# 2. ENTIDADES CORE
# ==============================================================================

class Season(Base):
    __tablename__ = "seasons"
    
    id: Mapped[str] = mapped_column(String(20), primary_key=True) # e.g. "2024-25"
    is_current: Mapped[bool] = mapped_column(Boolean, default=False)
    last_github_sync: Mapped[Optional[datetime]] = mapped_column(DateTime)


class Team(Base):
    __tablename__ = "teams"
    
    id: Mapped[str] = mapped_column(String(100), primary_key=True) # Slug e.g. "kitchee"
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    tm_id: Mapped[Optional[int]] = mapped_column(Integer) # Transfermarkt ID
    logo_url: Mapped[Optional[str]] = mapped_column(String(255))
    
    # Enriquecimiento TheSportsDB
    tsdb_id: Mapped[Optional[int]] = mapped_column(Integer) # idTeam
    formed_year: Mapped[Optional[int]] = mapped_column(Integer)
    
    # Estadio (Info fija del equipo)
    stadium_name: Mapped[Optional[str]] = mapped_column(String(200))
    stadium_id: Mapped[Optional[int]] = mapped_column(Integer) # idVenue
    stadium_capacity: Mapped[Optional[int]] = mapped_column(Integer)
    stadium_thumb: Mapped[Optional[str]] = mapped_column(String(255))
    stadium_location: Mapped[Optional[str]] = mapped_column(String(200))
    
    # Redes y Bio
    website: Mapped[Optional[str]] = mapped_column(String(255))
    facebook: Mapped[Optional[str]] = mapped_column(String(255))
    twitter: Mapped[Optional[str]] = mapped_column(String(255))
    instagram: Mapped[Optional[str]] = mapped_column(String(255))
    description_en: Mapped[Optional[str]] = mapped_column(Text)
    
    players: Mapped[List["Player"]] = relationship(back_populates="current_team")
    aliases: Mapped[List["TeamAlias"]] = relationship(back_populates="team")


class TeamAlias(Base):
    __tablename__ = "team_aliases"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    team_id: Mapped[str] = mapped_column(ForeignKey("teams.id"), nullable=False)
    alias: Mapped[str] = mapped_column(String(150), nullable=False) # e.g. "傑志"
    
    team: Mapped["Team"] = relationship(back_populates="aliases")


class Player(Base):
    __tablename__ = "players"
    
    id: Mapped[str] = mapped_column(String(100), primary_key=True) # Slug e.g. "eduardo-praes"
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    tm_id: Mapped[Optional[int]] = mapped_column(Integer) # Transfermarkt ID
    
    nationality: Mapped[Optional[str]] = mapped_column(String(100)) # Pasaporte/Nacionalidad deportiva
    birth_country: Mapped[Optional[str]] = mapped_column(String(100)) # Lugar de nacimiento real
    position_main: Mapped[Optional[str]] = mapped_column(String(50))
    foot: Mapped[Optional[str]] = mapped_column(String(20))
    height: Mapped[Optional[int]] = mapped_column(Integer) # cm
    age: Mapped[Optional[int]] = mapped_column(Integer) # Last known age
    birth_date: Mapped[Optional[datetime]] = mapped_column(DateTime)
    
    current_team_id: Mapped[Optional[str]] = mapped_column(ForeignKey("teams.id"))
    
    current_team: Mapped[Optional["Team"]] = relationship(back_populates="players")
    user_link: Mapped[Optional["UserPlayerLink"]] = relationship(back_populates="player")
    season_stats: Mapped[List["PlayerSeasonStat"]] = relationship(back_populates="player")
    match_history: Mapped[List["MatchHistory"]] = relationship(back_populates="player")
    injuries: Mapped[List["Injury"]] = relationship(back_populates="player")
    photos: Mapped[List["PlayerPhoto"]] = relationship(back_populates="player")
    designs: Mapped[List["CardDesign"]] = relationship(back_populates="player")
    
    # Agentes que representan a este jugador
    agents: Mapped[List["User"]] = relationship(
        secondary=agent_player_links, back_populates="managed_players"
    )


class UserPlayerLink(Base):
    """Conecta un usuario de tipo Player con su perfil biodemográfico."""
    __tablename__ = "user_player_links"
    
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True)
    player_id: Mapped[str] = mapped_column(ForeignKey("players.id"), primary_key=True)
    
    user: Mapped["User"] = relationship(back_populates="player_link")
    player: Mapped["Player"] = relationship(back_populates="user_link")


# ==============================================================================
# 3. RENDIMIENTO Y SALUD
# ==============================================================================

class PlayerSeasonStat(Base):
    """Almacena los datos procesados de los CSVs de la HKPL."""
    __tablename__ = "player_season_stats"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    player_id: Mapped[str] = mapped_column(ForeignKey("players.id"), nullable=False)
    season_id: Mapped[str] = mapped_column(ForeignKey("seasons.id"), nullable=False)
    
    # Core Metrics for quick querying
    matches_played: Mapped[Optional[int]] = mapped_column(Integer)
    minutes_played: Mapped[Optional[int]] = mapped_column(Integer)
    goals: Mapped[Optional[int]] = mapped_column(Integer)
    assists: Mapped[Optional[int]] = mapped_column(Integer)
    yellow_cards: Mapped[Optional[int]] = mapped_column(Integer)
    red_cards: Mapped[Optional[int]] = mapped_column(Integer)
    
    # Advanced Metrics / Remainder of CSV columns stored flexibly
    advanced_stats: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON)
    
    player: Mapped["Player"] = relationship(back_populates="season_stats")


class Fixture(Base):
    """Calendario oficial de partidos (proviene de iCal/HKFA)."""
    __tablename__ = "fixtures"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    external_id: Mapped[Optional[str]] = mapped_column(String(255)) # ID de iCal/Google
    season_id: Mapped[str] = mapped_column(ForeignKey("seasons.id"), nullable=False)
    date_utc: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    
    home_team_id: Mapped[str] = mapped_column(ForeignKey("teams.id"), nullable=False)
    away_team_id: Mapped[str] = mapped_column(ForeignKey("teams.id"), nullable=False)
    
    venue: Mapped[Optional[str]] = mapped_column(String(200)) # Estadio (Nombre)
    stadium_id: Mapped[Optional[str]] = mapped_column(String(50)) # ID de TheSportsDB
    
    competition_type: Mapped[Optional[str]] = mapped_column(String(100)) # HKPL, FA Cup
    stream_url: Mapped[Optional[str]] = mapped_column(String(255))
    
    # Caché de assets para visualización rápida
    home_team_logo: Mapped[Optional[str]] = mapped_column(String(255))
    away_team_logo: Mapped[Optional[str]] = mapped_column(String(255))
    
    # Bolsa de datos completa (Social links, fanart, etc.)
    metadata_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON)


class MatchHistory(Base):
    """Historial detallado de rendimiento individual (proviene de Transfermarkt)."""
    __tablename__ = "match_history"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    player_id: Mapped[str] = mapped_column(ForeignKey("players.id"), nullable=False)
    
    date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    competition_name: Mapped[Optional[str]] = mapped_column(String(100))
    competition_logo: Mapped[Optional[str]] = mapped_column(String(255))
    opponent: Mapped[Optional[str]] = mapped_column(String(150))
    result: Mapped[Optional[str]] = mapped_column(String(50))
    
    # Rendimiento
    minutes_played: Mapped[Optional[int]] = mapped_column(Integer, default=0)
    goals: Mapped[Optional[int]] = mapped_column(Integer, default=0)
    assists: Mapped[Optional[int]] = mapped_column(Integer, default=0)
    yellow_cards: Mapped[Optional[int]] = mapped_column(Integer, default=0)
    red_cards: Mapped[Optional[int]] = mapped_column(Integer, default=0)
    
    # Contexto del partido
    position: Mapped[Optional[str]] = mapped_column(String(50)) # Posición en el partido
    status: Mapped[str] = mapped_column(String(50), default="Jugado") # Titular, Suplente, Lesionado...
    
    # Datos crudos adicionales
    raw_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON)
    
    player: Mapped["Player"] = relationship(back_populates="match_history")


class Injury(Base):
    __tablename__ = "injuries"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    player_id: Mapped[str] = mapped_column(ForeignKey("players.id"), nullable=False)
    
    injury_type: Mapped[str] = mapped_column(String(200), nullable=False)
    body_part: Mapped[Optional[str]] = mapped_column(String(100))
    severity: Mapped[Optional[str]] = mapped_column(String(50))
    
    start_date: Mapped[Optional[datetime]] = mapped_column(DateTime)
    return_date: Mapped[Optional[datetime]] = mapped_column(DateTime)
    days_out: Mapped[Optional[int]] = mapped_column(Integer)
    status: Mapped[Optional[str]] = mapped_column(String(50)) # Active, Recovered
    
    player: Mapped["Player"] = relationship(back_populates="injuries")


# ==============================================================================
# 4. MÓDULO DE DISEÑO (CARD EDITOR)
# ==============================================================================

class CardTemplate(Base):
    """Configuración maestra de plantillas de diseño (sustituye assets/templates/*.json)."""
    __tablename__ = "card_templates"
    
    id: Mapped[str] = mapped_column(String(50), primary_key=True) # e.g. "player_card_standard"
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    config: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False) # Dimensions, colors, default elements
    
    designs: Mapped[List["CardDesign"]] = relationship(back_populates="template")


class PlayerPhoto(Base):
    """Álbum digital de fotos de jugadores con versiones con fondo eliminado."""
    __tablename__ = "player_photos"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    player_id: Mapped[str] = mapped_column(ForeignKey("players.id"), nullable=False)
    
    original_path: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    cutout_path: Mapped[Optional[str]] = mapped_column(String(255)) # Background removed version
    photo_data: Mapped[Optional[bytes]] = mapped_column(LargeBinary, nullable=True) # Binary blob, served as data URI

    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    upload_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    player: Mapped["Player"] = relationship(back_populates="photos")


class CardDesign(Base):
    """Borradores y diseños finales creados en el Editor Studio."""
    __tablename__ = "card_designs"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    player_id: Mapped[str] = mapped_column(ForeignKey("players.id"), nullable=False)
    template_id: Mapped[str] = mapped_column(ForeignKey("card_templates.id"), nullable=False)
    
    milestone_id: Mapped[Optional[str]] = mapped_column(String(100)) # Contexto ej: "goal_vs_kitchee"
    status: Mapped[str] = mapped_column(String(20), default="DRAFT") # DRAFT, FINAL
    format: Mapped[str] = mapped_column(String(20), default="1:1") # 1:1, 9:16, 16:9
    
    # Configuración completa del diseño (AI proposal + User overrides)
    config: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    template: Mapped["CardTemplate"] = relationship(back_populates="designs")
    player: Mapped["Player"] = relationship(back_populates="designs")


# ==============================================================================
# 5. SISTEMA Y METADATOS
# ==============================================================================

class AIModelRegistry(Base):
    __tablename__ = "ai_models_registry"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    model_name: Mapped[str] = mapped_column(String(150), nullable=False) # e.g. "xgboost_Goals"
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    path: Mapped[str] = mapped_column(String(255), nullable=False)
    model_type: Mapped[str] = mapped_column(String(50))
    
    metrics: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON) # RMSE, MAE, R2
    features: Mapped[Optional[List[str]]] = mapped_column(JSON) # List of feature columns
    
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class SystemSyncLog(Base):
    __tablename__ = "system_sync_logs"
    
    task_name: Mapped[str] = mapped_column(String(100), primary_key=True) # e.g. "transfermarkt_weekly", "hkpl_2024-25"
    last_run: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    status: Mapped[Optional[str]] = mapped_column(String(50)) # SUCCESS, FAILED
    details: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON)
