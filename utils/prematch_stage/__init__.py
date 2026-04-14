# ABOUTME: Prematch-stage intelligence package exposing reusable artifact contracts and deterministic integration helpers.
# ABOUTME: Keeps prematch expansion modular so shared orchestration can adopt hot prematch artifacts without stage-specific forks.

from utils.prematch_stage.prematch_intelligence import (
    PREMATCH_ARTIFACT_TYPES,
    PREMATCH_FIXTURE_CONTEXT_ARTIFACT,
    PREMATCH_FRESHNESS_POLICY,
    PREMATCH_GAME_PLAN_CONTEXT_ARTIFACT,
    PREMATCH_HEAD_TO_HEAD_CONTEXT_ARTIFACT,
    PREMATCH_RECENT_FORM_CONTEXT_ARTIFACT,
    build_prematch_artifact_payloads,
    build_prematch_artifact_scope,
)

__all__ = [
    "PREMATCH_ARTIFACT_TYPES",
    "PREMATCH_FIXTURE_CONTEXT_ARTIFACT",
    "PREMATCH_FRESHNESS_POLICY",
    "PREMATCH_GAME_PLAN_CONTEXT_ARTIFACT",
    "PREMATCH_HEAD_TO_HEAD_CONTEXT_ARTIFACT",
    "PREMATCH_RECENT_FORM_CONTEXT_ARTIFACT",
    "build_prematch_artifact_payloads",
    "build_prematch_artifact_scope",
]
