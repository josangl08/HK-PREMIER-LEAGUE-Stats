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

# Flow name aliases for backward compatibility and feature naming consistency
FLOW_ALIASES = {"player_analysis": "scouting"}


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
    # Normalize flow name via aliases
    flow = FLOW_ALIASES.get(flow, flow)

    # 1. Try to load Subscriber Credentials (OAuth Bridge)
    from google.oauth2.credentials import Credentials
    creds = None
    if os.path.exists("token.json"):
        try:
            # Match the scope used in auth_bridge.py (Generative Language API — AI Studio track)
            creds = Credentials.from_authorized_user_file("token.json", ["https://www.googleapis.com/auth/generative-language"])
            print("🚀 BRIDGE ACTIVE: Using Gemini Subscriber Account (OAuth).")
            logger.info("Using Gemini Subscriber Bridge (OAuth Credentials).")
        except Exception as e:
            print(f"⚠️ BRIDGE ERROR: {e}")
            logger.warning("Failed to load subscriber credentials: %s", e)

    api_key = os.environ.get("GOOGLE_API_KEY", "").strip().strip('"').strip("'")
    if not api_key and not creds:
        raise EnvironmentError(
            "Neither GOOGLE_API_KEY nor subscriber 'token.json' found. "
            "Set GOOGLE_API_KEY or run scripts/auth_bridge.py."
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

    # Use Flash 2.0 by default — faster latency for Dash callbacks, active on AI Studio track
    model_name = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
    
    # Initialize LLM with credentials (OAuth Bridge) or API Key
    if creds:
        llm = ChatGoogleGenerativeAI(
            model=model_name,
            credentials=creds,
            temperature=0,
        )
    else:
        llm = ChatGoogleGenerativeAI(
            model=model_name,
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
