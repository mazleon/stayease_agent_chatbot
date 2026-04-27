-- StayEase PostgreSQL Schema
-- Run once to initialise the database.

-- ─────────────────────────────────────────────────────────────────────────────
-- Table: listings
-- Stores all property listings on the platform.
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS listings (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title               VARCHAR(200)    NOT NULL,
    description         TEXT,
    location            VARCHAR(150)    NOT NULL,          -- e.g. "Cox's Bazar"
    address             VARCHAR(300),
    price_per_night_bdt INTEGER         NOT NULL CHECK (price_per_night_bdt > 0),
    capacity            SMALLINT        NOT NULL CHECK (capacity >= 1),
    bedrooms            SMALLINT        NOT NULL DEFAULT 1,
    bathrooms           SMALLINT        NOT NULL DEFAULT 1,
    amenities           TEXT[]          NOT NULL DEFAULT '{}',
    house_rules         TEXT,
    cancellation_policy TEXT,
    host_name           VARCHAR(100),
    host_phone          VARCHAR(20),
    rating              NUMERIC(3, 2)   CHECK (rating BETWEEN 0 AND 5),
    review_count        INTEGER         NOT NULL DEFAULT 0,
    thumbnail_url       TEXT,
    is_active           BOOLEAN         NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_listings_location ON listings (location);
CREATE INDEX idx_listings_capacity ON listings (capacity);
CREATE INDEX idx_listings_active    ON listings (is_active);


-- ─────────────────────────────────────────────────────────────────────────────
-- Table: bookings
-- One row per reservation; links a guest to a listing for a date range.
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TYPE booking_status AS ENUM ('confirmed', 'cancelled', 'completed', 'pending');

CREATE TABLE IF NOT EXISTS bookings (
    id              UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    listing_id      UUID            NOT NULL REFERENCES listings (id) ON DELETE RESTRICT,
    guest_name      VARCHAR(150)    NOT NULL,
    guest_phone     VARCHAR(20)     NOT NULL,
    check_in        DATE            NOT NULL,
    check_out       DATE            NOT NULL,
    num_guests      SMALLINT        NOT NULL CHECK (num_guests >= 1),
    total_price_bdt INTEGER         NOT NULL CHECK (total_price_bdt > 0),
    status          booking_status  NOT NULL DEFAULT 'confirmed',
    notes           TEXT,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_dates CHECK (check_out > check_in)
);

-- Prevent double-booking: no two 'confirmed' bookings can overlap for same listing
CREATE UNIQUE INDEX idx_bookings_no_overlap ON bookings (listing_id, check_in, check_out)
    WHERE status = 'confirmed';

CREATE INDEX idx_bookings_listing   ON bookings (listing_id);
CREATE INDEX idx_bookings_checkin   ON bookings (check_in);


-- ─────────────────────────────────────────────────────────────────────────────
-- Table: conversations
-- Persists multi-turn chat sessions between guests and the AI agent.
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TYPE conversation_status AS ENUM ('active', 'escalated', 'closed');

CREATE TABLE IF NOT EXISTS conversations (
    id              UUID                    PRIMARY KEY DEFAULT gen_random_uuid(),
    guest_phone     VARCHAR(20),                        -- optional; for returning guests
    status          conversation_status     NOT NULL DEFAULT 'active',
    messages        JSONB                   NOT NULL DEFAULT '[]',
    -- messages element shape:
    --   { "role": "user"|"assistant", "content": "...", "timestamp": "ISO-8601" }
    booking_id      UUID                    REFERENCES bookings (id) ON DELETE SET NULL,
    metadata        JSONB                   NOT NULL DEFAULT '{}',
    -- metadata example: { "intent": "book", "location": "Cox's Bazar" }
    created_at      TIMESTAMPTZ             NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ             NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_conversations_status ON conversations (status);
CREATE INDEX idx_conversations_phone  ON conversations (guest_phone);