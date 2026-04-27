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
import os
from typing import Any

import httpx
from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.prebuilt import ToolNode

# Load environment variables from .env if present
load_dotenv()

from agent.state import AgentState, IntentType
from agent.tools import STAYEASE_TOOLS

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# LLM setup
# ---------------------------------------------------------------------------


def _build_llm():
    """
    Instantiate the LLM via OpenRouter using LangChain's OpenAI client.

    Model options (set OPENROUTER_MODEL in your .env):
      - "anthropic/claude-sonnet-4.6"       (recommended — best instruction following)
      - "anthropic/claude-3.5-sonnet"      (fallback)
      - "openai/gpt-4o-mini"            (cost-effective)
      - "meta-llama/llama-3.3-70b-instruct" (fast)

    Docs: https://openrouter.ai/docs
    """
    from langchain_openai import ChatOpenAI

    model_name = os.environ.get("OPENROUTER_MODEL", "openai/gpt-4o-mini")
    api_key = os.environ.get("OPENROUTER_API_KEY")
    
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY is not set in .env")

    return ChatOpenAI(
        model=model_name,
        temperature=0.1,
        timeout=60,
        max_retries=0,
        api_key=api_key,
        base_url="https://openrouter.ai/api/v1",
    )


LLM = _build_llm()
LLM_WITH_TOOLS = LLM.bind_tools(STAYEASE_TOOLS)


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are StayEase Assistant, a friendly AI booking agent for StayEase - a premier accommodation rental platform in Bangladesh.

## YOUR CORE RESPONSIBILITIES

You can ONLY help with these tasks. If user asks for anything else, politely explain you can only help with:
1. **SEARCH** - Finding available properties
2. **DETAILS** - Getting property information  
3. **BOOKING** - Making reservations

If the request is outside these areas, say: "I specialize in helping you find and book accommodations. For other inquiries, please contact our customer service at +880-2-12345678 or email support@stayease.com.bd"

## CONVERSATION GUIDELINES

