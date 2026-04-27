"""
StayEase Agent Graph
---------------------
Assembles all nodes and edges into the compiled LangGraph StateGraph.

Graph topology:

  START
    │
    ▼
  classify_intent_node
    │
    ├─(escalate)──► escalate_node ──► END
    │
    └─(search/details/book/unknown)──► agent_node
                                          │
                          ┌───────────────┘
                          │
                    (has tool_calls?)
                          │
                    yes ──► tool_executor_node
                          │         │
                          │         ▼
                          │   extract_params_node
                          │         │
                          │         ▼
                          └──── agent_node  (loop until no more tool_calls)
                                    │
                                 no │
                                    ▼
                                   END
"""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from agent.state import AgentState
from agent.nodes import (
    agent_node,
    classify_intent_node,
    escalate_node,
    extract_params_node,
    route_after_agent,
    route_by_intent,
    tool_executor_node,
)


def build_graph() -> StateGraph:
    """
    Construct and compile the StayEase LangGraph agent.

    Returns the compiled graph, ready to be invoked with:
        graph.invoke({"messages": [...], "conversation_id": "..."})
    """
    builder = StateGraph(AgentState)

    # ── Register nodes ───────────────────────────────────────────────────────
    builder.add_node("classify_intent_node", classify_intent_node)
    builder.add_node("agent_node", agent_node)
    builder.add_node("tool_executor_node", tool_executor_node)
    builder.add_node("extract_params_node", extract_params_node)
    builder.add_node("escalate_node", escalate_node)

    # ── Entry edge ───────────────────────────────────────────────────────────
    builder.add_edge(START, "classify_intent_node")

    # ── Conditional: route by intent ─────────────────────────────────────────
    builder.add_conditional_edges(
        "classify_intent_node",
        route_by_intent,
        {
            "agent_node": "agent_node",
            "escalate_node": "escalate_node",
        },
    )

    # ── Conditional: route after agent responds ───────────────────────────────
    builder.add_conditional_edges(
        "agent_node",
        route_after_agent,
        {
            "tool_executor_node": "tool_executor_node",
            "__end__": END,
        },
    )

    # ── Tool execution → param extraction → back to agent ────────────────────
    builder.add_edge("tool_executor_node", "extract_params_node")
    builder.add_edge("extract_params_node", "agent_node")

    # ── Escalation always ends ────────────────────────────────────────────────
    builder.add_edge("escalate_node", END)

    return builder.compile()


# ---------------------------------------------------------------------------
# Module-level compiled graph instance (import and use directly)
# ---------------------------------------------------------------------------
graph = build_graph()


# ---------------------------------------------------------------------------
# Convenience helper used by FastAPI route handlers
# ---------------------------------------------------------------------------

async def run_agent(
    conversation_id: str,
    user_message: str,
    history: list[dict] | None = None,
) -> dict:
    """
    High-level async wrapper around the compiled graph.

    Parameters
    ----------
    conversation_id : str
        UUID linking this run to the conversations table.
    user_message : str
        The latest guest message.
    history : list[dict] | None
        Previous messages in LangChain serialized format:
        [{"type": "human", "content": "..."}, {"type": "ai", "content": "..."}, ...]

    Returns
    -------
    dict
        Final agent state after the graph completes. Callers should read
        ``state["messages"][-1].content`` for the response text.
    """
    from langchain_core.messages import HumanMessage, AIMessage

    # Reconstruct message objects from stored history
    messages = []
    for m in (history or []):
        if m.get("type") == "human":
            messages.append(HumanMessage(content=m["content"]))
        elif m.get("type") == "ai":
            messages.append(AIMessage(content=m["content"]))

    # Append the new human message
    messages.append(HumanMessage(content=user_message))

    initial_state: AgentState = {
        "conversation_id": conversation_id,
        "messages": messages,
        "intent": "unknown",
        "location": None,
        "check_in": None,
        "check_out": None,
        "num_guests": None,
        "listing_id": None,
        "listing_details": None,
        "booking_id": None,
        "booking_confirmed": False,
        "search_results": [],
        "error_message": None,
    }

    final_state = await graph.ainvoke(initial_state)
    return final_state