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
        metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
        summarized.append(
            {
                "label": str(payload.get("label") or payload.get("title") or "").strip(),
                "body": str(payload.get("body") or "").strip(),
                "support": str(payload.get("support") or "").strip(),
                "confidence": str(payload.get("confidence") or "medium").strip().lower(),
                "evidence_key": normalize_evidence_key(payload.get("evidence_key") or ""),
                "emphasis": str(payload.get("emphasis") or "neutral").strip().lower(),
                "framing_hint": str(metadata.get("framing_hint") or "").strip().lower(),
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
        "The explanation must be direct and player-facing, and every driver/risk must include a concrete value or trend.\n"
        "Writing rules:\n"
        "- Do not lightly paraphrase the deterministic copy.\n"
        "- Each rewritten signal must materially differ in wording and framing from the deterministic input.\n"
        "- Make every signal feel specific to this player and this case, not reusable for many players.\n"
        "- Use the concrete career scale already present in the support text whenever possible.\n"
        "- Avoid generic phrases like 'real weight', 'competitive value', 'current trend', or 'career momentum' unless you make them specific with surrounding context.\n"
        "- Vary sentence openings and structure across signals.\n"
        "- For career value signals, anchor the wording in the actual size of the player's body of work.\n"
        "- For phase signals, explain what this phase means for this player now, not just what age band they are in.\n"
        "- For recent signals, explicitly connect the short-term change to the wider career arc.\n"
        "- Avoid report-like phrases such as 'competitive settings', 'threatens to undermine progress', or 'throughout the rest of the season'.\n"
        "- Avoid inflated phrases like 'defying the typical decline', 'significant influence on the pitch', 'plenty to offer', or 'maintain your current standing'.\n"
        "- Keep the language natural, concise, and non-technical.\n"
        "- Use simple everyday English that any player can understand quickly.\n"
        "- Prefer words like level, minutes, performance, trust, starts, rhythm, and next step over abstract career language.\n"
        "- If a sentence can be explained with level, minutes, form, or role, choose that wording.\n"
        "- Prefer short, plain words over abstract or polished analyst vocabulary.\n"
        "- Avoid sounding corporate, academic, dramatic, or overly editorial.\n"
        "- Do not use words like 'tenure', 'trajectory', 'volatility', 'substance', 'contraction', or 'campaign' unless absolutely necessary.\n"
        "- Write like a smart human explaining the situation clearly, not like a report template.\n"
        "- Do not reuse stock phrases such as 'solid foundation', 'flash in the pan', 'red flag', 'at this stage', 'built a body of work', or 'proving you belong'.\n"
        "Block-specific rules:\n"
        "- career_thesis: do not reuse the fallback body structure; explain the main career story in a fresh way that sounds personal to this player.\n"
        "- career_thesis: the explanation should connect the strongest drivers and risks into one readable thought, not just restate labels.\n"
        "- career_thesis: avoid broad prestige language and say plainly what is still strong, what is slipping, or why this phase is unusual.\n"
        "- career_thesis: when the player is older, explain the challenge in simple terms such as keeping this level, these minutes, or this rhythm going.\n"
        "- signals: each signal should feel like a specific reading of this player's situation, not a reusable dashboard label with new numbers.\n"
        "- signals: avoid starting multiple signals with 'Your...' unless it is the clearest option.\n"
        "- signals: every body must include at least one concrete anchor from this case, such as age, seasons tracked, latest season, last 5 matches, career minutes, goals, assists, or momentum.\n"
        "- signals: do not put all the specificity into the support line while leaving the body generic.\n"
        "- signals: titles should feel natural and specific, not generic category labels like 'Career Value' or 'Age and Impact' unless no better option is possible.\n"
        "- signals: use framing_hint when provided to vary the angle of the message. recognition should sound like earned credit, warning should sound like a clear concern, tension should highlight a contradiction, checkpoint should sound like a moment to pay attention, and opportunity should sound like a realistic opening.\n"
        "- signals: vary the framing between signals instead of using the same narrative pattern three times.\n"
        "- signals: if one signal already talks about the player's long history, the next positive signal should focus on the current phase or role, not repeat the same idea.\n"
        "- levers: explain what the player should focus on in simple football language, not percentile or analyst language.\n"
        "- levers: the body should explain the football action itself, while the support line should explain the evidence behind it.\n"
        "- levers: keep outcome language in the unlock metadata, not in the body or support.\n"
        "- outlook: say what the next period means for this player in plain terms, and avoid repeating the thesis wording.\n"
        "- outlook: avoid generic motivational language; be concrete about whether the player should steady their level, push on, or hold their current ground."
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
        "{\"recommended_phase\": str, \"phase_hypothesis\": str, \"phase_adjustment\": str, "
        "\"momentum_adjustment\": int, \"confidence\": str, \"context_patterns\": [str], "
        "\"supporting_factors\": [str], \"blockers\": [str], \"risk_flags\": [str], "
        "\"next_condition\": str, \"contradictions\": [str], \"insight_flags\": [str], "
        "\"rationale\": str}.\n"
        "Rules:\n"
        "- recommended_phase must be one of Ambitious|Keep Pushing|Maintain Consistency|Find Consistency.\n"
        "- phase_hypothesis must be one of development|building|peak|post-peak|unknown.\n"
        "- phase_adjustment must be one of none|lean_forward|lean_backward.\n"
        "- momentum_adjustment must be -1, 0, or 1.\n"
        "- confidence must be low|medium|high.\n"
        "- Use only factors visible in the provided feature JSON.\n"
        "- Do not invent external context, injuries, contracts, or future events.\n"
        "- Keep context_patterns, supporting_factors, blockers, risk_flags, and contradictions concise tokens, not sentences.\n"
        "- next_condition must be one short sentence about what would move the player to a stronger recommendation.\n"
        "- When late_peak_candidate is true, you may keep the player closer to peak rather than post-peak if the deterministic context still looks highly competitive.\n"
        "- Use rationale to explain whether the deterministic baseline should be kept or lightly adjusted."
    )


def build_evidence_explanation_prompt(
    *,
    player_name: str,
    evidence_key: str,
    card_context: Dict[str, Any],
    evidence_facts: Dict[str, Any],
    career_summary: Dict[str, Any],
) -> str:
    """Builds a strict JSON prompt for evidence-modal explanation tied to one evidence view."""
    card_context_json = json.dumps(card_context or {}, ensure_ascii=True)
    evidence_json = json.dumps(evidence_facts or {}, ensure_ascii=True)
    summary_json = json.dumps(career_summary or {}, ensure_ascii=True)
    return (
        "You are explaining one football evidence view for a player-facing dashboard modal.\n"
        f"Player: {player_name or 'Unknown player'}.\n"
        f"Evidence key: {normalize_evidence_key(evidence_key)}.\n"
        f"Card context JSON: {card_context_json}\n"
        f"Career summary JSON: {summary_json}\n"
        f"Evidence facts JSON: {evidence_json}\n"
        "Task:\n"
        "- Explain what this evidence view shows in simple player-friendly language.\n"
        "- Explain why it matters.\n"
        "- Explain what the player should watch next.\n"
        "- Use only the supplied context.\n"
        "- Do not invent facts, causes, injuries, contracts, or tactical explanations not visible in the data.\n"
        "- Keep every claim traceable to the supplied evidence facts.\n"
        "- Keep the wording short, plain, and non-technical.\n"
        "Return JSON only with this exact shape: "
        "{\"evidence_key\": str, \"headline\": str, \"what_this_shows\": str, "
        "\"why_it_matters\": str, \"what_to_watch\": str, \"confidence\": str}.\n"
        "Rules:\n"
        "- confidence must be low|medium|high.\n"
        "- evidence_key must stay unchanged.\n"
        "- headline must be short and direct.\n"
        "- Each field after headline must be 1 sentence maximum.\n"
        "- Avoid analyst words like trajectory, volatility, profile separation, or percentile unless absolutely necessary.\n"
        "- Do not repeat the card body word-for-word.\n"
    )
