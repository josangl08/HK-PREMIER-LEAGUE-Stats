# ABOUTME: Shared stage-agent package for season, career, prematch, and postmatch persisted discovery runtimes.
# ABOUTME: Keeps package exports lazy so specialist agents can depend on each other without import-order cycles.

from utils.agents.stage_agents.base import StageAgent

__all__ = ["StageAgent", "SeasonStageAgent", "CareerStageAgent", "PrematchStageAgent", "PostmatchStageAgent"]


def __getattr__(name: str):
    if name == "SeasonStageAgent":
        from utils.agents.stage_agents.season_agent import SeasonStageAgent

        return SeasonStageAgent
    if name == "CareerStageAgent":
        from utils.agents.stage_agents.career_agent import CareerStageAgent

        return CareerStageAgent
    if name == "PrematchStageAgent":
        from utils.agents.stage_agents.prematch_agent import PrematchStageAgent

        return PrematchStageAgent
    if name == "PostmatchStageAgent":
        from utils.agents.stage_agents.postmatch_agent import PostmatchStageAgent

        return PostmatchStageAgent
    raise AttributeError(name)
