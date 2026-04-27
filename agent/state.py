from __future__ import annotations

from typing import Annotated, Any, Literal
from typing_extensions import TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


# ---------------------------------------------------------------------------
# Intent type
# ---------------------------------------------------------------------------

IntentType = Literal["search", "details", "book", "escalate", "unknown"]


# ---------------------------------------------------------------------------
# Core state
# ---------------------------------------------------------------------------


class AgentState(TypedDict):
    """
    Shared state object for the StayEase LangGraph agent.

    Every node reads from and/or writes to this object.
    LangGraph's `add_messages` reducer appends new messages rather than
    overwriting the list, preserving full conversation history.
    """

    # ── Conversation ────────────────────────────────────────────────────────
    conversation_id: str
    """Unique ID linking this graph run to a row in the `conversations` table."""

    messages: Annotated[list[BaseMessage], add_messages]
    """Full message history (HumanMessage / AIMessage / ToolMessage)."""

    # ── Routing ─────────────────────────────────────────────────────────────
    intent: IntentType
    """
    Classified intent of the latest guest message.
    Drives the conditional edge out of `classify_intent_node`.
    """

    # ── Search parameters (populated during search flow) ────────────────────
    location: str | None
    """Destination queried by the guest, e.g. 'Cox's Bazar'."""

    check_in: str | None
    """Check-in date as ISO-8601 string, e.g. '2025-06-01'."""

    check_out: str | None
    """Check-out date as ISO-8601 string, e.g. '2025-06-03'."""

    num_guests: int | None
    """Number of guests; used to filter listings by capacity."""

    # ── Listing context (populated when guest asks for details / books) ──────
    listing_id: str | None
    """ID of the property the guest is currently interested in."""

    listing_details: dict[str, Any] | None
    """Full listing record fetched from DB; cached to avoid redundant queries."""

    # ── Booking context ──────────────────────────────────────────────────────
    booking_id: str | None
    """Returned by `create_booking` tool on success."""

    booking_confirmed: bool
    """True once a booking has been successfully created."""

    # ── Tool output cache ────────────────────────────────────────────────────
    search_results: list[dict[str, Any]]
    """List of property dicts returned by `search_available_properties`."""

    # ── Error handling ───────────────────────────────────────────────────────
    error_message: str | None
    """Human-readable error surfaced to the guest when something goes wrong."""
