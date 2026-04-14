# ABOUTME: Central version constants for stage-intelligence taxonomy, signals, prompts, and analysis logic.
# ABOUTME: Keeps artifact fingerprints stable and explicit when domain logic changes over time.

from __future__ import annotations

from typing import Dict


ROLE_TAXONOMY_VERSION = "1.0"
SIGNAL_RULES_VERSION = "1.0"
PROMPT_TEMPLATE_VERSION = "1.0"
STAGE_ANALYSIS_LOGIC_VERSION = "1.0"
ARTIFACT_SCHEMA_VERSION = "1.0"


def get_intelligence_version_bundle() -> Dict[str, str]:
    """Return the current version bundle used for artifact fingerprints."""
    return {
        "artifact_schema": ARTIFACT_SCHEMA_VERSION,
        "role_taxonomy": ROLE_TAXONOMY_VERSION,
        "signal_rules": SIGNAL_RULES_VERSION,
        "prompt_template": PROMPT_TEMPLATE_VERSION,
        "stage_analysis_logic": STAGE_ANALYSIS_LOGIC_VERSION,
    }

