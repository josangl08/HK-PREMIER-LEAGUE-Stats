# ABOUTME: Singleton registry for global application instances
# ABOUTME: Prevents circular imports by providing centralized access to managers

"""
Application Context Manager - Singleton Registry Pattern

This module provides a centralized registry for global application instances
to avoid circular import issues between app.py and callback modules.

Design Pattern:
    - app.py creates instances and registers them here
    - Callback modules import from this module (not from app.py)
    - No circular dependency: app_context doesn't import from app

Usage:
    # In app.py (after creating instances):
    from utils.app_context import set_hong_kong_data_manager
    data_manager = HongKongDataManager(auto_load=False)
    set_hong_kong_data_manager(data_manager)

    # In callbacks (to access the instance):
    from utils.app_context import get_hong_kong_data_manager
    data_manager = get_hong_kong_data_manager()
"""

import logging
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    # Type hints only - no runtime import
    from data.hong_kong_data_manager import HongKongDataManager
    from data.transfermarkt_data_manager import TransfermarktDataManager

logger = logging.getLogger(__name__)

# ============================================================================
# SINGLETON REGISTRY - Global instances storage
# ============================================================================

_hong_kong_data_manager: Optional["HongKongDataManager"] = None
_transfermarkt_data_manager: Optional["TransfermarktDataManager"] = None


# ============================================================================
# HONG KONG DATA MANAGER - Getter and Setter
# ============================================================================

def set_hong_kong_data_manager(manager) -> None:  # type: ignore
    """
    Registers the HongKongDataManager instance globally.

    Should be called ONCE from app.py after creating the instance.

    Args:
        manager: HongKongDataManager instance to register (or DummyDataManager)

    Raises:
        ValueError: If manager is None or already registered

    Note:
        Type hint is relaxed to accept DummyDataManager fallback from app.py
    """
    global _hong_kong_data_manager

    if manager is None:
        raise ValueError("Cannot register None as HongKongDataManager")

    if _hong_kong_data_manager is not None:
        logger.warning(
            "HongKongDataManager already registered. "
            "Overwriting previous instance."
        )

    _hong_kong_data_manager = manager  # type: ignore
    logger.info("✓ HongKongDataManager registered in app context")


def get_hong_kong_data_manager() -> "HongKongDataManager":
    """
    Retrieves the registered HongKongDataManager instance.

    Returns:
        The registered HongKongDataManager instance

    Raises:
        RuntimeError: If no manager has been registered yet
    """
    if _hong_kong_data_manager is None:
        raise RuntimeError(
            "HongKongDataManager not initialized. "
            "Make sure app.py has called set_hong_kong_data_manager() "
            "before importing callbacks."
        )

    return _hong_kong_data_manager


# ============================================================================
# TRANSFERMARKT DATA MANAGER - Getter and Setter
# ============================================================================

def set_transfermarkt_data_manager(
    manager: "TransfermarktDataManager"
) -> None:
    """
    Registers the TransfermarktDataManager instance globally.

    Should be called from app.py or callbacks that initialize it.

    Args:
        manager: TransfermarktDataManager instance to register

    Raises:
        ValueError: If manager is None
    """
    global _transfermarkt_data_manager

    if manager is None:
        raise ValueError("Cannot register None as TransfermarktDataManager")

    if _transfermarkt_data_manager is not None:
        logger.warning(
            "TransfermarktDataManager already registered. "
            "Overwriting previous instance."
        )

    _transfermarkt_data_manager = manager
    logger.info("✓ TransfermarktDataManager registered in app context")


def get_transfermarkt_data_manager() -> "TransfermarktDataManager":
    """
    Retrieves the registered TransfermarktDataManager instance.

    Returns:
        The registered TransfermarktDataManager instance

    Raises:
        RuntimeError: If no manager has been registered yet
    """
    if _transfermarkt_data_manager is None:
        raise RuntimeError(
            "TransfermarktDataManager not initialized. "
            "Make sure it has been registered before use."
        )

    return _transfermarkt_data_manager


# ============================================================================
# UTILITY FUNCTIONS - For testing and debugging
# ============================================================================

def is_hong_kong_manager_registered() -> bool:
    """Check if HongKongDataManager is registered."""
    return _hong_kong_data_manager is not None


def is_transfermarkt_manager_registered() -> bool:
    """Check if TransfermarktDataManager is registered."""
    return _transfermarkt_data_manager is not None


def reset_all_managers() -> None:
    """
    Resets all registered managers.

    WARNING: Only use for testing purposes!
    """
    global _hong_kong_data_manager, _transfermarkt_data_manager

    _hong_kong_data_manager = None
    _transfermarkt_data_manager = None

    logger.warning("⚠️ All managers have been reset (testing mode)")
