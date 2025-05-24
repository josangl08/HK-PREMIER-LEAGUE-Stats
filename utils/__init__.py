"""
Utilidades y funciones auxiliares para la aplicación.
"""

# Funciones principales de autenticación
from .auth import User, validate_credentials, load_user

# Funciones comunes
from .common import (
    format_season_short, 
    format_datetime, 
    validate_data, 
    handle_empty_data,
    create_error_message
)

# Cache
from .cache import init_cache

# PDF Generator
from .pdf_generator import SportsPDFGenerator

__all__ = [
    # Auth
    'User', 'validate_credentials', 'load_user',
    
    # Common utilities
    'format_season_short', 'format_datetime', 'validate_data', 
    'handle_empty_data', 'create_error_message',
    
    # Cache
    'init_cache',
    
    # PDF
    'SportsPDFGenerator'
]