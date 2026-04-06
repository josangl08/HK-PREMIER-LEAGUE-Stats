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

# Session-level quota tracker: models known to be exhausted (429)
_EXHAUSTED_MODELS: set = set()

# Flow name aliases for backward compatibility and feature naming consistency
FLOW_ALIASES = {"player_analysis": "scouting"}


def _get_llm_with_fallback(model_list, temperature=0):
    """Instantiate the first non-exhausted model from the priority list."""
    from langchain_google_genai import ChatGoogleGenerativeAI
    from utils.ai_config import GOOGLE_API_KEY

    available = [m for m in model_list if m and m not in _EXHAUSTED_MODELS] or model_list
    last_err = None
    for model_name in available:
        if not model_name:
            continue
        try:
            return ChatGoogleGenerativeAI(
                model=model_name,
                google_api_key=GOOGLE_API_KEY,
                temperature=temperature,
                max_retries=1,  # 1 = no retries (0 is a quirk that maps to SDK default of 5)
            )
        except Exception as e:
            logger.warning(f"⚠️ Model {model_name} failed at init. Trying fallback. Error: {e}")
            last_err = e
    raise EnvironmentError(f"❌ All models in hierarchy failed. Last error: {last_err}")

def create_agent(flow: str = "scouting") -> Any:
    """
    Creates and returns a compiled LangGraph agent using an Elite Multi-Model Strategy.
    Hierarchical Orchestration: Gemini 3 Pro -> Gemini 2.5 Pro
    Hierarchical Execution: Gemini 3 Flash -> Gemini 2.5 Flash -> Gemini 2 Flash
    """
    # Resolve alias if present
    flow = FLOW_ALIASES.get(flow, flow)

    if flow not in ("content", "scouting"):
        raise ValueError(f"Unknown flow '{flow}'. Choose 'content' or 'scouting'.")

    if flow in _compiled_flows:
        return _compiled_flows[flow]

    from utils.ai_config import AI_DEFAULTS

    # 1. Instantiate the Brain (Orchestrator) with fallback
    orchestrator_list = [
        AI_DEFAULTS["orchestrator"]["primary"],
        AI_DEFAULTS["orchestrator"]["fallback"]
    ]
    llm_brain = _get_llm_with_fallback(orchestrator_list, temperature=AI_DEFAULTS["orchestrator"]["temperature"])

    # 2. Instantiate the Worker (Executioner) with hierarchical fallbacks
    worker_list = [
        AI_DEFAULTS["worker"]["primary"],
        AI_DEFAULTS["worker"]["fallback_1"],
        AI_DEFAULTS["worker"]["fallback_2"]
    ]
    llm_worker = _get_llm_with_fallback(worker_list, temperature=AI_DEFAULTS["worker"]["temperature"])

    logger.info(f"🚀 ELITE MULTI-MODEL ACTIVE: Brain ({llm_brain.model}) + Worker ({llm_worker.model}).")

    # Lazy import flows and tools
    from ai_models.agent_flows import build_content_flow, build_scouting_flow
    from ai_models.agent_tools import (
        create_dossier, detect_changes, generate_caption,
        generate_card, get_percentiles, query_players, get_top_performers
    )

    tools = [query_players, get_percentiles, detect_changes, generate_card, create_dossier, generate_caption, get_top_performers]

    # Brain orchestrates, Worker executes tasks
    if flow == "content":
        compiled = build_content_flow(llm_brain, tools)
    else:
        compiled = build_scouting_flow(llm_brain, tools)

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
        from langchain_core.messages import HumanMessage, SystemMessage

        config = {"recursion_limit": 25}
        
        # Inyectamos una instrucción de sistema para maximizar la eficiencia en cada paso
        system_instruction = (
            "Eres un analista de datos ÉLITE de la liga de Hong Kong. "
            "Tu prioridad es la VELOCIDAD y la EFICIENCIA. "
            "NO hagas una llamada por cada jugador. Si el usuario pide comparar o listar mejores jugadores: "
            "1. USA 'get_top_performers' para obtener datos de grupo de una sola vez. "
            "2. Si necesitas métricas de eficiencia (Goles vs xG), pide ambos campos en una sola consulta o usa la herramienta de top performers. "
            "3. NUNCA hagas más de 2-3 llamadas a herramientas por consulta. Procesa los datos tú mismo si ya tienes la lista. "
            "4. Sé directo, usa tablas Markdown para los datos y da un análisis táctico breve pero profesional."
        )
        
        result = agent.invoke(
            {"messages": [SystemMessage(content=system_instruction), HumanMessage(content=query)]},
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
        error_msg = str(exc)
        if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
            # Mark primary orchestrator exhausted and clear cached flows so next
            # call to create_agent() rebuilds the graph with the fallback model.
            from utils.ai_config import AI_DEFAULTS
            primary = AI_DEFAULTS["orchestrator"]["primary"]
            _EXHAUSTED_MODELS.add(primary)
            _compiled_flows.clear()
            logger.warning("run_agent: %s quota exhausted — flow cache cleared, will use fallback.", primary)
            return {"output": "", "steps": [], "error": "quota_exhausted"}
        logger.error("run_agent error: %s", exc)
        if "recursion_limit" in error_msg.lower() or "recursion" in error_msg.lower():
            error_msg = "Agent exceeded maximum iterations (10). Try a simpler query."
        return {"output": "", "steps": [], "error": error_msg}
