"""
seed_db.py — Populates the StayEase listings table with sample properties.
Run once: uv run scratch/seed_db.py
"""

import asyncio
import os
import asyncpg
from dotenv import load_dotenv

load_dotenv()

LISTINGS = [
    {
        "title": "Seabreeze Cottage",
        "description": "A beautifully furnished beachfront cottage steps away from Cox's Bazar Marine Drive. Perfect for couples and small families.",
        "property_type": "cottage",
        "location": "Cox's Bazar",
        "address": "Plot 12, Kolatoli Beach Road, Cox's Bazar-4700",
        "price_per_night_bdt": 3800,
        "capacity": 4,
        "bedrooms": 2,
        "bathrooms": 1,
        "amenities": ["WiFi", "AC", "Breakfast Included", "Sea View", "Hot Water"],
        "house_rules": "No smoking. No pets. Check-in after 2:00 PM. Check-out by 11:00 AM.",
        "cancellation_policy": "Free cancellation up to 48 hours before check-in.",
        "host_name": "Rahim Uddin",
        "host_phone": "+8801711000001",
        "rating": 4.6,
        "review_count": 38,
    },
    {
        "title": "Hillside Family Resort",
        "description": "Spacious resort nestled in the hills, ideal for families and groups. Features a rooftop pool and panoramic views.",
        "property_type": "resort",
        "location": "Cox's Bazar",
        "address": "Hill View Road, Inani, Cox's Bazar-4730",
        "price_per_night_bdt": 6500,
        "capacity": 6,
        "bedrooms": 3,
        "bathrooms": 2,
        "amenities": ["WiFi", "AC", "Pool", "Kitchen", "Parking", "Garden"],
        "house_rules": "No loud music after 10 PM. Pets allowed with prior approval.",
        "cancellation_policy": "50% refund if cancelled 72 hours before check-in.",
        "host_name": "Nasrin Akter",
        "host_phone": "+8801811000002",
        "rating": 4.9,
        "review_count": 62,
    },
    {
        "title": "Sylhet Tea Garden Retreat",
        "description": "A tranquil bungalow surrounded by lush tea gardens. Ideal for a peaceful nature escape.",
        "property_type": "cottage",
        "location": "Sylhet",
        "address": "Lawachara, Moulvibazar, Sylhet-3200",
        "price_per_night_bdt": 4200,
        "capacity": 4,
        "bedrooms": 2,
        "bathrooms": 1,
        "amenities": ["WiFi", "Hot Water", "Balcony", "Garden View", "Breakfast Included"],
        "house_rules": "No smoking. Check-in after 1:00 PM.",
        "cancellation_policy": "Free cancellation up to 24 hours before check-in.",
        "host_name": "Karim Hossain",
        "host_phone": "+8801911000003",
        "rating": 4.7,
        "review_count": 27,
    },
    {
        "title": "Bandarban Mountain Lodge",
        "description": "A rustic lodge at 1,200 ft altitude offering stunning valley views. Perfect for trekkers and nature lovers.",
        "property_type": "lodge",
        "location": "Bandarban",
        "address": "Meghla Tourist Complex, Bandarban-4600",
        "price_per_night_bdt": 2900,
        "capacity": 5,
        "bedrooms": 2,
        "bathrooms": 2,
        "amenities": ["WiFi", "Fireplace", "Trekking Access", "Parking"],
        "house_rules": "No alcohol on premises. Check-out by 10:00 AM.",
        "cancellation_policy": "Non-refundable after booking.",
        "host_name": "Aung Marma",
        "host_phone": "+8801511000004",
        "rating": 4.5,
        "review_count": 19,
    },
    {
        "title": "Dhaka Premium Serviced Apartment",
        "description": "Modern fully-furnished serviced apartment in Gulshan, Dhaka. Ideal for business travellers and long stays.",
        "property_type": "apartment",
        "location": "Dhaka",
        "address": "Road 23, Gulshan 2, Dhaka-1212",
        "price_per_night_bdt": 5500,
        "capacity": 2,
        "bedrooms": 1,
        "bathrooms": 1,
        "amenities": ["WiFi", "AC", "Gym Access", "Laundry", "24/7 Security", "Kitchen"],
        "house_rules": "No parties. ID verification required at check-in.",
        "cancellation_policy": "Full refund if cancelled 48 hours before check-in.",
        "host_name": "Tahmina Rahman",
        "host_phone": "+8801611000005",
        "rating": 4.8,
        "review_count": 44,
    },
    {
        "title": "Cox's Bazar Beachfront Villa",
        "description": "A luxurious private villa directly on Laboni Beach with a private pool and personal chef service.",
        "property_type": "villa",
        "location": "Cox's Bazar",
        "address": "Laboni Beach Point, Cox's Bazar-4700",
        "price_per_night_bdt": 12000,
        "capacity": 10,
        "bedrooms": 5,
        "bathrooms": 4,
        "amenities": ["WiFi", "AC", "Private Pool", "Chef Service", "Sea View", "Parking", "BBQ"],
        "house_rules": "No events without prior approval. Check-in after 3:00 PM.",
        "cancellation_policy": "50% refund if cancelled 7 days before check-in.",
        "host_name": "Sabbir Ahmed",
        "host_phone": "+8801711000010",
        "rating": 4.8,
        "review_count": 15,
    },
    {
        "title": "Sreemangal Tea Estate Guesthouse",
        "description": "Charming colonial-era guesthouse inside a working tea estate. Wake up to misty gardens and fresh tea.",
        "property_type": "guesthouse",
        "location": "Sylhet",
        "address": "Finlay Tea Estate, Sreemangal, Moulvibazar-3210",
        "price_per_night_bdt": 3200,
        "capacity": 3,
        "bedrooms": 2,
        "bathrooms": 1,
        "amenities": ["WiFi", "Breakfast Included", "Tea Garden Tour", "Balcony", "Hot Water"],
        "house_rules": "No loud noise after 9 PM. Children welcome.",
        "cancellation_policy": "Free cancellation up to 48 hours before check-in.",
        "host_name": "Priya Devi",
        "host_phone": "+8801711000011",
        "rating": 4.6,
        "review_count": 33,
    },
    {
        "title": "Rangamati Lake View Resort",
        "description": "A serene lakeside resort in the Chittagong Hill Tracts, offering boat rides and indigenous cultural experiences.",
        "property_type": "resort",
        "location": "Rangamati",
        "address": "Kaptai Lake Shore, Rangamati-4500",
        "price_per_night_bdt": 4800,
        "capacity": 6,
        "bedrooms": 3,
        "bathrooms": 2,
        "amenities": ["WiFi", "Lake View", "Boat Rides", "Restaurant", "AC", "Parking"],
        "house_rules": "Respect local culture. No littering near the lake.",
        "cancellation_policy": "Free cancellation up to 72 hours before check-in.",
        "host_name": "Chakma Roy",
        "host_phone": "+8801911000012",
        "rating": 4.4,
        "review_count": 21,
    },
    {
        "title": "Old Dhaka Heritage Apartment",
        "description": "A tastefully restored apartment in historic Old Dhaka, walking distance from Lalbagh Fort and Ahsan Manzil.",
        "property_type": "apartment",
        "location": "Dhaka",
        "address": "Shakhari Bazar Lane, Old Dhaka-1100",
        "price_per_night_bdt": 2800,
        "capacity": 4,
        "bedrooms": 2,
        "bathrooms": 1,
        "amenities": ["WiFi", "AC", "Kitchen", "Heritage Tour Access"],
        "house_rules": "No smoking indoors. Respect neighbours.",
        "cancellation_policy": "Full refund if cancelled 24 hours before check-in.",
        "host_name": "Dilruba Begum",
        "host_phone": "+8801611000013",
        "rating": 4.3,
        "review_count": 18,
    },
    {
        "title": "Sundarbans Edge Eco Lodge",
        "description": "An eco-friendly lodge on the fringe of the Sundarbans mangrove forest. Guided wildlife tours available.",
        "property_type": "lodge",
        "location": "Khulna",
        "address": "Mongla Port Road, Bagerhat, Khulna-9300",
        "price_per_night_bdt": 3500,
        "capacity": 5,
        "bedrooms": 2,
        "bathrooms": 2,
        "amenities": ["Solar Power", "Wildlife Tours", "Mosquito Nets", "Local Meals", "Boat Access"],
        "house_rules": "No single-use plastics. Lights out by 11 PM.",
        "cancellation_policy": "50% refund if cancelled 48 hours before check-in.",
        "host_name": "Monir Hossain",
        "host_phone": "+8801811000014",
        "rating": 4.7,
        "review_count": 29,
    },
]


