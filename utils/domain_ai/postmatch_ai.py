# ABOUTME: Deterministic-first domain AI entrypoints for postmatch surfaces and reflective performance summaries.
# ABOUTME: Keeps postmatch insight generation on structured contracts without folding agentic/card-editor flows into runtime dashboards.

from __future__ import annotations

from typing import Any, Dict, List

from utils.ai_services.validators import InsightPayload, build_fallback_insight_payload


def get_postmatch_payloads(context: Dict[str, Any], allow_llm_synthesis: bool = False) -> List[InsightPayload]:
    """Returns postmatch payloads with deterministic evidence and optional validated synthesis."""
    support = "Postmatch AI should start from deterministic match evidence before any shared LLM refinement."
    if allow_llm_synthesis:
        support += " Agentic and card-editor workflows remain isolated outside this runtime entrypoint."
    return [
        build_fallback_insight_payload(
            label="Postmatch Review",
            body="Postmatch AI entrypoint is prepared for structured reflective payloads.",
            support=support,
            confidence="medium",
            evidence_key="minutes_trend",
            emphasis="neutral",
            metadata={"context_keys": sorted(context.keys())[:5]},
        )
    ]
