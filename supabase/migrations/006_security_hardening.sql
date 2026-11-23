-- Migration 006: close the three worst gaps from the security review.
-- Idempotent: safe to re-run.

-- 1. events: anon/authenticated could write to it; make them read-only via RLS.
-- The backend writes through the admin connection (table owner), which bypasses RLS.
-- readonly_app is listed because RLS applies to it too, and the chat and calendar reads need rows.
ALTER TABLE events ENABLE ROW LEVEL SECURITY;
REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON events FROM anon, authenticated;
GRANT SELECT ON events TO anon, authenticated;

DROP POLICY IF EXISTS events_public_read ON events;
CREATE POLICY events_public_read ON events
    FOR SELECT TO anon, authenticated, readonly_app
    USING (is_deleted = FALSE);

-- 2. users: any signed-in user could read every row (and so every admin email).
DROP POLICY IF EXISTS users_select_authenticated ON users;
CREATE POLICY users_select_authenticated ON users
    FOR SELECT TO authenticated
    USING (LOWER(email) = LOWER(auth.jwt() ->> 'email'));

-- 3. readonly_app serves LLM-generated SQL only: events and nothing else.
REVOKE SELECT ON event_reviews, event_reactions FROM readonly_app;
ALTER ROLE readonly_app SET default_transaction_read_only = on;
ALTER ROLE readonly_app SET statement_timeout = '3s';

-- query_to_xml runs a SQL string the statement guard never parses.
-- Hosted Supabase may refuse a REVOKE on pg_catalog functions; that must not abort the migration.
DO $$
BEGIN
    REVOKE EXECUTE ON FUNCTION
        query_to_xml(text, boolean, boolean, text),
        query_to_xmlschema(text, boolean, boolean, text),
        query_to_xml_and_xmlschema(text, boolean, boolean, text)
    FROM PUBLIC;
EXCEPTION WHEN insufficient_privilege THEN
    RAISE WARNING 'could not revoke EXECUTE on query_to_xml*: %', SQLERRM;
END
$$;

-- Manual step on the real Supabase project (no password belongs in this file).
-- ALTER ROLE settings on readonly_app are not inherited through membership, so the
-- login role needs its own copies:
--   CREATE ROLE chat_reader LOGIN PASSWORD '<generate-a-password>' IN ROLE readonly_app;
--   ALTER ROLE chat_reader SET default_transaction_read_only = on;
--   ALTER ROLE chat_reader SET statement_timeout = '3s';
-- Then point SUPABASE_READONLY_URL at chat_reader.
