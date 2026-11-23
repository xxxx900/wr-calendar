-- Mirrors the chat_reader login role described at the end of 006_security_hardening.sql.
-- The password is a local dummy.
CREATE ROLE chat_reader LOGIN PASSWORD 'local-readonly' IN ROLE readonly_app;
ALTER ROLE chat_reader SET default_transaction_read_only = on;
ALTER ROLE chat_reader SET statement_timeout = '3s';