async def seed():
    url = os.getenv("DATABASE_URL")
    conn = await asyncpg.connect(url, ssl=True)

    inserted = 0
    skipped = 0
    try:
        for listing in LISTINGS:
            exists = await conn.fetchval(
                "SELECT id FROM listings WHERE title = $1 AND location = $2",
                listing["title"],
                listing["location"],
            )
            if exists:
                print(f"  SKIP  {listing['title']} ({listing['location']})")
                skipped += 1
                continue

            await conn.execute(
                """
                INSERT INTO listings (
                    title, description, property_type, location, address,
                    price_per_night_bdt, capacity, bedrooms, bathrooms,
                    amenities, house_rules, cancellation_policy,
                    host_name, host_phone, rating, review_count
                ) VALUES (
                    $1, $2, $3::property_type, $4, $5,
                    $6, $7, $8, $9,
                    $10, $11, $12,
                    $13, $14, $15, $16
                )
                """,
                listing["title"],
                listing["description"],
                listing["property_type"],
                listing["location"],
                listing["address"],
                listing["price_per_night_bdt"],
                listing["capacity"],
                listing["bedrooms"],
                listing["bathrooms"],
                listing["amenities"],
                listing["house_rules"],
                listing["cancellation_policy"],
                listing["host_name"],
                listing["host_phone"],
                listing["rating"],
                listing["review_count"],
            )
            print(f"  INSERT {listing['title']} ({listing['location']}) [{listing['property_type']}]")
            inserted += 1
    finally:
        await conn.close()

    print(f"\nDone — {inserted} inserted, {skipped} skipped.")


if __name__ == "__main__":
    asyncio.run(seed())
