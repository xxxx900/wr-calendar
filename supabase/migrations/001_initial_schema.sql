CREATE EXTENSION IF NOT EXISTS pgcrypto;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'user_role') THEN
        CREATE TYPE user_role AS ENUM ('user', 'admin', 'calendar_admin', 'event_admin');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'host_type') THEN
        CREATE TYPE host_type AS ENUM ('hoa_event', 'food_truck', 'paid_fitness', 'homeowner_hosted', 'hoa_announcement', 'community');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'audience_tag') THEN
        CREATE TYPE audience_tag AS ENUM ('kids_friendly', 'adult_friendly', 'all_ages', 'unspecified');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'feedback_rating') THEN
        CREATE TYPE feedback_rating AS ENUM ('thumbs_up', 'thumbs_down');
    END IF;
END
$$;

CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT NOT NULL UNIQUE,
    role user_role NOT NULL DEFAULT 'user',
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

CREATE TABLE IF NOT EXISTS events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    community_id TEXT NOT NULL DEFAULT 'wolf_ranch',
    event_date DATE NOT NULL,
    day_of_week TEXT NOT NULL,
    start_time_utc TIMESTAMPTZ,
    end_time_utc TIMESTAMPTZ,
    is_all_day BOOLEAN NOT NULL DEFAULT FALSE,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    location TEXT NOT NULL DEFAULT '',
    host_type host_type NOT NULL,
    fee_required BOOLEAN NOT NULL DEFAULT FALSE,
    rsvp_required BOOLEAN NOT NULL DEFAULT FALSE,
    audience_tag audience_tag NOT NULL DEFAULT 'unspecified',
    is_kids_friendly BOOLEAN NOT NULL DEFAULT FALSE,
    is_adult_friendly BOOLEAN NOT NULL DEFAULT FALSE,
    notes TEXT NOT NULL DEFAULT '',
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    created_by UUID REFERENCES users(id),
    capacity INT,
    registered_count INT NOT NULL DEFAULT 0,
    attended_count INT NOT NULL DEFAULT 0,
    popularity_score NUMERIC(3, 2),
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    CONSTRAINT events_capacity_nonnegative CHECK (capacity IS NULL OR capacity >= 0),
    CONSTRAINT events_registered_count_nonnegative CHECK (registered_count >= 0),
    CONSTRAINT events_attended_count_nonnegative CHECK (attended_count >= 0),
    CONSTRAINT events_popularity_score_range CHECK (popularity_score IS NULL OR popularity_score BETWEEN 0 AND 9.99)
);

CREATE TABLE IF NOT EXISTS user_turns (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    idempotency_hash TEXT UNIQUE,
    raw_question TEXT NOT NULL,
    refined_question TEXT,
    generated_sql TEXT,
    raw_answer TEXT NOT NULL,
    structured_payload JSONB,
    execution_latency_ms INT,
    tokens_used INT,
    model_used TEXT,
    flagged_pii BOOLEAN NOT NULL DEFAULT FALSE,
    feedback_rating feedback_rating,
    feedback_comment TEXT,
    feedback_timestamp TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

CREATE INDEX IF NOT EXISTS events_community_date_deleted_idx
    ON events (community_id, event_date, is_deleted);

CREATE INDEX IF NOT EXISTS events_audience_idx
    ON events (is_kids_friendly, is_adult_friendly)
    WHERE is_deleted = FALSE;

CREATE UNIQUE INDEX IF NOT EXISTS events_ingestion_idempotency_idx
    ON events (
        community_id,
        event_date,
        title,
        COALESCE(start_time_utc, TIMESTAMPTZ '1970-01-01 00:00:00+00')
    );

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'readonly_app') THEN
        CREATE ROLE readonly_app NOLOGIN;
    END IF;
END
$$;

DO $$
BEGIN
    EXECUTE format('GRANT CONNECT ON DATABASE %I TO readonly_app', current_database());
END
$$;
GRANT USAGE ON SCHEMA public TO readonly_app;
GRANT SELECT ON events TO readonly_app;
REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON events FROM readonly_app;

ALTER TABLE user_turns ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON user_turns FROM authenticated;
GRANT SELECT ON user_turns TO authenticated;
GRANT UPDATE (feedback_rating, feedback_comment, feedback_timestamp)
    ON user_turns TO authenticated;

DROP POLICY IF EXISTS user_turns_select_own ON user_turns;
CREATE POLICY user_turns_select_own
    ON user_turns
    FOR SELECT
    TO authenticated
    USING (user_id = auth.uid());

DROP POLICY IF EXISTS user_turns_feedback_update_own ON user_turns;
CREATE POLICY user_turns_feedback_update_own
    ON user_turns
    FOR UPDATE
    TO authenticated
    USING (user_id = auth.uid())
    WITH CHECK (user_id = auth.uid());
