"""
StayEase Agent Tests
--------------------
All tests mock the LLM (LLM_WITH_TOOLS) so they never hit the real
OpenRouter API. This keeps tests fast, free, and deterministic.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.messages import AIMessage

# ---------------------------------------------------------------------------
# Helpers to build fake LLM responses
# ---------------------------------------------------------------------------


def _ai_message_with_tool_call(tool_name: str, tool_input: dict) -> AIMessage:
    """Return an AIMessage that looks like the LLM called a tool."""
    tool_call = {
        "id": f"call_{tool_name}",
        "name": tool_name,
        "args": tool_input,
        "type": "tool_call",
    }
    return AIMessage(content="", tool_calls=[tool_call])


def _ai_message_text(text: str) -> AIMessage:
    """Return a plain AIMessage with no tool calls (end of turn)."""
    return AIMessage(content=text)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_flow():
    """
    Search intent: agent should call search_available_properties
    and return a message that mentions properties.
    """
    from agent.graph import run_agent

    # First call → LLM emits a tool call; second call → LLM returns final text
    mock_responses = [
        _ai_message_with_tool_call(
            "search_available_properties",
            {
                "location": "Cox's Bazar",
                "check_in": "2025-06-01",
                "check_out": "2025-06-03",
                "num_guests": 2,
            },
        ),
        _ai_message_text(
            "I found 2 properties in Cox's Bazar:\n"
            "1. Seabreeze Cottage ৳3,800/night\n"
            "2. Hillside Family Resort ৳6,500/night"
        ),
    ]

    mock_llm = MagicMock()
    mock_llm.invoke.side_effect = mock_responses

    with patch("agent.nodes.LLM_WITH_TOOLS", mock_llm):
        final_state = await run_agent(
            conversation_id="test-conv-001",
            user_message="I need a room in Cox's Bazar for 2 guests",
        )

    # Intent was correctly classified
    assert final_state["intent"] == "search"

    # LLM was called twice (tool call + final reply)
    assert mock_llm.invoke.call_count == 2

    # search_results were populated by extract_params_node
    assert isinstance(final_state["search_results"], list)
    assert len(final_state["search_results"]) == 2

    # Final assistant message mentions the location
    last_msg = final_state["messages"][-1]
    assert isinstance(last_msg, AIMessage)
    assert "Cox's Bazar" in last_msg.content or "Bazar" in last_msg.content


@pytest.mark.asyncio
async def test_details_flow():
    """
    Details intent: agent should call get_listing_details
    and return listing info.
    """
    from agent.graph import run_agent

    mock_responses = [
        _ai_message_with_tool_call(
            "get_listing_details",
            {"listing_id": "prop-001"},
        ),
        _ai_message_text(
            "Here are the details for Seabreeze Cottage:\n"
            "Price: ৳3,800/night | Rating: 4.6 | Location: Cox's Bazar"
        ),
    ]

    mock_llm = MagicMock()
    mock_llm.invoke.side_effect = mock_responses

    with patch("agent.nodes.LLM_WITH_TOOLS", mock_llm):
        final_state = await run_agent(
            conversation_id="test-conv-002",
            user_message="Tell me more about Seabreeze Cottage (prop-001)",
        )

    assert final_state["intent"] == "details"
    assert final_state["listing_details"] is not None
    assert final_state["listing_details"]["id"] == "prop-001"

    last_msg = final_state["messages"][-1]
    assert isinstance(last_msg, AIMessage)


@pytest.mark.asyncio
async def test_booking_flow():
    """
    Book intent: agent should call create_booking and set booking_confirmed.
    """
    from agent.graph import run_agent

    mock_responses = [
        _ai_message_with_tool_call(
            "create_booking",
            {
                "listing_id": "prop-001",
                "guest_name": "Farhan Ahmed",
                "guest_phone": "+8801711000000",
                "check_in": "2025-06-01",
                "check_out": "2025-06-03",
                "num_guests": 2,
            },
        ),
        _ai_message_text("✅ Your booking is confirmed! Reference: BKG-20250601-TEST"),
    ]

    mock_llm = MagicMock()
    mock_llm.invoke.side_effect = mock_responses

    with patch("agent.nodes.LLM_WITH_TOOLS", mock_llm):
        final_state = await run_agent(
            conversation_id="test-conv-003",
            user_message="Book Seabreeze Cottage for me",
        )

    assert final_state["intent"] == "book"
    assert final_state["booking_confirmed"] is True
    assert final_state["booking_id"] is not None


@pytest.mark.asyncio
async def test_escalation_flow():
    """
    Escalate intent: agent should skip LLM and return a handoff message.
    """
    from agent.graph import run_agent

    # escalate_node does NOT call the LLM — no mock needed
    with patch("agent.nodes.LLM_WITH_TOOLS", MagicMock()) as mock_llm:
        final_state = await run_agent(
            conversation_id="test-conv-004",
            user_message="I want to talk to a human agent",
        )

        # LLM was never called because escalate_node bypasses it
        mock_llm.invoke.assert_not_called()

    assert final_state["intent"] == "escalate"
    last_msg = final_state["messages"][-1]
    assert isinstance(last_msg, AIMessage)
    assert "human agent" in last_msg.content.lower()


@pytest.mark.asyncio
async def test_conversation_history_is_passed():
    """
    Verify that prior history messages are forwarded to the LLM
    on the next turn (multi-turn capability).
    """
    from agent.graph import run_agent

    mock_llm = MagicMock()
    mock_llm.invoke.return_value = _ai_message_text("Sure, let me help you search.")

    history = [
        {"type": "human", "content": "Hello!"},
        {"type": "ai", "content": "Hi there! How can I help you today?"},
    ]

    with patch("agent.nodes.LLM_WITH_TOOLS", mock_llm):
        final_state = await run_agent(
            conversation_id="test-conv-005",
            user_message="Find me a hotel",
            history=history,
        )

    # The LLM was called with the history + new message in context
    call_args = mock_llm.invoke.call_args[0][0]  # positional arg: list of messages
    # SystemMessage + 2 history + 1 new = at least 4 messages
    assert len(call_args) >= 4
