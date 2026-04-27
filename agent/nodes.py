"""
StayEase Agent Nodes
---------------------
Each function is a LangGraph node: it receives the full AgentState,
performs a focused unit of work, and returns a *partial* state dict
with only the fields it changes.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import ToolNode

from agent.state import AgentState, IntentType
from agent.tools import STAYEASE_TOOLS

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# LLM setup
# ---------------------------------------------------------------------------


def _build_llm() -> ChatOpenAI:
    """
    Instantiate the LLM via OpenRouter.

    OpenRouter exposes an OpenAI-compatible API, so we use ChatOpenAI
    with a custom base_url and api_key pointing to OpenRouter.

    Model options (set OPENROUTER_MODEL in your .env to override):
      - "anthropic/claude-3.5-sonnet"        (recommended — best instruction following)
      - "meta-llama/llama-3.3-70b-instruct"  (fast & free tier available)
      - "google/gemini-flash-1.5"            (very low latency)
      - "openai/gpt-4o-mini"                 (cost-effective)

    OpenRouter docs: https://openrouter.ai/docs
    """
    import os

    return ChatOpenAI(
        model=os.environ.get("OPENROUTER_MODEL", "anthropic/claude-3.5-sonnet"),
        api_key=os.environ["OPENROUTER_API_KEY"],
        base_url="https://openrouter.ai/api/v1",
        temperature=0.1,
        default_headers={
            # Optional but recommended by OpenRouter for analytics / rate-limit tiers.
            "HTTP-Referer": os.environ.get("APP_URL", "https://stayease.app"),
            "X-Title": "StayEase AI Agent",
        },
    )


LLM = _build_llm()
LLM_WITH_TOOLS = LLM.bind_tools(STAYEASE_TOOLS)


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are StayEase Assistant, an AI agent for a short-term \
accommodation rental platform in Bangladesh.

You can ONLY help with three tasks:
1. SEARCH — Find available properties given location, dates, and number of guests.
2. DETAILS — Provide full information about a specific property.
3. BOOK — Create a confirmed booking for a property.

If the guest asks about anything outside these three tasks, politely explain \
that you can only help with searching, viewing property details, or making \
bookings, and offer to connect them with a human agent.

Always respond in a friendly, professional tone. Use Bangladeshi context \
(BDT currency symbol ৳, local place names) where relevant.

When you need information (e.g., dates are missing for a search), ask the \
guest for the missing details before calling a tool.
"""


# ---------------------------------------------------------------------------
# Node 1 — classify_intent_node
# ---------------------------------------------------------------------------


def classify_intent_node(state: AgentState) -> dict[str, Any]:
    """
    Inspect the latest guest message and classify it into one of:
    'search' | 'details' | 'book' | 'escalate' | 'unknown'.

    Updates: intent
    Next node: router (conditional edge)
    """
    last_human = next(
        (m for m in reversed(state["messages"]) if isinstance(m, HumanMessage)),
        None,
    )
    if last_human is None:
        return {"intent": "unknown"}

    text = last_human.content.lower()

    # Simple keyword-based classification; replace with LLM call for production.
    if any(
        kw in text
        for kw in (
            "search",
            "find",
            "available",
            "looking for",
            "need a room",
            "want a place",
        )
    ):
        intent: IntentType = "search"
    elif any(
        kw in text
        for kw in (
            "details",
            "tell me more",
            "about property",
            "information",
            "amenities",
            "rules",
        )
    ):
        intent = "details"
    elif any(
        kw in text for kw in ("book", "reserve", "confirm", "i'll take", "go ahead")
    ):
        intent = "book"
    elif any(
        kw in text
        for kw in ("human", "agent", "support", "help me with something else", "other")
    ):
        intent = "escalate"
    else:
        # Fallback — let the LLM decide in agent_node
        intent = "unknown"

    logger.info("classify_intent_node: intent=%s", intent)
    return {"intent": intent}


# ---------------------------------------------------------------------------
# Node 2 — agent_node  (the "brain")
# ---------------------------------------------------------------------------


