"""
Quick smoke test for the three agent tools against the live Neon DB.
Run: uv run scratch/test_tools.py
"""
import asyncio
from agent.tools import search_available_properties, get_listing_details, create_booking


async def main():
    print("=== Tool Smoke Test ===\n")

    # 1. Search
    print("1. search_available_properties (Cox's Bazar, 2 guests, 2 nights)")
    results = await search_available_properties.ainvoke({
        "location": "Cox's Bazar",
        "check_in": "2025-08-01",
        "check_out": "2025-08-03",
        "num_guests": 2,
    })
    print(f"   Found {len(results)} properties")
    if results:
        first = results[0]
        print(f"   First: {first['title']} — ৳{first['price_per_night_bdt']}/night | rating: {first['rating']}")
        listing_id = first["id"]
    else:
        print("   No properties found — check that listings table is seeded.")
        return

    # 2. Details
    print(f"\n2. get_listing_details (id={listing_id})")
    details = await get_listing_details.ainvoke({"listing_id": listing_id})
    if "error" in details:
        print(f"   Error: {details['error']}")
    else:
        print(f"   Title: {details['title']}")
        print(f"   Amenities: {details['amenities']}")
        print(f"   Host: {details['host_name']} ({details['host_phone']})")

    # 3. Booking
    print(f"\n3. create_booking (prop={listing_id}, Farhan Ahmed)")
    booking = await create_booking.ainvoke({
        "listing_id": listing_id,
        "guest_name": "Farhan Ahmed",
        "guest_phone": "+8801700000001",
        "check_in": "2025-08-01",
        "check_out": "2025-08-03",
        "num_guests": 2,
    })
    if "error" in booking:
        print(f"   Error: {booking['error']}")
    else:
        print(f"   Booking ID: {booking['booking_id']}")
        print(f"   Total: ৳{booking['total_price_bdt']:,} for {booking['nights']} nights")
        print(f"   Status: {booking['status']}")

    print("\n✅ All tools passed smoke test.")


asyncio.run(main())
