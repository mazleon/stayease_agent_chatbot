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
    import json
    import re
    from langchain_core.messages import HumanMessage, AIMessage

    # Reconstruct message objects from stored history
    messages = []
    search_results = []
    location = None
    check_in = None
    check_out = None
    num_guests = None
    listing_id = None
    
    text_lower = user_message.lower().strip()
    
    # Check if user is selecting from options (e.g., "option 1", "1", "first one", "the first")
    is_selecting_option = any(phrase in text_lower for phrase in [
        "option 1", "option 2", "option 3", "options 1", "first one", "first option",
        "number 1", "number 2", "number 3", "1st", "the first", "go with 1", "choose 1"
    ])
    
    # Check if user is providing booking info (name + phone)
    has_guest_name = any(phrase in text_lower for phrase in [
        "name is", "my name", "i am", "i'm", "full name"
    ])
    has_guest_phone = any(phrase in text_lower for phrase in [
        "phone", "mobile", "contact", "+880"
    ])
    is_booking_request = any(phrase in text_lower for phrase in [
        "book", "reserve", "confirm", "proceed"
    ])
    
    for m in (history or []):
        if m.get("type") == "human":
            content = m.get("content", "")
            messages.append(HumanMessage(content=content))
            
            # Extract location
            loc_match = re.search(r'(?:in|at|to|stay\s+in)\s+([A-Za-z]+(?:\s+[A-Za-z]+)?)', content, re.IGNORECASE)
            if loc_match and not location:
                location = loc_match.group(1).strip()
            
            # Extract dates
            dates = re.findall(r'\d{4}-\d{2}-\d{2}', content)
            month_match = re.findall(r'(january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{1,2}', content, re.IGNORECASE)
            year_match = re.findall(r'20\d{2}', content)
            
            if len(dates) >= 1 and not check_in:
                check_in = dates[0]
            if len(dates) >= 2 and not check_out:
                check_out = dates[1]
                
            # Extract guests
            guests_match = re.search(r'(\d+)\s*(?:guest|people|person)', content, re.IGNORECASE)
            if guests_match:
                num_guests = int(guests_match.group(1))
                
        elif m.get("type") == "ai":
            content = m.get("content", "")
            messages.append(AIMessage(content=content))
            
            # Extract listing_id from AI message (look for UUID pattern)
            uuid_matches = re.findall(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', content, re.IGNORECASE)
            if uuid_matches and not listing_id:
                listing_id = uuid_matches[0].lower()
            
            # Try to extract dates from AI message if not set yet
            if not check_in or not check_out:
                dates_in_msg = re.findall(r'\d{4}-\d{2}-\d{2}', content)
                if len(dates_in_msg) >= 2 and not check_in:
                    check_in = dates_in_msg[0]
                if len(dates_in_msg) >= 2 and not check_out:
                    check_out = dates_in_msg[1]

    # Append the new human message
    messages.append(HumanMessage(content=user_message))
    
    # Extract info from the latest user message
    text = user_message
    
    # Extract location - multiple patterns to catch different formats
    # Pattern 1: "in/at/to Dhaka", "stay in Coxs Bazar"
    loc_match = re.search(r'(?:in|at|to|stay\s+in)\s+([A-Za-z]+(?:\s+[A-Za-z]+)?)', text, re.IGNORECASE)
    if loc_match:
        location = loc_match.group(1).strip()
    # Pattern 2: If message is just a location name (like "Dhaka" or "Coxs Bazar" alone)
    # Check for short, simple messages that are likely just a location
    elif len(text.strip().split()) == 1:
        # Single word - could be a location like Dhaka, Sylhet, CoxsBazar
        potential_loc = text.strip()
        known_locations = ['dhaka', 'sylhet', 'bandarban', 'rangamati', 'khulna', 'chittagong']
        if potential_loc.lower() in known_locations:
            location = potential_loc
        elif potential_loc.lower().replace(' ', '') in ['coxsbazar', 'cox bazar', "cox'sbazar"]:
            location = "Cox's Bazar"
    elif len(text.strip().split()) == 2:
        # Two words - could be "Coxs Bazar" or "Cox's Bazar"
        potential_loc = text.strip()
        if 'coxs' in potential_loc.lower() or 'cox' in potential_loc.lower():
            location = "Cox's Bazar"
    
    # Extract dates
    dates = re.findall(r'\d{4}-\d{2}-\d{2}', text)
    if len(dates) >= 1:
        check_in = dates[0]
    if len(dates) >= 2:
        check_out = dates[1]
        
    # Extract guests
    guests_match = re.search(r'(\d+)\s*(?:guest|people|person|night)', text, re.IGNORECASE)
    if guests_match:
        num_guests = int(guests_match.group(1))
    
    # Check if user is selecting option - if so, try to get listing_id from history
    if is_selecting_option and not listing_id:
        # Look in previous AI messages for UUIDs
        for m in reversed(messages[:-1]):  # Exclude the latest message
            if isinstance(m, AIMessage):
                uuids = re.findall(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', m.content, re.IGNORECASE)
                if uuids:
                    # If user said "option 1" - get first UUID
                    if "1" in text_lower or "first" in text_lower:
                        listing_id = uuids[0].lower()
                    # If user said "option 2" - get second UUID
                    elif "2" in text_lower:
                        listing_id = uuids[1].lower() if len(uuids) > 1 else uuids[0].lower()
                    # If user said "option 3" - get third UUID
                    elif "3" in text_lower:
                        listing_id = uuids[2].lower() if len(uuids) > 2 else uuids[0].lower()
                    break
    
    # Also extract dates from AI messages if we don't have them yet
    if not check_in or not check_out:
        for m in messages[:-1]:
            if isinstance(m, AIMessage):
                # Look for dates in format like "June 1 to June 2, 2026"
                date_range_match = re.search(
                    r'(january|february|march|april|may|june|july|august|september|october|november|december)\s+(\d{1,2}).*?(to|[-–])\s*(january|february|march|april|may|june|july|august|september|october|november|december)\s+(\d{1,2})',
                    m.content, re.IGNORECASE
                )
                if date_range_match:
                    month_map = {'january': '01', 'february': '02', 'march': '03', 'april': '04', 
                                'may': '05', 'june': '06', 'july': '07', 'august': '08',
                                'september': '09', 'october': '10', 'november': '11', 'december': '12'}
                    try:
                        year_match = re.search(r'20\d{2}', m.content)
                        year = year_match.group(0) if year_match else '2026'
                        
                        if not check_in:
                            check_in = f"{year}-{month_map[date_range_match.group(1).lower()]}-{int(date_range_match.group(2)):02d}"
                        if not check_out:
                            check_out = f"{year}-{month_map[date_range_match.group(4).lower()]}-{int(date_range_match.group(5)):02d}"
                    except:
                        pass

    # Extract guest info if provided
    guest_name = None
    guest_phone = None
    
    name_match = re.search(r'(?:name is|full name|i am|i\'m|my name\'s)\s+([A-Za-z\s]+?)(?:,|\.|$)', text, re.IGNORECASE)
    if name_match:
        guest_name = name_match.group(1).strip()
    
    phone_match = re.search(r'(\+?880\d{9,10})', text, re.IGNORECASE)
    if phone_match:
        guest_phone = phone_match.group(1).strip()

    initial_state: AgentState = {
        "conversation_id": conversation_id,
        "messages": messages,
        "intent": "unknown",
        "location": location,
        "check_in": check_in,
        "check_out": check_out,
        "num_guests": num_guests,
        "listing_id": listing_id,
        "listing_details": None,
        "booking_id": None,
        "booking_confirmed": False,
        "search_results": search_results if search_results else [],
        "error_message": None,
    }

    final_state = await graph.ainvoke(initial_state)
    
    # Pass through search_results and other context from initial state if not set in final state
    if not final_state.get("search_results") and search_results:
        final_state["search_results"] = search_results
    if not final_state.get("listing_id") and listing_id:
        final_state["listing_id"] = listing_id
    if not final_state.get("check_in") and check_in:
        final_state["check_in"] = check_in
    if not final_state.get("check_out") and check_out:
        final_state["check_out"] = check_out
    if not final_state.get("num_guests") and num_guests:
        final_state["num_guests"] = num_guests
        
    return final_state