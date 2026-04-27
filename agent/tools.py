from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from langchain_core.tools import tool
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Input schemas (Pydantic v2)
# ---------------------------------------------------------------------------


class SearchPropertiesInput(BaseModel):
    """Input schema for the property search tool."""

    location: str = Field(
        ...,
        description="City or area name, e.g. 'Cox's Bazar', 'Sylhet', 'Bandarban'.",
    )
    check_in: str = Field(
        ...,
        description="Check-in date in YYYY-MM-DD format.",
    )
    check_out: str = Field(
        ...,
        description="Check-out date in YYYY-MM-DD format.",
    )
    num_guests: int = Field(
        ...,
        ge=1,
        le=20,
        description="Number of guests (1–20).",
    )


class GetListingDetailsInput(BaseModel):
    """Input schema for the listing details tool."""

    listing_id: str = Field(
        ...,
        description="UUID of the property listing.",
    )


class CreateBookingInput(BaseModel):
    """Input schema for the booking creation tool."""

    listing_id: str = Field(
        ...,
        description="UUID of the property to book.",
    )
    guest_name: str = Field(
        ...,
        description="Full name of the primary guest.",
    )
    guest_phone: str = Field(
        ...,
        description="Guest contact phone number (Bangladeshi format preferred).",
    )
    check_in: str = Field(
        ...,
        description="Check-in date in YYYY-MM-DD format.",
    )
    check_out: str = Field(
        ...,
        description="Check-out date in YYYY-MM-DD format.",
    )
    num_guests: int = Field(
        ...,
        ge=1,
        description="Number of guests.",
    )


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------


@tool("search_available_properties", args_schema=SearchPropertiesInput)
def search_available_properties(
    location: str,
    check_in: str,
    check_out: str,
    num_guests: int,
) -> list[dict[str, Any]]:
    """
    Search for available property listings on StayEase.

    Queries the `listings` table for properties in the given location that:
      - have capacity >= num_guests
      - are NOT already booked for the requested date range

    Returns a list of matching property summaries including id, title,
    price_per_night_bdt, capacity, and amenities.

    Used when: the agent classifies the guest's intent as 'search'.

    Example output:
    [
        {
            "id": "a1b2c3d4-...",
            "title": "Ocean View Suite",
            "location": "Cox's Bazar",
            "price_per_night_bdt": 4500,
            "capacity": 4,
            "amenities": ["WiFi", "AC", "Sea View"],
            "rating": 4.7
        },
        ...
    ]
    """
    # returning mock data for now
    check_in_date = date.fromisoformat(check_in)
    check_out_date = date.fromisoformat(check_out)
    nights = (check_out_date - check_in_date).days

    return [
        {
            "id": "prop-001",
            "title": "Seabreeze Cottage",
            "location": location,
            "price_per_night_bdt": 3800,
            "total_price_bdt": 3800 * nights,
            "capacity": max(num_guests, 2),
            "amenities": ["WiFi", "AC", "Breakfast Included", "Sea View"],
            "rating": 4.6,
            "thumbnail_url": "https://example.com/img/seabreeze.jpg",
        },
        {
            "id": "prop-002",
            "title": "Hillside Family Resort",
            "location": location,
            "price_per_night_bdt": 6500,
            "total_price_bdt": 6500 * nights,
            "capacity": max(num_guests, 6),
            "amenities": ["WiFi", "AC", "Pool", "Kitchen", "Parking"],
            "rating": 4.9,
            "thumbnail_url": "https://example.com/img/hillside.jpg",
        },
    ]


