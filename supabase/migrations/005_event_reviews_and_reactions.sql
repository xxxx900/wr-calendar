-- Migration 005: Event Reviews, Attendance Marking, and Distinct Reactions
-- Supports 1..5 star ratings, optional review comments, attendance confirmations, and anonymous publishing.
-- Supports distinct reactions: 'going' (Planning to go), 'love' (Love this), 'helpful' (Helpful).
-- Supports soft-deletion of reviews with partial unique indexing.

-- 1. Add denormalized summary columns to events if not present
ALTER TABLE events
    ADD COLUMN IF NOT EXISTS review_count INT NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS average_rating NUMERIC(3, 2),
    ADD COLUMN IF NOT EXISTS reaction_counts JSONB NOT NULL DEFAULT '{"going": 0, "love": 0, "helpful": 0}'::jsonb;

-- 2. Create event_reviews table with soft-delete support
CREATE TABLE IF NOT EXISTS event_reviews (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id UUID NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    rating SMALLINT NOT NULL CHECK (rating BETWEEN 1 AND 5),
    comment TEXT CHECK (comment IS NULL OR length(comment) <= 3000),
    attended_event BOOLEAN NOT NULL DEFAULT FALSE,
    is_anonymous BOOLEAN NOT NULL DEFAULT FALSE,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    deleted_at TIMESTAMPTZ NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

-- 3. Partial unique index allowing a fresh review after a previous soft-delete
CREATE UNIQUE INDEX IF NOT EXISTS event_reviews_active_user_event_idx
    ON event_reviews (event_id, user_id)
    WHERE is_deleted = FALSE;

-- 4. Create event_reactions table
CREATE TABLE IF NOT EXISTS event_reactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id UUID NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    reaction_type TEXT NOT NULL CHECK (reaction_type IN ('going', 'love', 'helpful')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    CONSTRAINT event_reactions_event_user_unique UNIQUE (event_id, user_id)
);

-- 5. Indexes for fast read performance
CREATE INDEX IF NOT EXISTS event_reviews_event_active_created_idx
    ON event_reviews (event_id, rating DESC, created_at DESC)
    WHERE is_deleted = FALSE;

CREATE INDEX IF NOT EXISTS event_reviews_user_idx
    ON event_reviews (user_id);

CREATE INDEX IF NOT EXISTS event_reactions_event_type_idx
    ON event_reactions (event_id, reaction_type);

CREATE INDEX IF NOT EXISTS event_reactions_user_idx
    ON event_reactions (user_id);

-- 6. Trigger functions for automatic aggregate synchronization on events table
CREATE OR REPLACE FUNCTION sync_event_review_metrics()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    target_event_id UUID;
    v_review_count INT;
    v_avg_rating NUMERIC(3, 2);
    v_attended_count INT;
BEGIN
    target_event_id := COALESCE(NEW.event_id, OLD.event_id);

    SELECT
        COUNT(*)::INT,
        ROUND(AVG(rating)::numeric, 2),
        COUNT(*) FILTER (WHERE attended_event = TRUE)::INT
    INTO
        v_review_count,
        v_avg_rating,
        v_attended_count
    FROM event_reviews
    WHERE event_id = target_event_id AND is_deleted = FALSE;

    UPDATE events
    SET
        review_count = COALESCE(v_review_count, 0),
        average_rating = v_avg_rating,
        attended_count = COALESCE(v_attended_count, 0),
        updated_at = timezone('utc'::text, now())
    WHERE id = target_event_id;

    RETURN NULL;
END;
$$;

DROP TRIGGER IF EXISTS trg_sync_event_review_metrics ON event_reviews;
CREATE TRIGGER trg_sync_event_review_metrics
    AFTER INSERT OR UPDATE OR DELETE ON event_reviews
    FOR EACH ROW EXECUTE FUNCTION sync_event_review_metrics();

CREATE OR REPLACE FUNCTION sync_event_reaction_metrics()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    target_event_id UUID;
    v_going_count INT;
    v_love_count INT;
    v_helpful_count INT;
BEGIN
    target_event_id := COALESCE(NEW.event_id, OLD.event_id);

    SELECT
        COUNT(*) FILTER (WHERE reaction_type = 'going')::INT,
        COUNT(*) FILTER (WHERE reaction_type = 'love')::INT,
        COUNT(*) FILTER (WHERE reaction_type = 'helpful')::INT
    INTO
        v_going_count,
        v_love_count,
        v_helpful_count
    FROM event_reactions
    WHERE event_id = target_event_id;

    UPDATE events
    SET
        reaction_counts = jsonb_build_object(
            'going', COALESCE(v_going_count, 0),
            'love', COALESCE(v_love_count, 0),
            'helpful', COALESCE(v_helpful_count, 0)
        ),
        updated_at = timezone('utc'::text, now())
    WHERE id = target_event_id;

    RETURN NULL;
END;
$$;

DROP TRIGGER IF EXISTS trg_sync_event_reaction_metrics ON event_reactions;
CREATE TRIGGER trg_sync_event_reaction_metrics
    AFTER INSERT OR UPDATE OR DELETE ON event_reactions
    FOR EACH ROW EXECUTE FUNCTION sync_event_reaction_metrics();

-- 7. Row Level Security & Permissions
ALTER TABLE event_reviews ENABLE ROW LEVEL SECURITY;
ALTER TABLE event_reactions ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS event_reviews_select ON event_reviews;
CREATE POLICY event_reviews_select ON event_reviews
    FOR SELECT TO authenticated, anon
    USING (is_deleted = FALSE OR user_id = auth.uid());

DROP POLICY IF EXISTS event_reviews_insert ON event_reviews;
CREATE POLICY event_reviews_insert ON event_reviews
    FOR INSERT TO authenticated
    WITH CHECK (user_id = auth.uid());

DROP POLICY IF EXISTS event_reviews_update ON event_reviews;
CREATE POLICY event_reviews_update ON event_reviews
    FOR UPDATE TO authenticated
    USING (
        user_id = auth.uid() OR
        EXISTS (
            SELECT 1 FROM users WHERE id = auth.uid() AND role IN ('admin', 'calendar_admin')
        )
    )
    WITH CHECK (
        user_id = auth.uid() OR
        EXISTS (
            SELECT 1 FROM users WHERE id = auth.uid() AND role IN ('admin', 'calendar_admin')
        )
    );

DROP POLICY IF EXISTS event_reviews_delete ON event_reviews;
CREATE POLICY event_reviews_delete ON event_reviews
    FOR DELETE TO authenticated
    USING (
        user_id = auth.uid() OR
        EXISTS (
            SELECT 1 FROM users WHERE id = auth.uid() AND role IN ('admin', 'calendar_admin')
        )
    );

DROP POLICY IF EXISTS event_reactions_select ON event_reactions;
CREATE POLICY event_reactions_select ON event_reactions
    FOR SELECT TO authenticated, anon
    USING (true);

DROP POLICY IF EXISTS event_reactions_insert ON event_reactions;
CREATE POLICY event_reactions_insert ON event_reactions
    FOR INSERT TO authenticated
    WITH CHECK (user_id = auth.uid());

DROP POLICY IF EXISTS event_reactions_update ON event_reactions;
CREATE POLICY event_reactions_update ON event_reactions
    FOR UPDATE TO authenticated
    USING (user_id = auth.uid())
    WITH CHECK (user_id = auth.uid());

DROP POLICY IF EXISTS event_reactions_delete ON event_reactions;
CREATE POLICY event_reactions_delete ON event_reactions
    FOR DELETE TO authenticated
    USING (user_id = auth.uid());

-- Permissions
REVOKE ALL ON event_reviews, event_reactions FROM PUBLIC;
GRANT SELECT, INSERT, UPDATE, DELETE ON event_reviews TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON event_reactions TO authenticated;
GRANT SELECT ON event_reviews, event_reactions TO anon;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'readonly_app') THEN
        GRANT SELECT ON event_reviews, event_reactions TO readonly_app;
    END IF;
END
$$;
