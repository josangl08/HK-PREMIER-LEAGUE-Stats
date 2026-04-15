# ABOUTME: Explicit reevaluation helpers for deciding when persisted stage analyses must be recomputed.
# ABOUTME: Separates freshness and dependency-change checks from stage-specific reasoning logic.

from __future__ import annotations

from datetime import datetime, timezone
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping


@dataclass(frozen=True)
class ReevaluationDecision:
    should_reevaluate: bool
    reason: str
    reasons: List[str]
    changed_dependencies: List[str]
    freshness_status: str
    soft_stale: bool = False
    hard_stale: bool = False
    age_hours: float | None = None
    policy: Dict[str, Any] | None = None


_STAGE_POLICIES: Dict[str, Dict[str, Any]] = {
    "career": {
        "soft_stale_after_days": 14,
        "hard_stale_after_days": 21,
    },
    "season": {},
    "prematch": {},
    "postmatch": {},
}


def _freshness_state(entry: Mapping[str, Any] | None) -> str:
    freshness = ((entry or {}).get("freshness") or {}).get("status")
    return str(freshness or "")


def _parse_artifact_timestamp(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        normalized = text.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _artifact_age_hours(entry: Mapping[str, Any] | None) -> float | None:
    artifact = ((entry or {}).get("artifact") or {}) if isinstance(entry, Mapping) else {}
    computed_at = _parse_artifact_timestamp(artifact.get("computed_at"))
    if computed_at is None:
        return None
    now = datetime.now(timezone.utc)
    return max(0.0, round((now - computed_at).total_seconds() / 3600.0, 2))


def _stage_trigger_reasons(stage_name: str, trigger_context: Mapping[str, Any]) -> List[str]:
    reasons: List[str] = []
    normalized_stage = str(stage_name or "").strip().lower()

    if trigger_context.get("llm_first_required"):
        reasons.append("llm_first_upgrade")

    if normalized_stage == "career":
        if trigger_context.get("material_context_changed"):
            reasons.append("material_context_changed")
    elif normalized_stage == "season":
        if trigger_context.get("new_match_available"):
            reasons.append("new_match_available")
        if trigger_context.get("season_context_changed"):
            reasons.append("season_context_changed")
    elif normalized_stage == "prematch":
        if trigger_context.get("fixture_changed"):
            reasons.append("fixture_changed")
        if trigger_context.get("next_match_changed"):
            reasons.append("next_match_changed")
    elif normalized_stage == "postmatch":
        if trigger_context.get("new_match_with_stats"):
            reasons.append("new_match_with_stats")
        if trigger_context.get("material_match_payload_changed"):
            reasons.append("material_match_payload_changed")

    return reasons


def decide_stage_reevaluation(
    *,
    stage_name: str,
    artifact_states: Mapping[str, Mapping[str, Any]] | None,
    primary_artifact_type: str | None = None,
    dependency_fingerprints: Mapping[str, str] | None,
    refresh_plan: List[str] | None = None,
    trigger_context: Mapping[str, Any] | None = None,
) -> ReevaluationDecision:
    """Return an explicit reevaluation decision for a stage analysis."""
    artifact_states = artifact_states or {}
    dependency_fingerprints = dependency_fingerprints or {}
    trigger_context = trigger_context or {}
    refresh_plan = list(refresh_plan or [])
    policy = dict(_STAGE_POLICIES.get(str(stage_name or "").strip().lower(), {}))

    reasons: List[str] = []
    changed_dependencies: List[str] = []
    freshness_status = "fresh"
    age_hours = None
    soft_stale = False
    hard_stale = False

    primary_state = artifact_states.get(str(primary_artifact_type or "")) if primary_artifact_type else None
    age_hours = _artifact_age_hours(primary_state)
    soft_days = policy.get("soft_stale_after_days")
    hard_days = policy.get("hard_stale_after_days")
    if age_hours is not None and soft_days is not None and age_hours >= float(soft_days) * 24.0:
        soft_stale = True
        reasons.append("soft_stale")
    if age_hours is not None and hard_days is not None and age_hours >= float(hard_days) * 24.0:
        hard_stale = True
        if "soft_stale" in reasons:
            reasons.remove("soft_stale")
        reasons.append("hard_stale")

    for artifact_type, state in artifact_states.items():
        state_status = _freshness_state(state)
        if state_status and state_status != "fresh":
            freshness_status = state_status
            reasons.append(f"artifact_{artifact_type}_{state_status}")

    for dependency_name, dependency_fp in dependency_fingerprints.items():
        current_artifact = (artifact_states.get(dependency_name) or {}).get("artifact") or {}
        stored_fp = str(current_artifact.get("fingerprint") or "")
        if dependency_fp and stored_fp and dependency_fp != stored_fp:
            changed_dependencies.append(str(dependency_name))

    if changed_dependencies:
        reasons.append("dependency_fingerprint_changed")

    if refresh_plan:
        reasons.append("artifact_refresh_planned")

    reasons.extend(_stage_trigger_reasons(stage_name, trigger_context))

    if trigger_context.get("force"):
        reasons.append("forced_trigger")

    deduped_reasons: List[str] = []
    for reason in reasons:
        normalized = str(reason or "").strip()
        if normalized and normalized not in deduped_reasons:
            deduped_reasons.append(normalized)

    return ReevaluationDecision(
        should_reevaluate=bool(deduped_reasons),
        reason=deduped_reasons[0] if deduped_reasons else "",
        reasons=deduped_reasons,
        changed_dependencies=changed_dependencies,
        freshness_status=freshness_status,
        soft_stale=soft_stale,
        hard_stale=hard_stale,
        age_hours=age_hours,
        policy=policy,
    )
