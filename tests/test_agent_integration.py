"""
StayEase Agent — Integration Tests
------------------------------------
These tests hit the real OpenRouter API to verify the agent works end-to-end
with a live LLM. They are marked `integration` so they can be run explicitly:

    PYTHONPATH=. uv run pytest tests/test_agent_integration.py -v -m integration

They are automatically SKIPPED if OPENROUTER_API_KEY is not set in the environment.
Retry logic (via tenacity) handles transient 429 rate-limit errors gracefully.
"""

from __future__ import annotations

import os

import pytest
from dotenv import load_dotenv
from langchain_core.messages import AIMessage
from openai import RateLimitError
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

load_dotenv()

# ---------------------------------------------------------------------------
# Skip all tests in this file if no API key is present
# ---------------------------------------------------------------------------
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not os.getenv("OPENROUTER_API_KEY"),
        reason="OPENROUTER_API_KEY is not set — skipping integration tests.",
    ),
]


# ---------------------------------------------------------------------------
# Helper: run_agent with automatic retry on rate limit
# ---------------------------------------------------------------------------


@retry(
    retry=retry_if_exception_type(RateLimitError),
    wait=wait_exponential(multiplier=2, min=5, max=60),
    stop=stop_after_attempt(4),
    reraise=True,
)
async def _run_with_retry(conversation_id: str, user_message: str, history=None):
    """Wraps run_agent with exponential-backoff retry on 429 RateLimitError."""
    from agent.graph import run_agent

    return await run_agent(conversation_id, user_message, history=history)


# ---------------------------------------------------------------------------
# Test 1: Search flow (real LLM + real mock tool)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_integration_search_flow():
    """
    End-to-end: guest asks to search for rooms.
    Verifies the LLM correctly calls search_available_properties
    and returns a coherent natural-language reply.
    """
    final_state = await _run_with_retry(
        conversation_id="integ-conv-001",
        user_message=(
            "I need a place to stay in Cox's Bazar from June 1 to June 3, 2026 for 2 guests."
        ),
    )

    # The agent should have classified this as a search
    assert final_state["intent"] == "search", (
        f"Expected intent='search', got '{final_state['intent']}'"
    )

    # The mock tool should have been called and results cached in state
    assert isinstance(final_state["search_results"], list), (
        "search_results should be a list"
    )
    assert len(final_state["search_results"]) > 0, "search_results should not be empty"

    # The final LLM reply should be a non-empty AI message
    last_msg = final_state["messages"][-1]
    assert isinstance(last_msg, AIMessage), "Last message should be from the AI"
    assert len(last_msg.content) > 0, "AI reply should not be empty"

    print(f"\n[Search] AI Reply:\n{last_msg.content}\n")


# ---------------------------------------------------------------------------
# Test 2: Property details flow
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_integration_details_flow():
    """
    End-to-end: guest asks for more details about a specific property.
    Verifies the LLM calls get_listing_details with the right listing_id.
    """
    final_state = await _run_with_retry(
        conversation_id="integ-conv-002",
        user_message="Tell me more about the property with id prop-001.",
    )

    assert final_state["intent"] == "details", (
        f"Expected intent='details', got '{final_state['intent']}'"
    )

    # listing_details should be populated from the mock tool
    assert final_state["listing_details"] is not None, "listing_details should be set"
    assert final_state["listing_details"].get("id") == "prop-001", (
        "listing_details should contain the queried listing"
    )

    last_msg = final_state["messages"][-1]
    assert isinstance(last_msg, AIMessage)
    assert len(last_msg.content) > 0

    print(f"\n[Details] AI Reply:\n{last_msg.content}\n")


# ---------------------------------------------------------------------------
# Test 3: Booking flow
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_integration_booking_flow():
    """
    End-to-end: guest books a specific property.
    Verifies create_booking is called and booking_confirmed is set to True.
    """
    final_state = await _run_with_retry(
        conversation_id="integ-conv-003",
        user_message=(
            "Please book prop-001 for Farhan Ahmed, phone +8801711000000, "
            "from June 1 to June 3, 2025 for 2 guests."
        ),
    )

    assert final_state["intent"] == "book", (
        f"Expected intent='book', got '{final_state['intent']}'"
    )

    assert final_state["booking_confirmed"] is True, "booking_confirmed should be True"
    assert final_state["booking_id"] is not None, "booking_id should be set"

    last_msg = final_state["messages"][-1]
    assert isinstance(last_msg, AIMessage)
    assert len(last_msg.content) > 0

    print(f"\n[Booking] AI Reply:\n{last_msg.content}\n")


# ---------------------------------------------------------------------------
# Test 4: Escalation (no LLM call expected — pure routing)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_integration_escalation_flow():
    """
    End-to-end: guest asks for a human agent.
    No LLM call should be made — escalate_node generates a canned response.
    """
    # Escalation does NOT call the LLM, so no retry needed here
    from agent.graph import run_agent

    final_state = await run_agent(
        conversation_id="integ-conv-004",
        user_message="I want to talk to a human agent please.",
    )

    assert final_state["intent"] == "escalate", (
        f"Expected intent='escalate', got '{final_state['intent']}'"
    )

    last_msg = final_state["messages"][-1]
    assert isinstance(last_msg, AIMessage)
    assert "human agent" in last_msg.content.lower(), (
        "Escalation message should mention 'human agent'"
    )

    print(f"\n[Escalation] AI Reply:\n{last_msg.content}\n")


# ---------------------------------------------------------------------------
# Test 5: Multi-turn conversation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_integration_multi_turn():
    """
    End-to-end: simulates a two-turn conversation to verify the agent
    correctly receives and uses prior history.
    """
    history = [
        {"type": "human", "content": "Hi, I'm looking for a place to stay in Sylhet."},
        {
            "type": "ai",
            "content": (
                "Hello! I'd be happy to help you find accommodation in Sylhet. "
                "Could you please tell me your check-in and check-out dates, "
                "and how many guests will be staying?"
            ),
        },
    ]

    final_state = await _run_with_retry(
        conversation_id="integ-conv-005",
        user_message="We're 2 guests, checking in July 10 and checking out July 13.",
        history=history,
    )

    # Should have triggered the search flow based on the context
    last_msg = final_state["messages"][-1]
    assert isinstance(last_msg, AIMessage)
    assert len(last_msg.content) > 0

    print(f"\n[Multi-turn] AI Reply:\n{last_msg.content}\n")
