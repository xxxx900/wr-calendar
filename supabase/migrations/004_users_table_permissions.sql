-- Enable RLS on users table and allow authenticated users to check their own role
ALTER TABLE users ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS users_select_authenticated ON users;
CREATE POLICY users_select_authenticated ON users
    FOR SELECT TO authenticated
    USING (LOWER(email) = LOWER(auth.jwt() ->> 'email') OR auth.jwt() ->> 'email' IS NOT NULL);

GRANT SELECT ON users TO authenticated;
