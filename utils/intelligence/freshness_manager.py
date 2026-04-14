# ABOUTME: Freshness evaluation helpers for intelligence artifacts using fingerprints, expirations, and dependency metadata.
# ABOUTME: Provides deterministic policy checks so orchestration can decide when cached analysis is safe to reuse.

from __future__ import annotations

import json
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Dict, Iterable, Mapping


FRESHNESS_FRESH = "fresh"
FRESHNESS_STALE = "stale"
FRESHNESS_EXPIRED = "expired"

FRESHNESS_HOT = "hot"
FRESHNESS_WARM = "warm"
FRESHNESS_COLD = "cold"


def utc_now() -> datetime:
    """Return the current UTC timestamp."""
    return datetime.now(timezone.utc)


def serialize_timestamp(value: datetime | None) -> str | None:
    """Serialize a datetime to ISO-8601 with timezone information."""
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def parse_timestamp(value: str | None) -> datetime | None:
    """Parse an ISO-8601 timestamp if present."""
    if not value:
        return None
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def build_artifact_fingerprint(parts: Mapping[str, Any]) -> str:
    """Hash fingerprint inputs into a deterministic artifact fingerprint."""
    payload = json.dumps(parts, sort_keys=True, default=str, separators=(",", ":"))
    return sha256(payload.encode("utf-8")).hexdigest()


def build_dependency_fingerprint_map(
    dependency_artifacts: Mapping[str, Mapping[str, Any] | None],
) -> Dict[str, str]:
    """Collect dependency fingerprints keyed by artifact type."""
    return {
        artifact_type: str((artifact or {}).get("fingerprint") or "")
        for artifact_type, artifact in dependency_artifacts.items()
        if artifact is not None and (artifact or {}).get("fingerprint")
    }


def apply_evaluated_freshness(
    artifact: Mapping[str, Any] | None,
    freshness_status: str,
) -> Dict[str, Any] | None:
    """Return a copy of an artifact payload with evaluated freshness injected."""
    if artifact is None:
        return None
    normalized = dict(artifact)
    normalized["freshness_status"] = freshness_status
    return normalized


def resolve_freshness_policy(
    artifact_type: str,
    policy_by_artifact: Mapping[str, Mapping[str, Any]],
    *,
    default_regime: str = FRESHNESS_WARM,
    default_ttl_hours: int = 24,
) -> Dict[str, Any]:
    """Resolve a freshness policy for an artifact with sensible defaults."""
    policy = dict(policy_by_artifact.get(artifact_type) or {})
    return {
        "regime": str(policy.get("regime") or default_regime),
        "ttl_hours": int(policy.get("ttl_hours") or default_ttl_hours),
    }


def collect_dependency_statuses(
    dependency_artifacts: Iterable[Mapping[str, Any] | None],
) -> list[str]:
    """Collect dependency freshness statuses from a set of artifact payloads."""
    statuses = []
    for artifact in dependency_artifacts:
        if artifact is None:
            statuses.append(FRESHNESS_STALE)
            continue
        statuses.append(str(artifact.get("freshness_status") or FRESHNESS_STALE))
    return statuses


def evaluate_artifact_freshness(
    artifact: Mapping[str, Any] | None,
    *,
    expected_fingerprint: str | None = None,
    dependency_artifacts: Iterable[Mapping[str, Any] | None] | None = None,
    dependency_fingerprint_map: Mapping[str, str] | None = None,
    now: datetime | None = None,
) -> Dict[str, Any]:
    """Evaluate whether an artifact is fresh, stale, or expired."""
    current_time = now or utc_now()
    if artifact is None:
        return {
            "status": FRESHNESS_STALE,
            "is_usable": False,
            "reasons": ["artifact_missing"],
        }

    reasons = []
    expires_at = parse_timestamp(str(artifact.get("expires_at") or "")) if artifact.get("expires_at") else None
    if expires_at is not None and current_time >= expires_at:
        reasons.append("artifact_expired")

    artifact_fingerprint = artifact.get("fingerprint")
    if expected_fingerprint and artifact_fingerprint != expected_fingerprint:
        reasons.append("fingerprint_mismatch")

    for dependency_status in collect_dependency_statuses(dependency_artifacts or []):
        if dependency_status == FRESHNESS_EXPIRED:
            reasons.append("dependency_expired")
        elif dependency_status != FRESHNESS_FRESH:
            reasons.append("dependency_stale")

    declared_dependency_fingerprints = artifact.get("dependency_fingerprints") or {}
    if dependency_fingerprint_map:
        for dependency_key, dependency_fingerprint in dependency_fingerprint_map.items():
            if declared_dependency_fingerprints.get(dependency_key) != dependency_fingerprint:
                reasons.append(f"dependency_fingerprint_mismatch:{dependency_key}")

    if "artifact_expired" in reasons:
        status = FRESHNESS_EXPIRED
    elif reasons:
        status = FRESHNESS_STALE
    else:
        status = FRESHNESS_FRESH

    return {
        "status": status,
        "is_usable": status == FRESHNESS_FRESH,
        "reasons": reasons,
    }
