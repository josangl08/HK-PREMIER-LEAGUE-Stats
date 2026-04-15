# ABOUTME: Base interfaces for shared stage-intelligence agents that emit persisted discoveries.
# ABOUTME: Keeps stage-specific reasoning behind one contract for orchestration, overlays, and persistence.

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Mapping

from utils.intelligence.discovery_contracts import StageAnalysis


class StageAgent(ABC):
    stage_name: str = "unknown"

    @abstractmethod
    def analyze(
        self,
        *,
        scope: Dict[str, str],
        artifacts: Mapping[str, Mapping[str, Any]],
        session_memory: Mapping[str, Any] | None = None,
    ) -> StageAnalysis:
        """Return a shared stage-analysis payload for the given stage scope."""
        raise NotImplementedError
