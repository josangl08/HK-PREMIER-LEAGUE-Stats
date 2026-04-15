# ABOUTME: Compatibility shim for competition-domain helpers moved into the data layer.
# ABOUTME: Re-exports the new registry functions while callers migrate off utils.

from data.competition_registry import (
    COMPETITION_LOGO_MAP,
    COMPETITION_MAPPING,
    get_competition_logo,
    normalize_competition,
)

__all__ = [
    "COMPETITION_LOGO_MAP",
    "COMPETITION_MAPPING",
    "get_competition_logo",
    "normalize_competition",
]
