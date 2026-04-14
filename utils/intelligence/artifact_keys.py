# ABOUTME: Deterministic builders for stage-intelligence artifact keys across player, season, and stage scopes.
# ABOUTME: Normalizes scope metadata into stable cache and registry keys for persisted analytical artifacts.

from __future__ import annotations

from typing import Any, Dict


def _normalize_scope_value(value: Any) -> str:
    """Normalize scope values into stable, URL-safe key fragments."""
    text = str(value if value is not None else "unknown").strip().lower()
    normalized = []
    for char in text:
        if char.isalnum():
            normalized.append(char)
        elif char in {"-", "_"}:
            normalized.append(char)
        else:
            normalized.append("-")
    collapsed = "".join(normalized)
    while "--" in collapsed:
        collapsed = collapsed.replace("--", "-")
    return collapsed.strip("-") or "unknown"


def normalize_scope(scope: Dict[str, Any]) -> Dict[str, str]:
    """Return a normalized scope dictionary with deterministic ordering support."""
    return {
        str(key).strip().lower(): _normalize_scope_value(value)
        for key, value in sorted(scope.items())
    }


def build_artifact_key(artifact_type: str, scope: Dict[str, Any]) -> str:
    """Build a deterministic artifact key from type plus normalized scope."""
    normalized_scope = normalize_scope(scope)
    scope_fragment = ":".join(
        f"{scope_key}={scope_value}"
        for scope_key, scope_value in normalized_scope.items()
    )
    return f"{_normalize_scope_value(artifact_type)}:{scope_fragment}"


def build_stage_artifact_scope(
    player_id: Any,
    stage: str,
    season: Any | None = None,
    **extra_scope: Any,
) -> Dict[str, Any]:
    """Build the canonical scope payload for a stage artifact."""
    scope: Dict[str, Any] = {
        "player_id": player_id,
        "stage": stage,
    }
    if season is not None:
        scope["season"] = season
    scope.update(extra_scope)
    return scope


def build_stage_artifact_key(
    artifact_type: str,
    player_id: Any,
    stage: str,
    season: Any | None = None,
    **extra_scope: Any,
) -> str:
    """Build a deterministic key for any stage-scoped artifact."""
    return build_artifact_key(
        artifact_type,
        build_stage_artifact_scope(
            player_id=player_id,
            stage=stage,
            season=season,
            **extra_scope,
        ),
    )


def build_season_artifact_key(
    artifact_type: str,
    player_id: Any,
    season: Any,
    **extra_scope: Any,
) -> str:
    """Build a deterministic key for season-stage artifacts."""
    return build_stage_artifact_key(
        artifact_type=artifact_type,
        player_id=player_id,
        stage="season",
        season=season,
        **extra_scope,
    )

