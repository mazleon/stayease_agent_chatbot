-- StayEase PostgreSQL Schema
-- Run once to initialise the database.
-- Requires PostgreSQL 14+ (Neon uses pg 17).

-- True range-overlap enforcement for bookings requires the btree_gist extension.
CREATE EXTENSION IF NOT EXISTS btree_gist;


-- ─────────────────────────────────────────────────────────────────────────────
-- Table: listings
-- Stores all property listings on the platform.
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TYPE property_type AS ENUM (
    'apartment', 'cottage', 'resort', 'lodge', 'villa', 'guesthouse', 'hostel', 'other'
);

CREATE TABLE IF NOT EXISTS listings (
    id                  UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    title               VARCHAR(200)  NOT NULL,
    description         TEXT,
    property_type       property_type NOT NULL DEFAULT 'other',
    location            VARCHAR(150)  NOT NULL,          -- e.g. "Cox's Bazar"
    address             VARCHAR(300),
    price_per_night_bdt INTEGER       NOT NULL CHECK (price_per_night_bdt > 0),
    capacity            SMALLINT      NOT NULL CHECK (capacity >= 1),
    bedrooms            SMALLINT      NOT NULL DEFAULT 1,
    bathrooms           SMALLINT      NOT NULL DEFAULT 1,
    amenities           TEXT[]        NOT NULL DEFAULT '{}',
    house_rules         TEXT,
    cancellation_policy TEXT,
    host_name           VARCHAR(100),
    host_phone          VARCHAR(20),
    rating              NUMERIC(3,2)  CHECK (rating BETWEEN 0 AND 5),
    review_count        INTEGER       NOT NULL DEFAULT 0,
    thumbnail_url       TEXT,
    is_active           BOOLEAN       NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_listings_location      ON listings (location);
CREATE INDEX idx_listings_property_type ON listings (property_type);
CREATE INDEX idx_listings_capacity      ON listings (capacity);
CREATE INDEX idx_listings_active        ON listings (is_active);


-- ─────────────────────────────────────────────────────────────────────────────
-- Table: bookings
-- One row per reservation; links a guest to a listing for a date range.
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TYPE booking_status AS ENUM ('confirmed', 'cancelled', 'completed', 'pending');

CREATE TABLE IF NOT EXISTS bookings (
    id              UUID           PRIMARY KEY DEFAULT gen_random_uuid(),
    listing_id      UUID           NOT NULL REFERENCES listings (id) ON DELETE RESTRICT,
    guest_name      VARCHAR(150)   NOT NULL,
    guest_phone     VARCHAR(20)    NOT NULL,
    guest_email     VARCHAR(200),
    check_in        DATE           NOT NULL,
    check_out       DATE           NOT NULL,
    num_guests      SMALLINT       NOT NULL CHECK (num_guests >= 1),
    total_price_bdt INTEGER        NOT NULL CHECK (total_price_bdt > 0),
    status          booking_status NOT NULL DEFAULT 'confirmed',
    notes           TEXT,
    created_at      TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ    NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_dates CHECK (check_out > check_in),

    -- Prevents overlapping confirmed/pending/completed bookings for the same listing.
    -- A UNIQUE index on (check_in, check_out) only blocks exact duplicates;
    -- this EXCLUDE constraint blocks any date range overlap.
    EXCLUDE USING gist (
        listing_id WITH =,
        daterange(check_in, check_out, '[)') WITH &&
    ) WHERE (status != 'cancelled')
);

CREATE INDEX idx_bookings_listing ON bookings (listing_id);
CREATE INDEX idx_bookings_checkin ON bookings (check_in);
CREATE INDEX idx_bookings_status  ON bookings (status);


-- ─────────────────────────────────────────────────────────────────────────────
-- Table: conversations
-- One row per chat session. Messages are stored in conversation_messages.
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TYPE conversation_status AS ENUM ('active', 'escalated', 'closed');

CREATE TABLE IF NOT EXISTS conversations (
    id          TEXT                NOT NULL PRIMARY KEY,  -- client-generated UUID string
    guest_phone VARCHAR(20),
    status      conversation_status NOT NULL DEFAULT 'active',
    metadata    JSONB               NOT NULL DEFAULT '{}',
    -- metadata keys: intent, booking_id, booking_confirmed, search_results_count
    created_at  TIMESTAMPTZ         NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ         NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_conversations_status  ON conversations (status);
CREATE INDEX idx_conversations_phone   ON conversations (guest_phone);
CREATE INDEX idx_conversations_updated ON conversations (updated_at DESC);


-- ─────────────────────────────────────────────────────────────────────────────
-- Table: conversation_messages
-- One row per message turn, normalised out of conversations.
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS conversation_messages (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id TEXT        NOT NULL REFERENCES conversations (id) ON DELETE CASCADE,
    message_id      TEXT        NOT NULL,   -- client-assigned idempotency key
    role            VARCHAR(20) NOT NULL CHECK (role IN ('user', 'assistant')),
    content         TEXT        NOT NULL,
    metadata        JSONB       NOT NULL DEFAULT '{}',
    -- metadata keys for assistant turns: intent, booking_id, booking_confirmed, search_results_count
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX        idx_conv_messages_conv_id ON conversation_messages (conversation_id, created_at);
CREATE UNIQUE INDEX idx_conv_messages_msg_id  ON conversation_messages (message_id);
