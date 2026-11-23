-- Admin users are environment-specific and are not seeded by migrations.
-- Grant admin on a real project with:
--   INSERT INTO users (email, role) VALUES ('<admin-email>', 'admin')
--   ON CONFLICT (email) DO UPDATE SET role = EXCLUDED.role;
-- The local Docker stack seeds its own fictional admins in docker/db/080_seed.sql.
SELECT 1;
