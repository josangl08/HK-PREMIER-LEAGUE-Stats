# ABOUTME: Builds evidence-specific explanation payloads for career evidence modals with deterministic fallback.
# ABOUTME: Keeps deeper AI interpretation tied to the selected evidence view instead of the main dashboard surface.

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, Optional

from utils.ai_services.evidence_router import normalize_evidence_key
from utils.ai_services.llm_client import (
    generate_gemini_content_with_status,
    get_dashboard_brief_model_candidates,
    gemini_is_available,
)
from utils.ai_services.orchestration import parse_structured_json
from utils.ai_services.prompt_builders import build_evidence_explanation_prompt
from utils.ai_services.validators import (
    EvidenceExplanationPayload,
    build_fallback_evidence_explanation_payload,
    coerce_evidence_explanation_payload,
    validate_evidence_explanation_payload,
)


_EVIDENCE_EXPLANATION_CACHE_VERSION = "v1"
_EVIDENCE_EXPLANATION_CACHE_TIMEOUT_SECONDS = 60 * 60 * 24 * 30


def _safe_int(value: Any) -> int:
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return 0


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _build_fallback_explanation(
    evidence_key: str,
    evidence_facts: Dict[str, Any],
    card_context: Optional[Dict[str, Any]] = None,
) -> EvidenceExplanationPayload:
    evidence_key = normalize_evidence_key(evidence_key)
    facts = evidence_facts if isinstance(evidence_facts, dict) else {}
    card_context = card_context if isinstance(card_context, dict) else {}
    card_body = str(card_context.get("body") or "").strip()

    if evidence_key == "minutes_trend":
        headline = str(facts.get("headline_fact") or "Your role needs context, not just raw minutes.")
        what_this_shows = "This chart shows how your minutes have changed across seasons."
        why_it_matters = "More minutes matter most when they turn into a role you can keep."
        what_to_watch = "Watch whether this level holds long enough to become normal."
    elif evidence_key == "recent_form":
        headline = str(facts.get("headline_fact") or "Recent form is a checkpoint, not the whole story.")
        what_this_shows = "This view compares your latest run with the stretch just before it."
        why_it_matters = "It helps show whether the short-term trend supports the bigger picture or starts to question it."
        what_to_watch = "Watch whether this trend continues beyond this short run."
    elif evidence_key == "career_trend":
        headline = str(facts.get("headline_fact") or "The bigger trend matters more than one spike.")
        what_this_shows = "This view shows whether your level is rising, flattening, or swinging across seasons."
        why_it_matters = "It helps separate a stable career pattern from a short spell."
        what_to_watch = "Watch whether the next season confirms the same direction."
    elif evidence_key == "career_phase_resolution":
        headline = str(facts.get("headline_fact") or "Your phase is about more than age on its own.")
        what_this_shows = "This view explains why your current age, momentum, and role signals point to this phase."
        why_it_matters = "It helps show whether the next step is to push, steady the level, or rebuild force."
        what_to_watch = "Watch whether momentum and role signals keep supporting this read."
    elif evidence_key == "career_value_summary":
        headline = str(facts.get("headline_fact") or "Career value comes from repeatable work over time.")
        what_this_shows = "This view sums up the size of your tracked body of work."
        why_it_matters = "It helps show whether your profile is built on one spell or on something more durable."
        what_to_watch = "Watch whether the next stretch adds more weight to the same body of work."
    elif evidence_key == "percentile_profile":
        main_limit = str(facts.get("main_limit") or "one weaker area")
        headline = "Your profile has clear strengths, but one weaker area still matters."
        what_this_shows = "This profile compares the stronger and weaker parts of your game."
        why_it_matters = f"Right now, improving {main_limit.lower()} could help more than adding small gains to the areas that are already strong."
        what_to_watch = "Watch whether the weaker area starts to move closer to the rest of your profile."
    elif evidence_key == "projection_outlook":
        headline = str(facts.get("headline_fact") or "The next step depends on what you can hold, not just on one good spell.")
        what_this_shows = "This view gives a forward-looking read of what your current signs point toward."
        why_it_matters = "It helps frame whether the next period is for building, consolidating, or pushing."
        what_to_watch = "Watch whether the next stretch strengthens the case for a more aggressive next move."
    elif evidence_key == "similarity_profiles":
        headline = str(facts.get("headline_fact") or "Similar profiles help show what kind of player you already look like.")
        what_this_shows = "This comparison shows the closest profiles to your current style."
        why_it_matters = "It helps explain where you already fit and what still needs more weight."
        what_to_watch = "Watch whether your profile starts to look closer to stronger or more complete versions of this role."
    elif evidence_key == "tactical_dna":
        headline = str(facts.get("headline_fact") or "Your profile identity comes from the strongest parts of your game.")
        what_this_shows = "This view highlights the traits that most shape your profile."
        why_it_matters = "A clearer identity makes it easier for your role and value to grow."
        what_to_watch = "Watch whether the same strong traits keep showing up over time."
    else:
        headline = "This evidence gives more context to the card."
        what_this_shows = "This view shows the supporting proof behind the dashboard insight."
        why_it_matters = card_body or "It helps explain why the main reading was shown."
        what_to_watch = "Watch whether the same pattern keeps showing up over time."

    return build_fallback_evidence_explanation_payload(
        evidence_key=evidence_key,
        headline=headline,
        what_this_shows=what_this_shows,
        why_it_matters=why_it_matters,
        what_to_watch=what_to_watch,
        confidence="medium",
    )


