"""
Layouts de páginas para la aplicación.
"""

from .home import layout as home_layout
from .login import create_login_layout
from .performance import create_performance_layout
from .injuries import create_injuries_layout
from .not_found import layout as not_found_layout

__all__ = [
    'home_layout',
    'create_login_layout', 
    'create_performance_layout',
    'create_injuries_layout',
    'not_found_layout'
]