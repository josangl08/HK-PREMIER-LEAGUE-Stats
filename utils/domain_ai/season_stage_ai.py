# ABOUTME: Deterministic-first domain AI entrypoints for season-stage surfaces that may later opt into shared synthesis.
# ABOUTME: Documents the surface contract so stage renderers can depend on structured payloads instead of inline AI logic.

from __future__ import annotations

from typing import Any, Dict, List

from utils.ai_services.validators import InsightPayload, build_fallback_insight_payload


def get_season_stage_payloads(context: Dict[str, Any], allow_llm_synthesis: bool = False) -> List[InsightPayload]:
    """Returns season-stage payloads; deterministic-first and LLM enhancement remains optional."""
    support = (
        "Season-stage services should prepare structured evidence deterministically before any optional synthesis."
    )
    if allow_llm_synthesis:
        support += " Shared LLM synthesis may refine wording only after validation."
    return [
        build_fallback_insight_payload(
            label="Season Intelligence",
            body="Season-stage AI entrypoint is ready for structured deterministic payloads.",
            support=support,
            confidence="medium",
            evidence_key="career_arc",
            emphasis="neutral",
            metadata={"context_keys": sorted(context.keys())[:5]},
        )
    ]
