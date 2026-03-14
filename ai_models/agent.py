# ABOUTME: Agentic AI orchestrator (LangGraph & Gemini Flash) for Feature G.
# ABOUTME: Provides create_agent() and run_agent() for content and scouting flows.

"""
Agentic AI module for the HK Premier League Stats Platform.
Implements LangGraph StateGraph agents backed by Gemini Flash.
Two flows: 'content' (post-match content automation) and 'scouting' (player search).
"""

# Standard Library
import logging
import os
from typing import Any, Dict

logger = logging.getLogger(__name__)

# Module-level cached compiled graphs (lazy-initialized)
_compiled_flows: Dict[str, Any] = {}


def create_agent(flow: str = "scouting") -> Any:
    """
    Creates and returns a compiled LangGraph agent for the specified flow.

    Agents are cached at module level — compilation only happens once per flow.

    Args:
        flow: One of 'content' or 'scouting'.

    Returns:
        A compiled LangGraph StateGraph (CompiledGraph).

    Raises:
        EnvironmentError: If GOOGLE_API_KEY is not set.
        ValueError: If flow name is not recognised.
    """
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "GOOGLE_API_KEY environment variable is not set. "
            "Set it before using the agentic AI features."
        )

    if flow not in ("content", "scouting"):
        raise ValueError(f"Unknown flow '{flow}'. Choose 'content' or 'scouting'.")

    if flow in _compiled_flows:
        return _compiled_flows[flow]

    # Lazy import to avoid breaking module load when dependencies are absent
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
    except ImportError as exc:
        raise ImportError(
            "langchain-google-genai is required for the agentic AI features. "
            "Run: pip install langchain-google-genai"
        ) from exc

    try:
        from ai_models.agent_flows import build_content_flow, build_scouting_flow
    except ImportError as exc:
        raise ImportError(
            "ai_models/agent_flows.py is missing. "
            "This file is created as part of task 3.1."
        ) from exc

    from ai_models.agent_tools import (
        create_dossier,
        detect_changes,
        generate_caption,
        generate_card,
        get_percentiles,
        query_players,
    )

    llm = ChatGoogleGenerativeAI(
        model="gemini-2.0-flash",
        google_api_key=api_key,
        temperature=0,
    )
    tools = [query_players, get_percentiles, detect_changes, generate_card, create_dossier, generate_caption]

    if flow == "content":
        compiled = build_content_flow(llm, tools)
    else:
        compiled = build_scouting_flow(llm, tools)

    _compiled_flows[flow] = compiled
    return compiled


def run_agent(agent: Any, query: str) -> Dict[str, Any]:
    """
    Executes a natural language query against a compiled LangGraph agent.

    Args:
        agent: Compiled LangGraph agent returned by create_agent().
        query: Natural language query or task description.

    Returns:
        Dict with keys:
          - 'output' (str): Final natural language answer.
          - 'steps' (list): Intermediate tool-calling steps.
          - 'error' (str | None): Error message if execution failed, else None.
    """
    if not query or not query.strip():
        return {"output": "", "steps": [], "error": "Empty query provided."}

    try:
        from langchain_core.messages import HumanMessage

        config = {"recursion_limit": 10}
        result = agent.invoke(
            {"messages": [HumanMessage(content=query)]},
            config=config,
        )

        # Extract final message content
        messages = result.get("messages", [])
        output = ""
        steps = []

        for msg in messages:
            msg_type = type(msg).__name__
            if msg_type == "HumanMessage":
                continue
            elif msg_type == "AIMessage":
                content = getattr(msg, "content", "")
                tool_calls = getattr(msg, "tool_calls", [])
                if tool_calls:
                    steps.append({"type": "tool_call", "calls": [tc.get("name", "") for tc in tool_calls]})
                elif content:
                    output = str(content)
            elif msg_type == "ToolMessage":
                steps.append({"type": "tool_result", "content": str(getattr(msg, "content", ""))[:500]})

        return {"output": output, "steps": steps, "error": None}

    except Exception as exc:
        logger.error("run_agent error: %s", exc)
        error_msg = str(exc)
        if "recursion_limit" in error_msg.lower() or "recursion" in error_msg.lower():
            error_msg = "Agent exceeded maximum iterations (10). Try a simpler query."
        return {"output": "", "steps": [], "error": error_msg}
