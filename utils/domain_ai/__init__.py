# ABOUTME: Domain AI entrypoints for product surfaces such as career dashboard, season stage, pregame, and postmatch.
# ABOUTME: Keeps surface-specific insight assembly separate from shared AI infrastructure and Dash callback layers.

"""Domain AI services."""

from utils.domain_ai.career_dashboard_ai import build_career_dashboard_brief
from utils.domain_ai.career_progression_assessor_ai import resolve_career_progression

__all__ = ["build_career_dashboard_brief", "resolve_career_progression"]
