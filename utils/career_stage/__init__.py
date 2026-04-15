# ABOUTME: Career-stage intelligence package exposing reusable artifact contracts and integration helpers.
# ABOUTME: Keeps career intelligence expansion modular so future stage orchestration can import a narrow surface.

from utils.career_stage.career_intelligence import (
    CAREER_ARTIFACT_TYPES,
    CAREER_DASHBOARD_BRIEF_ARTIFACT,
    CAREER_FRESHNESS_POLICY,
    CAREER_PHASE_CONTEXT_ARTIFACT,
    CAREER_PRIORITIES_CONTEXT_ARTIFACT,
    CAREER_SIGNALS_ARTIFACT,
    CAREER_SIGNALS_CONTEXT_ARTIFACT,
    CAREER_STAGE_ANALYSIS_ARTIFACT,
    build_career_base_artifact_payloads,
    build_career_stage_analysis_payload,
    build_career_artifact_scope,
)

__all__ = [
    "CAREER_ARTIFACT_TYPES",
    "CAREER_DASHBOARD_BRIEF_ARTIFACT",
    "CAREER_FRESHNESS_POLICY",
    "CAREER_PHASE_CONTEXT_ARTIFACT",
    "CAREER_PRIORITIES_CONTEXT_ARTIFACT",
    "CAREER_SIGNALS_ARTIFACT",
    "CAREER_SIGNALS_CONTEXT_ARTIFACT",
    "CAREER_STAGE_ANALYSIS_ARTIFACT",
    "build_career_base_artifact_payloads",
    "build_career_stage_analysis_payload",
    "build_career_artifact_scope",
]
