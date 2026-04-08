# ABOUTME: Deterministic-first domain AI entrypoints for pregame surfaces and tactical preparation summaries.
# ABOUTME: Shared LLM synthesis is optional and must sit behind validated structured payloads instead of direct UI calls.

from __future__ import annotations

from typing import Any, Dict, List

from utils.ai_services.validators import InsightPayload, build_fallback_insight_payload


def get_pregame_payloads(context: Dict[str, Any], allow_llm_synthesis: bool = False) -> List[InsightPayload]:
    """Returns pregame payloads using deterministic evidence as the source of truth."""
    support = "Pregame AI should stay deterministic-first so match previews remain fast and auditable."
    if allow_llm_synthesis:
        support += " Optional shared synthesis may polish wording but must preserve evidence keys."
    return [
        build_fallback_insight_payload(
            label="Pregame Brief",
            body="Pregame AI entrypoint is prepared for structured tactical payloads.",
            support=support,
            confidence="medium",
            evidence_key="projection_outlook",
            emphasis="neutral",
            metadata={"context_keys": sorted(context.keys())[:5]},
        )
    ]
