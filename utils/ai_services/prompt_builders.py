# ABOUTME: Prompt builders for shared AI synthesis paths that start from structured domain payloads.
# ABOUTME: Preserves evidence handles and field constraints so LLM output can be validated before UI rendering.

from __future__ import annotations

import json
from typing import Any, Dict, Iterable, List

from utils.ai_services.evidence_router import normalize_evidence_key


def _summarize_payloads(payloads: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    summarized: List[Dict[str, Any]] = []
    for payload in payloads:
        if not isinstance(payload, dict):
            continue
        summarized.append(
            {
                "label": str(payload.get("label") or payload.get("title") or "").strip(),
                "body": str(payload.get("body") or "").strip(),
                "support": str(payload.get("support") or "").strip(),
                "confidence": str(payload.get("confidence") or "medium").strip().lower(),
                "evidence_key": normalize_evidence_key(payload.get("evidence_key") or ""),
                "emphasis": str(payload.get("emphasis") or "neutral").strip().lower(),
            }
        )
    return summarized


def build_insight_synthesis_prompt(
    *,
    domain_name: str,
    player_name: str,
    deterministic_payloads: Iterable[Dict[str, Any]],
    extra_context: Dict[str, Any] | None = None,
    instruction: str = "",
) -> str:
    """Builds a strict JSON-first prompt for insight synthesis from structured payloads."""
    payload_summary = _summarize_payloads(deterministic_payloads)
    context_json = json.dumps(extra_context or {}, ensure_ascii=True)
    payload_json = json.dumps(payload_summary, ensure_ascii=True)
    instruction_text = instruction.strip() or (
        "Refine the deterministic payloads without inventing evidence, preserving the same evidence_key values."
    )

    return (
        f"You are synthesizing football insight payloads for the {domain_name} surface.\n"
        f"Player: {player_name or 'Unknown player'}.\n"
        f"Instructions: {instruction_text}\n"
        f"Context JSON: {context_json}\n"
        f"Deterministic payloads JSON: {payload_json}\n"
        "Return JSON only as a list of objects with fields "
        "`label`, `body`, `support`, `confidence`, `evidence_key`, and `emphasis`.\n"
        "Do not invent new evidence keys. Keep confidence within low|medium|high."
    )


def build_career_narrative_prompt(
    *,
    player_name: str,
    position_group: str,
    primary_metric: str,
    brief_stats: str,
    form_trend: Dict[str, Any] | None = None,
    transferability: Dict[str, Any] | None = None,
) -> str:
    """Builds the lightweight career narrative prompt used outside the dashboard card contract."""
    trend = form_trend or {}
    transfer = transferability or {}
    metric_label = primary_metric.split(",")[0].strip()
    return (
        "Football scout context.\n"
        f"Player: {player_name} ({position_group or 'Unknown role'}).\n"
        f"Last 5-match form trend: {trend.get('trend', 'stable')} (slope {trend.get('slope', 0.0):+.3f}).\n"
        f"Transferability score: {round(float(transfer.get('score', 0) or 0) * 100)}% ({transfer.get('label', '')}).\n"
        f"Recent {metric_label} history: {brief_stats}.\n"
        "Return a JSON object only with fields "
        "`title`, `body`, `tier`, `cta_label`, and `urgency`.\n"
        "The `body` must be exactly 2 sentences for a professional scout, focused on development trajectory and transfer potential."
    )


def build_career_dashboard_synthesis_prompt(
    *,
    player_name: str,
    career_thesis: Dict[str, Any],
    signals: Iterable[Dict[str, Any]],
    levers: Iterable[Dict[str, Any]],
    outlook: Dict[str, Any],
    context: Dict[str, Any] | None = None,
) -> str:
    """Builds a strict JSON prompt for structured career-dashboard synthesis."""
    thesis_json = json.dumps(career_thesis or {}, ensure_ascii=True)
    signals_json = json.dumps(_summarize_payloads(signals), ensure_ascii=True)
    levers_json = json.dumps(_summarize_payloads(levers), ensure_ascii=True)
    outlook_json = json.dumps(outlook or {}, ensure_ascii=True)
    context_json = json.dumps(context or {}, ensure_ascii=True)

    return (
        "You are refining a football career dashboard for player-facing UI.\n"
        f"Player: {player_name or 'Unknown player'}.\n"
        f"Context JSON: {context_json}\n"
        f"Career thesis JSON: {thesis_json}\n"
        f"Signals JSON: {signals_json}\n"
        f"Levers JSON: {levers_json}\n"
        f"Outlook JSON: {outlook_json}\n"
        "Return JSON only with this exact top-level shape: "
        "{\"career_thesis\": {\"label\": str, \"body\": str, \"support\": str, \"explanation\": str, "
        "\"drivers\": [{\"label\": str, \"value\": str, \"tone\": str, \"evidence_key\": str}], "
        "\"risks\": [{\"label\": str, \"value\": str, \"tone\": str, \"evidence_key\": str}]}, "
        "\"signals\": ["
        "{\"label\": str, \"body\": str, \"support\": str, \"confidence\": str, \"evidence_key\": str, \"emphasis\": str}"
        "], "
        "\"levers\": ["
        "{\"label\": str, \"body\": str, \"support\": str, \"confidence\": str, \"evidence_key\": str, \"emphasis\": str}"
        "], "
        "\"outlook\": {\"label\": str, \"body\": str, \"support\": str, \"evidence_key\": str}}.\n"
        "Preserve the existing evidence_key values and keep the same number and order of signals and levers.\n"
        "Do not invent metrics or factual claims beyond the provided support text.\n"
        "Keep confidence within low|medium|high and emphasis within neutral|positive|warning.\n"
        "The explanation must be direct and player-facing, and every driver/risk must include a concrete value or trend."
    )


def build_career_progression_assessment_prompt(
    *,
    player_name: str,
    features: Dict[str, Any],
) -> str:
    """Builds a strict JSON prompt for guarded career progression assessment."""
    features_json = json.dumps(features or {}, ensure_ascii=True)
    return (
        "You are evaluating football career progression from a closed deterministic feature set.\n"
        f"Player: {player_name or 'Unknown player'}.\n"
        f"Features JSON: {features_json}\n"
        "Return JSON only with this exact shape: "
        "{\"phase_hypothesis\": str, \"phase_adjustment\": str, \"momentum_adjustment\": int, "
        "\"confidence\": str, \"supporting_factors\": [str], \"contradictions\": [str], "
        "\"insight_flags\": [str], \"rationale\": str}.\n"
        "Rules:\n"
        "- phase_hypothesis must be one of development|building|peak|post-peak|unknown.\n"
        "- phase_adjustment must be one of none|lean_forward|lean_backward.\n"
        "- momentum_adjustment must be -1, 0, or 1.\n"
        "- confidence must be low|medium|high.\n"
        "- Use only factors visible in the provided feature JSON.\n"
        "- Do not invent external context, injuries, contracts, or future events.\n"
        "- Keep supporting_factors and contradictions concise tokens, not sentences.\n"
        "- When late_peak_candidate is true, you may keep the player closer to peak rather than post-peak if the deterministic context still looks highly competitive.\n"
        "- Use rationale to explain whether the deterministic baseline should be kept or lightly adjusted."
    )
