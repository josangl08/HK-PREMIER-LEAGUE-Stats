# ABOUTME: Postmatch-stage intelligence package exposing reusable artifact contracts and deterministic integration helpers.
# ABOUTME: Keeps postmatch expansion modular so shared orchestration can consume recent-match artifacts without renderer-specific forks.

from utils.postmatch_stage.postmatch_intelligence import (
    POSTMATCH_ARTIFACT_TYPES,
    POSTMATCH_FRESHNESS_POLICY,
    POSTMATCH_MATCH_CONTEXT_ARTIFACT,
    POSTMATCH_OVERLAY_CANDIDATES_ARTIFACT,
    POSTMATCH_PERFORMANCE_CONTEXT_ARTIFACT,
    POSTMATCH_REFLECTION_PAYLOADS_ARTIFACT,
    build_postmatch_artifact_payloads,
    build_postmatch_artifact_scope,
)

__all__ = [
    "POSTMATCH_ARTIFACT_TYPES",
    "POSTMATCH_FRESHNESS_POLICY",
    "POSTMATCH_MATCH_CONTEXT_ARTIFACT",
    "POSTMATCH_OVERLAY_CANDIDATES_ARTIFACT",
    "POSTMATCH_PERFORMANCE_CONTEXT_ARTIFACT",
    "POSTMATCH_REFLECTION_PAYLOADS_ARTIFACT",
    "build_postmatch_artifact_payloads",
    "build_postmatch_artifact_scope",
]
