# ABOUTME: Performance dashboard callbacks orchestrator
# ABOUTME: Imports and registers all callback modules

"""
Orchestrator for performance dashboard callbacks.

This module imports all callback modules, which auto-register
their callbacks via @callback decorators.

Structure:
- shared_callbacks: Data loading, filter updates
- league_callbacks: League-level visualizations
- team_callbacks: Team-level visualizations
- player_callbacks: Player-level visualizations
- export_callbacks: PDF/data export

All modules are auto-registered on import.
"""

import logging

logger = logging.getLogger(__name__)

# Import callback modules (auto-registers all @callback decorators)
try:
    from .performance_callbacks_helpers import (
        shared_callbacks,
        league_callbacks,
        team_callbacks,
        player_callbacks,
        export_callbacks
    )
    logger.info("✓ All performance callback modules loaded successfully")

except ImportError as e:
    logger.error(f"❌ Error loading callback modules: {e}")
    raise

__all__ = [
    "shared_callbacks",
    "league_callbacks",
    "team_callbacks",
    "player_callbacks",
    "export_callbacks"
]
