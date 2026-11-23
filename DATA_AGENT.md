# ROLE: Database Engineer (data_agent)

Generate a single production-ready PostgreSQL migration file (`001_initial_schema.sql`) for Supabase that serves as the foundation for a community calendar chatbot.

### Requirements:
1. **Roles & Sandboxing:**
   - Create unprivileged read-only role: `readonly_app`.
   - Grant `CONNECT` on database and `USAGE` on schema `public` to `readonly_app`.
   - Grant strictly `SELECT` on `events` to `readonly_app`. Explicitly revoke all mutation permissions (`INSERT`, `UPDATE`, `DELETE`, `TRUNCATE`).
2. **Schema & Tables (UTC Enforced):**
   - Use `TIMESTAMPTZ` for all timestamp columns with default `timezone('utc'::text, now())`.
   - **`users` Table:** `id` (UUID PK), `email` (TEXT UNIQUE), `role` (ENUM: `user`, `admin`, `calendar_admin`, `event_admin` DEFAULT `user`), `created_at` (TIMESTAMPTZ).
   - **`events` Table:** `id` (UUID PK), `community_id` (TEXT DEFAULT 'wolf_ranch'), `event_date` (DATE), `day_of_week` (TEXT), `start_time_utc` (TIMESTAMPTZ, nullable), `end_time_utc` (TIMESTAMPTZ, nullable), `is_all_day` (BOOLEAN DEFAULT FALSE), `title` (TEXT), `description` (TEXT), `location` (TEXT), `host_type` (ENUM: `hoa_event`, `food_truck`, `paid_fitness`, `homeowner_hosted`, `hoa_announcement`, `community`), `fee_required` (BOOLEAN DEFAULT FALSE), `rsvp_required` (BOOLEAN DEFAULT FALSE), `audience_tag` (ENUM: `kids_friendly`, `adult_friendly`, `all_ages`, `unspecified`), `is_kids_friendly` (BOOLEAN DEFAULT FALSE), `is_adult_friendly` (BOOLEAN DEFAULT FALSE), `notes` (TEXT), `is_deleted` (BOOLEAN DEFAULT FALSE), `created_by` (UUID REFERENCES users(id)), `created_at` (TIMESTAMPTZ), `updated_at` (TIMESTAMPTZ).
   - **Future Analytics Placeholders (Schema Only):** `capacity` (INT NULL), `registered_count` (INT DEFAULT 0), `attended_count` (INT DEFAULT 0), `popularity_score` (NUMERIC(3, 2) NULL).
   - **`user_turns` Table:** `id` (UUID PK), `user_id` (UUID REFERENCES users(id)), `idempotency_hash` (TEXT UNIQUE, nullable), `raw_question` (TEXT NOT NULL), `refined_question` (TEXT), `generated_sql` (TEXT), `raw_answer` (TEXT NOT NULL), `structured_payload` (JSONB), `execution_latency_ms` (INT), `tokens_used` (INT), `model_used` (TEXT), `flagged_pii` (BOOLEAN DEFAULT FALSE), `feedback_rating` (ENUM: `thumbs_up`, `thumbs_down` NULL), `feedback_comment` (TEXT NULL), `feedback_timestamp` (TIMESTAMPTZ NULL), `created_at` (TIMESTAMPTZ).
3. **Strict Column-Level Grant for Feedback:**
   - Enable Row Level Security (RLS) on `user_turns`.
   - Grant authenticated users `UPDATE` permission **strictly and exclusively** on columns `feedback_rating`, `feedback_comment`, and `feedback_timestamp` where `user_id = auth.uid()`.
   - Revoke table-wide `UPDATE` rights on `user_turns` to block alterations to `generated_sql`, `raw_question`, `raw_answer`, or `idempotency_hash`.
4. **Idempotency & Indexes:**
   - Composite index on `events(community_id, event_date, is_deleted)`.
   - Composite index on `events(is_kids_friendly, is_adult_friendly)` WHERE `is_deleted = FALSE`.
   - Unique index for calendar ingestion idempotency: `UNIQUE(community_id, event_date, title, COALESCE(start_time_utc, '1970-01-01 00:00:00+00'))`.

Produce raw, syntax-checked SQL without truncation.