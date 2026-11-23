CREATE TABLE IF NOT EXISTS profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email TEXT,
    display_name TEXT,
    avatar_url TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

CREATE TABLE IF NOT EXISTS monthly_usage (
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    usage_month DATE NOT NULL,
    query_count INT NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    PRIMARY KEY (user_id, usage_month),
    CONSTRAINT monthly_usage_count_nonnegative CHECK (query_count >= 0)
);

CREATE TABLE IF NOT EXISTS feedback_audit (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    turn_id UUID NOT NULL REFERENCES user_turns(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    rating feedback_rating NOT NULL,
    comment TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

CREATE INDEX IF NOT EXISTS feedback_audit_turn_idx ON feedback_audit (turn_id, created_at DESC);
CREATE INDEX IF NOT EXISTS feedback_audit_user_idx ON feedback_audit (user_id, created_at DESC);

ALTER TABLE user_turns DROP CONSTRAINT IF EXISTS user_turns_user_id_fkey;
ALTER TABLE user_turns
    ADD CONSTRAINT user_turns_auth_user_id_fkey
    FOREIGN KEY (user_id) REFERENCES auth.users(id) NOT VALID;

ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE monthly_usage ENABLE ROW LEVEL SECURITY;
ALTER TABLE feedback_audit ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS profiles_select_own ON profiles;
CREATE POLICY profiles_select_own ON profiles FOR SELECT TO authenticated
    USING (id = auth.uid());

DROP POLICY IF EXISTS profiles_update_own ON profiles;
CREATE POLICY profiles_update_own ON profiles FOR UPDATE TO authenticated
    USING (id = auth.uid()) WITH CHECK (id = auth.uid());

DROP POLICY IF EXISTS monthly_usage_select_own ON monthly_usage;
CREATE POLICY monthly_usage_select_own ON monthly_usage FOR SELECT TO authenticated
    USING (user_id = auth.uid());

DROP POLICY IF EXISTS feedback_audit_select_own ON feedback_audit;
CREATE POLICY feedback_audit_select_own ON feedback_audit FOR SELECT TO authenticated
    USING (user_id = auth.uid());

REVOKE ALL ON profiles, monthly_usage, feedback_audit FROM authenticated;
GRANT SELECT, UPDATE (display_name, avatar_url, updated_at) ON profiles TO authenticated;
GRANT SELECT ON monthly_usage, feedback_audit TO authenticated;

CREATE OR REPLACE FUNCTION handle_new_auth_user()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
    INSERT INTO profiles (id, email, display_name, avatar_url)
    VALUES (
        NEW.id,
        NEW.email,
        COALESCE(NEW.raw_user_meta_data ->> 'full_name', NEW.raw_user_meta_data ->> 'name'),
        NEW.raw_user_meta_data ->> 'avatar_url'
    )
    ON CONFLICT (id) DO UPDATE SET
        email = EXCLUDED.email,
        display_name = COALESCE(EXCLUDED.display_name, profiles.display_name),
        avatar_url = COALESCE(EXCLUDED.avatar_url, profiles.avatar_url),
        updated_at = timezone('utc'::text, now());
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
    AFTER INSERT OR UPDATE OF email, raw_user_meta_data ON auth.users
    FOR EACH ROW EXECUTE FUNCTION handle_new_auth_user();