# ABOUTME: LangGraph flow definitions for the HK Premier League Agent.
# ABOUTME: Defines CONTENT_FLOW and SCOUTING_FLOW state machines.

"""
LangGraph flow definitions for the HK Premier League Stats Platform.
Utilizes StateGraph with MessagesState for agentic tool orchestration.
"""

from typing import Annotated, Any, Dict, List, Literal, Sequence, TypedDict, Union

from langchain_core.messages import BaseMessage
from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.prebuilt import ToolNode


def build_scouting_flow(llm, tools):
    """
    Builds a LangGraph for player scouting.
    The agent can call tools to query players, get stats, and detect changes.
    """
    
    # 1. Define the tool node
    tool_node = ToolNode(tools)
    
    # 2. Define the model calling logic
    model = llm.bind_tools(tools)
    
    def call_model(state: MessagesState):
        messages = state['messages']
        response = model.invoke(messages)
        return {"messages": [response]}
    
    # 3. Define the conditional routing logic
    def should_continue(state: MessagesState) -> Literal["tools", END]:
        messages = state['messages']
        last_message = messages[-1]
        if last_message.tool_calls:
            return "tools"
        return END
    
    # 4. Initialize and compile the graph
    workflow = StateGraph(MessagesState)
    
    workflow.add_node("agent", call_model)
    workflow.add_node("tools", tool_node)
    
    workflow.add_edge(START, "agent")
    workflow.add_conditional_edges("agent", should_continue)
    workflow.add_edge("tools", "agent")
    
    return workflow.compile()


def build_content_flow(llm, tools):
    """
    Builds a LangGraph for content automation.
    The agent can call tools to generate cards, dossiers, and captions.
    """
    
    # 1. Define the tool node
    tool_node = ToolNode(tools)
    
    # 2. Define the model calling logic
    model = llm.bind_tools(tools)
    
    def call_model(state: MessagesState):
        messages = state['messages']
        response = model.invoke(messages)
        return {"messages": [response]}
    
    # 3. Define the conditional routing logic
    def should_continue(state: MessagesState) -> Literal["tools", END]:
        messages = state['messages']
        last_message = messages[-1]
        if last_message.tool_calls:
            return "tools"
        return END
    
    # 4. Initialize and compile the graph
    workflow = StateGraph(MessagesState)
    
    workflow.add_node("agent", call_model)
    workflow.add_node("tools", tool_node)
    
    workflow.add_edge(START, "agent")
    workflow.add_conditional_edges("agent", should_continue)
    workflow.add_edge("tools", "agent")
    
    return workflow.compile()