def agent_node(state: AgentState) -> dict[str, Any]:
    """
    Core reasoning node. Calls the LLM (with tools bound) to decide
    what to do next: either respond to the guest or invoke a tool.

    Updates: messages (appends AIMessage which may contain tool_calls)
    Next node: tool_executor_node (if tool call present) or END
    """
    system_msg = SystemMessage(content=SYSTEM_PROMPT)
    conversation = [system_msg] + list(state["messages"])

    response: AIMessage = LLM_WITH_TOOLS.invoke(conversation)

    logger.info(
        "agent_node: tool_calls=%s",
        [tc["name"] for tc in (response.tool_calls or [])],
    )

    return {"messages": [response]}


# ---------------------------------------------------------------------------
# Node 3 — tool_executor_node
# ---------------------------------------------------------------------------

# LangGraph's built-in ToolNode handles calling the right tool function,
# catching exceptions, and wrapping results in ToolMessage objects.
tool_executor_node = ToolNode(tools=STAYEASE_TOOLS)


# ---------------------------------------------------------------------------
# Node 4 — extract_params_node
# ---------------------------------------------------------------------------


def extract_params_node(state: AgentState) -> dict[str, Any]:
    """
    After a tool call completes, parse the ToolMessage result and
    populate convenience fields on the state (search_results, listing_details,
    booking_id, etc.) so downstream nodes and the API layer can access them
    without re-parsing JSON.

    Updates: search_results | listing_details | booking_id | booking_confirmed | error_message
    Next node: agent_node (to generate the final human-readable reply)
    """
    updates: dict[str, Any] = {}

    # Walk backwards to find the most recent ToolMessage(s)
    for msg in reversed(state["messages"]):
        if not isinstance(msg, ToolMessage):
            break

        try:
            payload = (
                json.loads(msg.content) if isinstance(msg.content, str) else msg.content
            )
        except json.JSONDecodeError:
            logger.warning("extract_params_node: could not parse ToolMessage content")
            continue

        tool_name = msg.name  # set by ToolNode

        if tool_name == "search_available_properties":
            updates["search_results"] = payload if isinstance(payload, list) else []

        elif tool_name == "get_listing_details":
            if "error" in payload:
                updates["error_message"] = payload["error"]
            else:
                updates["listing_details"] = payload
                updates["listing_id"] = payload.get("id")

        elif tool_name == "create_booking":
            if "booking_id" in payload:
                updates["booking_id"] = payload["booking_id"]
                updates["booking_confirmed"] = True
            else:
                updates["error_message"] = payload.get("error", "Booking failed.")

    return updates


# ---------------------------------------------------------------------------
# Node 5 — escalate_node
# ---------------------------------------------------------------------------


def escalate_node(state: AgentState) -> dict[str, Any]:
    """
    Generates a handoff message and marks the conversation for human review.
    Triggered when intent == 'escalate' or the agent cannot handle the request.

    Updates: messages (appends escalation AIMessage)
    Next node: END
    """
    escalation_text = (
        "I'm sorry, I can only help with searching for properties, viewing listing "
        "details, or making bookings on StayEase. For anything else, I'm connecting "
        "you with a human agent — someone will be with you shortly. 🙏"
    )
    return {"messages": [AIMessage(content=escalation_text)]}


# ---------------------------------------------------------------------------
# Conditional edge helpers
# ---------------------------------------------------------------------------


def route_by_intent(state: AgentState) -> str:
    """
    Determines which node to visit after classify_intent_node.

    Returns the node name as a string (used in graph.add_conditional_edges).
    """
    intent = state.get("intent", "unknown")

    if intent == "escalate":
        return "escalate_node"

    # For search / details / book / unknown: let the LLM agent decide
    return "agent_node"


def route_after_agent(state: AgentState) -> str:
    """
    After the agent (LLM) responds, decide whether to execute a tool or end.
    """
    last_msg = state["messages"][-1]
    if isinstance(last_msg, AIMessage) and last_msg.tool_calls:
        return "tool_executor_node"
    return "__end__"
