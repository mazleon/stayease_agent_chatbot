"""
StayEase Agent Tools
---------------------
Three async tools exposed to the LLM via the @tool decorator.
Each tool uses the asyncpg connection pool (db.get_pool) to query
the PostgreSQL database on Neon.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from db import get_pool


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
async def search_available_properties(
    location: str,
    check_in: str,
    check_out: str,
    num_guests: int,
) -> list[dict[str, Any]]:
    """
    Search for available property listings on StayEase.

    Queries the `listings` table for properties in the given location that:
      - have capacity >= num_guests
      - are NOT already booked (confirmed) for the requested date range

    Returns a list of matching property summaries including id, title,
    price_per_night_bdt, capacity, amenities, rating, and total_price_bdt
    for the requested stay duration.

    Used when: the agent classifies the guest's intent as 'search'.
    """
    check_in_date = date.fromisoformat(check_in)
    check_out_date = date.fromisoformat(check_out)
    nights = (check_out_date - check_in_date).days

    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                id::text,
                title,
                location,
                price_per_night_bdt,
                capacity,
                amenities,
                rating,
                thumbnail_url
            FROM listings
            WHERE
                location ILIKE $1
                AND capacity >= $2
                AND is_active = TRUE
                AND id NOT IN (
                    SELECT listing_id
                    FROM bookings
                    WHERE status != 'cancelled'
                      AND check_in  < $4
                      AND check_out > $3
                )
            ORDER BY rating DESC NULLS LAST
            LIMIT 10
            """,
            f"%{location}%",
            num_guests,
            check_in_date,
            check_out_date,
        )

    return [
        {
            "id": str(row["id"]),
            "title": row["title"],
            "location": row["location"],
            "price_per_night_bdt": row["price_per_night_bdt"],
            "total_price_bdt": row["price_per_night_bdt"] * nights,
            "capacity": row["capacity"],
            "amenities": list(row["amenities"]),
            "rating": float(row["rating"]) if row["rating"] is not None else None,
            "thumbnail_url": row["thumbnail_url"],
        }
        for row in rows
    ]


@tool("get_listing_details", args_schema=GetListingDetailsInput)
async def get_listing_details(listing_id: str) -> dict[str, Any]:
    """
    Fetch full details for a single property listing.

    Queries the `listings` table by primary key and returns all fields
    including description, house rules, cancellation policy, and host info.

    Used when: the agent classifies the guest's intent as 'details',
    or as a prerequisite before creating a booking.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT
                id::text,
                title,
                description,
                location,
                address,
                price_per_night_bdt,
                capacity,
                bedrooms,
                bathrooms,
                amenities,
                house_rules,
                cancellation_policy,
                host_name,
                host_phone,
                rating,
                review_count,
                thumbnail_url
            FROM listings
            WHERE id = $1::uuid
              AND is_active = TRUE
            """,
            listing_id,
        )

    if row is None:
        return {"error": f"Listing '{listing_id}' not found or is no longer active."}

    return {
        "id": str(row["id"]),
        "title": row["title"],
        "description": row["description"],
        "location": row["location"],
        "address": row["address"],
        "price_per_night_bdt": row["price_per_night_bdt"],
        "capacity": row["capacity"],
        "bedrooms": row["bedrooms"],
        "bathrooms": row["bathrooms"],
        "amenities": list(row["amenities"]),
        "house_rules": row["house_rules"],
        "cancellation_policy": row["cancellation_policy"],
        "host_name": row["host_name"],
        "host_phone": row["host_phone"],
        "rating": float(row["rating"]) if row["rating"] is not None else None,
        "review_count": row["review_count"],
        "thumbnail_url": row["thumbnail_url"],
    }


@tool("create_booking", args_schema=CreateBookingInput)
async def create_booking(
    listing_id: str,
    guest_name: str,
    guest_phone: str,
    check_in: str,
    check_out: str,
    num_guests: int,
) -> dict[str, Any]:
    """
    Create a confirmed booking for a property on StayEase.

    Verifies the listing exists and is available for the dates, then inserts
    a row into the `bookings` table with status='confirmed'.

    Returns the booking reference ID, total price in BDT, and a confirmation
    message. Raises an error if the listing is no longer available.

    Used when: the agent classifies the guest's intent as 'book' and all
    required parameters are available in state.
    """
    check_in_date = date.fromisoformat(check_in)
    check_out_date = date.fromisoformat(check_out)
    nights = (check_out_date - check_in_date).days

    pool = await get_pool()
    async with pool.acquire() as conn:
        # 1. Fetch listing & verify it exists
        listing = await conn.fetchrow(
            """
            SELECT id::text, title, location, price_per_night_bdt
            FROM listings
            WHERE id = $1::uuid AND is_active = TRUE
            """,
            listing_id,
        )
        if listing is None:
            return {"error": f"Listing '{listing_id}' not found or is no longer active."}

        price_per_night: int = listing["price_per_night_bdt"]
        total_price = price_per_night * nights

        # 2. Check availability (no overlapping confirmed bookings)
        conflict = await conn.fetchval(
            """
            SELECT COUNT(*) FROM bookings
            WHERE listing_id = $1::uuid
              AND status      != 'cancelled'
              AND check_in     < $3
              AND check_out    > $2
            """,
            listing_id,
            check_in_date,
            check_out_date,
        )
        if conflict > 0:
            return {
                "error": (
                    f"'{listing['title']}' is not available from {check_in} to {check_out}. "
                    "Please choose different dates."
                )
            }

        # 3. Insert booking inside a transaction
        async with conn.transaction():
            booking_row = await conn.fetchrow(
                """
                INSERT INTO bookings (
                    listing_id, guest_name, guest_phone,
                    check_in, check_out, num_guests,
                    total_price_bdt, status
                ) VALUES (
                    $1::uuid, $2, $3,
                    $4, $5, $6,
                    $7, 'confirmed'
                )
                RETURNING id::text, created_at
                """,
                listing_id,
                guest_name,
                guest_phone,
                check_in_date,
                check_out_date,
                num_guests,
                total_price,
            )

    # Build a human-readable reference from the UUID prefix
    booking_uuid_prefix = booking_row["id"][:8].upper()
    booking_ref = f"BKG-{check_in.replace('-', '')}-{booking_uuid_prefix}"

    return {
        "booking_id": booking_ref,
        "booking_uuid": booking_row["id"],
        "status": "confirmed",
        "listing_id": listing_id,
        "listing_title": listing["title"],
        "location": listing["location"],
        "check_in": check_in,
        "check_out": check_out,
        "nights": nights,
        "num_guests": num_guests,
        "total_price_bdt": total_price,
        "guest_name": guest_name,
        "guest_phone": guest_phone,
        "created_at": booking_row["created_at"].isoformat(),
        "confirmation_message": (
            f"✅ Booking confirmed! Your reference is **{booking_ref}**. "
            f"Total: ৳{total_price:,} for {nights} night(s). "
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