def _build_cache_key(player_id: str, evidence_key: str, evidence_facts: Dict[str, Any], card_context: Optional[Dict[str, Any]]) -> str:
    payload = {
        "version": _EVIDENCE_EXPLANATION_CACHE_VERSION,
        "player_id": player_id,
        "evidence_key": normalize_evidence_key(evidence_key),
        "evidence_facts": evidence_facts or {},
        "card_context": card_context or {},
    }
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, default=str, ensure_ascii=True).encode("utf-8")).hexdigest()
    return f"career-evidence-explanation:{player_id or 'unknown'}:{digest}"


def _get_cached_payload(cache_key: str) -> Optional[EvidenceExplanationPayload]:
    try:
        from utils.cache import cache

        cached_payload = cache.get(cache_key)
        payload = coerce_evidence_explanation_payload(cached_payload)
        return payload if payload and validate_evidence_explanation_payload(payload) else None
    except Exception:
        return None


def _set_cached_payload(cache_key: str, payload: EvidenceExplanationPayload) -> None:
    try:
        from utils.cache import cache

        cache.set(cache_key, payload.__dict__, timeout=_EVIDENCE_EXPLANATION_CACHE_TIMEOUT_SECONDS)
    except Exception:
        return


def build_evidence_explanation(
    *,
    player_id: str,
    player_name: str,
    evidence_key: str,
    career_facts: Dict[str, Any],
    card_context: Optional[Dict[str, Any]] = None,
) -> Optional[EvidenceExplanationPayload]:
    """Returns a validated evidence explanation payload with deterministic fallback."""
    normalized_key = normalize_evidence_key(evidence_key)
    evidence_facts = ((career_facts or {}).get("evidence_facts") or {}).get(normalized_key) or {}
    cache_key = _build_cache_key(player_id, normalized_key, evidence_facts, card_context)
    cached_payload = _get_cached_payload(cache_key)
    if cached_payload is not None:
        return cached_payload

    fallback = _build_fallback_explanation(normalized_key, evidence_facts, card_context=card_context)
    if not gemini_is_available():
        _set_cached_payload(cache_key, fallback)
        return fallback

    prompt = build_evidence_explanation_prompt(
        player_name=player_name,
        evidence_key=normalized_key,
        card_context=card_context or {},
        evidence_facts=evidence_facts,
        career_summary=(career_facts or {}).get("career_summary") or {},
    )
    for model_name in get_dashboard_brief_model_candidates():
        result = generate_gemini_content_with_status(
            prompt,
            model_name=model_name,
            temperature=0.3,
            max_output_tokens=500,
            response_mime_type="application/json",
        )
        parsed = parse_structured_json(result.text) if result.ok else None
        payload = coerce_evidence_explanation_payload(parsed)
        if payload is None or not validate_evidence_explanation_payload(payload):
            continue
        resolved_payload = EvidenceExplanationPayload(
            evidence_key=payload.evidence_key,
            headline=payload.headline,
            what_this_shows=payload.what_this_shows,
            why_it_matters=payload.why_it_matters,
            what_to_watch=payload.what_to_watch,
            confidence=payload.confidence,
            llm_generated=True,
            source_model=result.model,
        )
        _set_cached_payload(cache_key, resolved_payload)
        return resolved_payload

    _set_cached_payload(cache_key, fallback)
    return fallback
