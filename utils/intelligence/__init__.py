# ABOUTME: Intelligence infrastructure package for artifact storage, freshness, and overlay primitives.
# ABOUTME: Keeps package-level imports light so shared stage runtime modules do not create circular imports.

"""Shared infrastructure for persisted intelligence artifacts."""

from utils.intelligence.overlay_surface import (
    PRESENTATION_CONTEXTUAL,
    PRESENTATION_CRITICAL,
    PRESENTATION_MICRO,
    PRESENTATION_PROMINENT,
    build_overlay_inbox_entry,
    choose_primary_overlay_candidate,
    normalize_overlay_candidate,
    resolve_stage_overlay_surface,
)

__all__ = [
    "PRESENTATION_CONTEXTUAL",
    "PRESENTATION_CRITICAL",
    "PRESENTATION_MICRO",
    "PRESENTATION_PROMINENT",
    "build_overlay_inbox_entry",
    "choose_primary_overlay_candidate",
    "normalize_overlay_candidate",
    "resolve_stage_overlay_surface",
]