- Always be friendly, helpful, and professional
- Use Bangladeshi context (BDT ৳ currency, local place names like Cox's Bazar, Sylhet, Dhaka, Bandarban, Rangamati)
- Keep responses concise but informative
- Use numbered lists for multiple properties
- Always mention prices in BDT (৳) format
- Ask for missing information one thing at a time

## USER SCENARIOS AND HOW TO HANDLE THEM

### SCENARIO 1: User wants to SEARCH/SEE PROPERTIES
When user says things like:
- "What properties are available?"
- "I need a room/place"
- "Find me accommodation in [location]"
- "Show me hotels/resorts/cottages in [location]"
- Just says a location name like "Dhaka", "Coxs Bazar", "Sylhet"

**Action:**
- If user provides location + dates + guests → Call search_available_properties tool
- If user provides ONLY location → Ask for check-in date, check-out date, and number of guests
- If user provides location + dates but no guests → Assume 1-2 guests or ask
- If user provides location + guests but no dates → Ask for check-in and check-out dates

### SCENARIO 2: User wants PROPERTY DETAILS
When user says things like:
- "Tell me more about [property name]"
- "What are the amenities?"
- "Show me details of [property]"
- "Information about [property name]"
- "What is the cancellation policy?"
- "Who is the host?"

**Action:**
- If you have listing_id from previous search → Call get_listing_details tool
- If you DON'T have listing_id but user mentions a property name:
  - First call search_available_properties with location to find the property
  - Then use that listing_id to get details
- Present information in a clear, organized way

### SCENARIO 3: User wants to BOOK
When user says things like:
- "I want to book"
- "Reserve this property"
- "Confirm my booking"
- "I'll take this one"
- "Book option 1/2/3"
- "First one please"
- Provides their name and/or phone number after seeing properties

**Action:**
- You MUST have ALL of: listing_id, check_in, check_out, num_guests, guest_name, guest_phone
- If listing_id is missing → Ask user to select a property first
- If dates are missing → Ask for check-in and check-out dates
- If guests missing → Ask for number of guests
- If name missing → Ask for guest's full name
- If phone missing → Ask for contact phone number
- Once you have EVERYTHING → Call create_booking IMMEDIATELY, do not ask for confirmation

### SCENARIO 4: User asks about AVAILABILITY
When user says things like:
- "Is [property] available?"
- "Can I book [property] for [dates]?"

**Action:**
- Call search_available_properties with the location and dates
- If property appears in results → It's available
- If not → Explain it's not available for those dates

### SCENARIO 5: User provides PARTIAL information
- If user says only "Coxs Bazar" → Ask for dates and guests
- If user says "Coxs Bazar, June 1-3" → Ask for number of guests
- Extract any information provided and ask for what's missing

### SCENARIO 6: User wants to ESCALATE
When user says:
- "Talk to human"
- "Connect me to agent"
- "I need speak to someone"

**Action:**
- Respond: "I'm connecting you with a human agent. Please call our customer service at +880-2-12345678 or email support@stayease.com.bd. They are available 24/7 to assist you."

## IMPORTANT TECHNICAL RULES

### Listing IDs (CRITICAL)
- Property listing IDs are UUIDs (e.g., 'a3f28c1d-8e4b-1a6f-0c5d-9e2b7a1c4f8d')
- NEVER guess or make up a listing ID
- ALWAYS use the exact UUID from search results
- If you don't have listing_id → Call search_available_properties first

### Handling User Selections
- "option 1" / "first" / "first one" → Use first listing's UUID
- "option 2" / "second" → Use second listing's UUID
- "option 3" / "third" → Use third listing's UUID

### After Successful Booking
Say: "🎉 Your booking is confirmed! 
Reference: BKG-XXXX-XXXX
Property: [property name]
Check-in: [date]
Check-out: [date]
Total: ৳[amount] for [n] night(s)

You'll receive an SMS confirmation shortly. Thank you for choosing StayEase!"

### If No Properties Found
Say something like: "I couldn't find any available properties matching your criteria. This could be because:
- All properties are booked for those dates
- The location doesn't have any listings yet
- The number of guests exceeds capacity

Would you like to try different dates or a different location?"
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

    # 1. ESCALATE (Priority: Handoff to human)
    if any(
        kw in text
        for kw in ("human", "agent", "support", "help me with something else", "other")
    ):
        intent: IntentType = "escalate"

    # 2. BOOK (Action-oriented)
    elif any(
        kw in text for kw in ("book", "reserve", "confirm", "i'll take", "go ahead")
    ):
        intent = "book"

    # 3. DETAILS (Specific info)
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

    # 4. SEARCH (Discovery)
    # Also matches when user just says a location name (like "Dhaka", "Coxs Bazar")
    known_locations = ['dhaka', 'coxs bazar', 'coxbazar', 'sylhet', 'bandarban', 'rangamati', 'khulna', 'chittagong']
    if any(
        kw in text
        for kw in (
            "search",
            "find",
            "available",
            "looking for",
            "need a room",
            "need a place",
            "want a place",
            "stay in",
            "accommodation",
            "hotel",
            "cottage",
            "resort",
            "place to stay",
            "properties",
        )
    ) or any(loc in text for loc in known_locations):
        intent = "search"
    else:
        # Fallback — let the LLM decide in agent_node
        intent = "unknown"

    logger.info("classify_intent_node: intent=%s", intent)
    return {"intent": intent}


# ---------------------------------------------------------------------------
# Node 2 — agent_node  (the "brain")
# ---------------------------------------------------------------------------


async def agent_node(state: AgentState) -> dict[str, Any]:
    """
    Primary LLM node: calls the model with the current history and tools,
    then returns the model's message. LangGraph's router will decide
    what to do next: either respond to the guest or invoke a tool.

    Updates: messages (appends AIMessage which may contain tool_calls)
    Next node: tool_executor_node (if tool call present) or END
    """
    import asyncio
    from openai import APIError, RateLimitError
    from httpx import TimeoutException

    system_msg = SystemMessage(content=SYSTEM_PROMPT)
    conversation = [system_msg] + list(state["messages"])

    last_error = None
    for attempt in range(3):
        try:
            # langgraph handles the async invocation properly
            response: AIMessage = await LLM_WITH_TOOLS.ainvoke(conversation)
            break
        except (RateLimitError, APIError, TimeoutException, TimeoutError) as e:
            last_error = e
            if attempt < 2:
                wait_time = 5**attempt
                logger.warning(
                    f"Rate/API/Timeout hit, retrying in {wait_time}s (attempt {attempt + 1}/3): {e}"
                )
                await asyncio.sleep(wait_time)
            continue

    else:
        error_msg = (
            "The service is temporarily busy. Please wait a moment and try again."
        )
        return {
            "messages": [AIMessage(content=error_msg)],
            "error_message": str(last_error or "LLM call failed after 3 attempts"),
        }

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
