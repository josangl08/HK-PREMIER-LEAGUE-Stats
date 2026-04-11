# ABOUTME: Central evidence routing registry for AI insight payloads and career dashboard evidence destinations.
# ABOUTME: Normalizes evidence keys so player-facing surfaces share one routing contract across AI domains.

from __future__ import annotations

from typing import Dict


EVIDENCE_DESTINATIONS: Dict[str, Dict[str, str]] = {
    "career_arc": {"title": "Career Arc", "group": "trajectory"},
    "career_trend": {"title": "Career Trend", "group": "trajectory"},
    "career_phase_resolution": {"title": "Career Phase", "group": "trajectory"},
    "career_value_summary": {"title": "Career Value", "group": "trajectory"},
    "minutes_trend": {"title": "Minutes Trend", "group": "trajectory"},
    "recent_form": {"title": "Recent Form", "group": "trajectory"},
    "percentile_profile": {"title": "Percentile Profile", "group": "profile"},
    "similarity_profiles": {"title": "Similarity Profiles", "group": "comparison"},
    "projection_outlook": {"title": "Season Projection", "group": "projection"},
    "tactical_dna": {"title": "Tactical DNA", "group": "identity"},
}

_DEFAULT_EVIDENCE_KEY = "career_arc"


def normalize_evidence_key(evidence_key: str) -> str:
    """Returns a known evidence key or the default dashboard destination."""
    key = str(evidence_key or "").strip().lower()
    return key if key in EVIDENCE_DESTINATIONS else _DEFAULT_EVIDENCE_KEY


def resolve_career_surface_evidence_key(evidence_key: str, *, label: str = "") -> str:
    """Migrates legacy career_arc links for known career surfaces without breaking old payloads."""
    normalized = normalize_evidence_key(evidence_key)
    normalized_label = str(label or "").strip().lower()
    if normalized == "career_arc" and normalized_label in {"reposition", "build", "consolidate"}:
        return "career_phase_resolution"
    return normalized


def get_evidence_destination_meta(evidence_key: str) -> Dict[str, str]:
    """Returns a normalized evidence payload for UI routing."""
    key = normalize_evidence_key(evidence_key)
    return {"key": key, **EVIDENCE_DESTINATIONS[key]}
