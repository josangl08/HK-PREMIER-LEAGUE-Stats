# ABOUTME: Processor for enriching player-match records with absence_reason classification.
# ABOUTME: Classifies absence as not_summoned, injured, suspended, or unknown using match report data.

from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

# Keys expected in a match_report entry
_INJURY_MARKERS = {"injury", "injured", "verletzt", "lesion", "lesión", "blessé"}
_SUSPENSION_MARKERS = {"suspension", "suspended", "gesperrt", "sperre", "suspendido", "sanction", "sancionado", "sanción"}


def enrich_absence_reason(
    player_match_record: Dict[str, Any],
    match_report: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Enriches a player-match record with an absence_reason field.

    Rules:
    - If minutes_played > 0: absence_reason is None (player appeared).
    - If minutes_played == 0 and the team played the match, classify the reason
      using match_report data: not_summoned, injured, suspended, or unknown.

    Args:
        player_match_record: Dict with at least 'minutes_played'. Modified in-place
            and also returned.
        match_report: Optional dict with absence classification hints. Expected keys:
            - 'in_squad' (bool): whether player was listed in match squad.
            - 'absence_marker' (str): raw text marker (e.g. "injury", "suspension").
            - 'reason' (str): pre-classified reason string (checked first).
            If None or empty, absence_reason defaults to 'unknown'.

    Returns:
        The enriched player_match_record dict with 'absence_reason' set.
    """
    minutes = int(player_match_record.get("minutes_played", 0) or 0)

    if minutes > 0:
        player_match_record["absence_reason"] = None
        return player_match_record

    # Player had 0 minutes — classify absence
    reason = _classify_absence(match_report)
    player_match_record["absence_reason"] = reason
    logger.debug(
        "Enriched absence_reason=%s for record date=%s",
        reason,
        player_match_record.get("date", "unknown"),
    )
    return player_match_record


def _classify_absence(match_report: Optional[Dict[str, Any]]) -> str:
    """
    Returns one of 'not_summoned', 'injured', 'suspended', or 'unknown'
    based on match_report data.
    """
    if not match_report:
        return "unknown"

    # 1. Pre-classified reason field takes priority
    pre_classified = str(match_report.get("reason", "")).lower().strip()
    if pre_classified in {"not_summoned", "injured", "suspended"}:
        return pre_classified

    # 2. in_squad = False → not summoned
    in_squad = match_report.get("in_squad")
    if in_squad is False:
        return "not_summoned"

    # 3. absence_marker text — check against known injury/suspension keywords
    marker = str(match_report.get("absence_marker", "")).lower().strip()
    if any(kw in marker for kw in _INJURY_MARKERS):
        return "injured"
    if any(kw in marker for kw in _SUSPENSION_MARKERS):
        return "suspended"

    return "unknown"