@tool("get_listing_details", args_schema=GetListingDetailsInput)
def get_listing_details(listing_id: str) -> dict[str, Any]:
    """
    Fetch full details for a single property listing.

    Queries the `listings` table by primary key and returns all fields
    including description, house rules, cancellation policy, and host info.

    Used when: the agent classifies the guest's intent as 'details',
    or as a prerequisite before creating a booking.

    Example output:
    {
        "id": "prop-001",
        "title": "Seabreeze Cottage",
        "description": "Cozy beachfront cottage ...",
        "location": "Cox's Bazar",
        "address": "Plot 12, Kolatoli Beach Road",
        "price_per_night_bdt": 3800,
        "capacity": 4,
        "bedrooms": 2,
        "bathrooms": 1,
        "amenities": ["WiFi", "AC", "Breakfast Included"],
        "house_rules": "No smoking. Check-in after 2 PM.",
        "cancellation_policy": "Free cancellation up to 48 hours before check-in.",
        "host_name": "Rahim Uddin",
        "host_phone": "+8801711XXXXXX",
        "rating": 4.6,
        "review_count": 38
    }
    """
    # Stub
    if listing_id not in ("prop-001", "prop-002"):
        return {"error": f"Listing '{listing_id}' not found."}

    return {
        "id": listing_id,
        "title": "Seabreeze Cottage"
        if listing_id == "prop-001"
        else "Hillside Family Resort",
        "description": (
            "A beautifully furnished beachfront cottage steps away from Cox's Bazar "
            "Marine Drive. Perfect for couples and small families."
        ),
        "location": "Cox's Bazar",
        "address": "Plot 12, Kolatoli Beach Road, Cox's Bazar-4700",
        "price_per_night_bdt": 3800 if listing_id == "prop-001" else 6500,
        "capacity": 4 if listing_id == "prop-001" else 6,
        "bedrooms": 2,
        "bathrooms": 1,
        "amenities": ["WiFi", "AC", "Breakfast Included", "Sea View", "Hot Water"],
        "house_rules": "No smoking. No pets. Check-in after 2:00 PM. Check-out by 11:00 AM.",
        "cancellation_policy": "Free cancellation up to 48 hours before check-in.",
        "host_name": "Rahim Uddin",
        "host_phone": "+8801711000000",
        "rating": 4.6,
        "review_count": 38,
    }


@tool("create_booking", args_schema=CreateBookingInput)
def create_booking(
    listing_id: str,
    guest_name: str,
    guest_phone: str,
    check_in: str,
    check_out: str,
    num_guests: int,
) -> dict[str, Any]:
    """
    Create a confirmed booking for a property on StayEase.

    Inserts a row into the `bookings` table with status='confirmed' and
    returns the booking reference, total price (in BDT), and confirmation
    details.

    Used when: the agent classifies the guest's intent as 'book' and all
    required parameters (listing_id, guest info, dates) are available in state.

    Example output:
    {
        "booking_id": "BKG-20250601-XXXX",
        "status": "confirmed",
        "listing_title": "Seabreeze Cottage",
        "location": "Cox's Bazar",
        "check_in": "2025-06-01",
        "check_out": "2025-06-03",
        "num_guests": 2,
        "total_price_bdt": 7600,
        "guest_name": "Farhan Ahmed",
        "confirmation_message": "Your booking is confirmed! ..."
    }
    """
    # returning mock data for now
    check_in_date = date.fromisoformat(check_in)
    check_out_date = date.fromisoformat(check_out)
    nights = (check_out_date - check_in_date).days
    price_per_night = 3800 if listing_id == "prop-001" else 6500
    total = price_per_night * nights
    booking_ref = f"BKG-{check_in.replace('-', '')}-{str(uuid.uuid4())[:4].upper()}"

    return {
        "booking_id": booking_ref,
        "status": "confirmed",
        "listing_id": listing_id,
        "listing_title": "Seabreeze Cottage"
        if listing_id == "prop-001"
        else "Hillside Family Resort",
        "location": "Cox's Bazar",
        "check_in": check_in,
        "check_out": check_out,
        "nights": nights,
        "num_guests": num_guests,
        "total_price_bdt": total,
        "guest_name": guest_name,
        "guest_phone": guest_phone,
        "confirmation_message": (
            f"✅ Booking confirmed! Your reference is **{booking_ref}**. "
            f"Total: ৳{total:,} for {nights} night(s). "
            "You'll receive an SMS confirmation shortly."
        ),
    }


# ---------------------------------------------------------------------------
# Tool registry (convenient import for nodes.py / graph.py)
# ---------------------------------------------------------------------------

STAYEASE_TOOLS = [
    search_available_properties,
    get_listing_details,
    create_booking,
]
