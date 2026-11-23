# Implementation History and Handoff

Updated: 2026-09-06
Project: `project_WR`

## Original Scope

The project is an MVP community calendar chatbot and admin portal with:

- FastAPI modular monolith backend
- Supabase PostgreSQL schema and RLS
- Redis idempotency and per-user query locks
- LangChain/OpenAI text-to-SQL pipeline
- GPT-4o Vision calendar image ingestion over SSE
- Next.js frontend with chat, feedback, event results, export actions, and admin ingestion
- Cloud Run deployment with Secret Manager bindings

The authoritative role requirements are in:

- `MANAGER.md`
- `BACKEND_AGENT.md`
- `DATA_AGENT.md`
- `FRONTEND_AGENT.md`
- `INFRASTRUCTURE_AGENT.md`

## Work Completed

### Database

Created `supabase/migrations/001_initial_schema.sql` with:

- `users`, `events`, and `user_turns` tables
- Required enums, foreign keys, UTC timestamp defaults, analytics placeholders
- Event search indexes
- Calendar ingestion uniqueness index
- `readonly_app` role with `SELECT` access to `events` only
- RLS and feedback-column update grants for `user_turns`
- Ownership policies based on `auth.uid()`

A static migration contract check passed. A real PostgreSQL/Supabase migration has not yet been executed.

### Backend Foundation

Created:

- `pyproject.toml`
- `app/main.py`
- `app/core/config.py`
- `app/core/auth.py`
- `app/core/database.py`
- `app/core/redis_client.py`
- `app/core/dependencies.py`
- `app/core/security.py`
- `app/core/redis_lock.py`

Implemented:

- Environment-based settings
- Supabase JWT bearer authentication
- Separate admin and read-only asyncpg pools
- Async Upstash Redis REST adapter
- Deterministic SHA-256 idempotency hashing by user, normalized question, and UTC hour
- UTC monthly quota key generation
- Redis user lock with `NX`, 30-second expiry, and unconditional `finally` cleanup
- Pre-LLM PII rejection for SSN, credit cards, email, and phone numbers

### Chat API

Created:

- `app/modules/chat/service.py`
- `app/modules/chat/router.py`
- `app/modules/chat/repository.py`
- `app/modules/chat/sql_guard.py`
- `app/modules/chat/pipeline.py`
- `app/modules/chat/openai_provider.py`

Implemented:

- `POST /api/v1/chat/query`
- `POST /api/v1/chat/feedback`
- Idempotency cache lookup before pipeline execution
- Five-question monthly quota for non-admin users
- PII filtering before LLM invocation
- Read-only SQL validation and execution through the read-only pool
- Telemetry persistence through the admin pool
- Feedback updates isolated from quota handling
- SQL guard rejecting mutations, DDL, multiple statements, and non-`SELECT`/`WITH` queries
- OpenAI SQL-generation adapter

### Calendar Ingestion

Created:

- `app/modules/calendar/service.py`
- `app/modules/calendar/router.py`
- `app/modules/calendar/vision.py`
- `app/modules/calendar/repository.py`

Implemented:

- `POST /api/v1/admin/calendar/ingest/stream`
- Admin and calendar-admin role checks
- SSE status events for upload, OCR, parsing, and database upsert stages
- Five-second heartbeat comments while processing
- Worker cancellation and cleanup on disconnect/error
- GPT-4o Vision adapter with JSON event extraction
- Event upsert repository

### Frontend

Created a minimal Next.js App Router application under `frontend/`:

- `frontend/package.json`
- `frontend/package-lock.json`
- `frontend/tsconfig.json`
- `frontend/app/layout.tsx`
- `frontend/app/globals.css`
- `frontend/app/page.tsx`

Implemented:

- Responsive chat interface
- Synchronous input lock while a query is active
- Deterministic `Idempotency-Key` generation
- AbortController cleanup on route unmount
- Monthly quota display
- UTC-to-browser-local timestamp formatting
- Feedback buttons
- Event result table
- Admin image upload
- Fetch-based SSE parsing
- Ignoring SSE comment heartbeat lines
- Progress bar for ingestion stages

### Infrastructure

Created:

- `Dockerfile`
- `.dockerignore`
- `infra/service.yaml`
- `infra/deploy.ps1`

Configured:

- Cloud Run request timeout: 600 seconds
- Min scale 0, max scale 3
- 1 vCPU and 1 GiB RAM
- Uvicorn keep-alive timeout: 65 seconds
- Secret Manager bindings for OpenAI, Supabase admin/service/read-only settings, JWT secret, and Upstash Redis

## Validation Completed

Passed:

- Python `compileall` checks for application and test code
- Full backend test suite: `20 passed` under Python 3.10
- PostgreSQL 16 migration execution passed with Supabase compatibility objects
- Database contract assertions passed for tables, indexes, `readonly_app` privileges, and `user_turns` RLS
- Docker image build passed as `wolf-ranch-calendar:test`
- Container smoke test passed; `/health` returned HTTP 200
- VS Code diagnostics on touched Python and TypeScript files
- Static migration contract check
- Static Cloud Run/infrastructure contract check
- Static Secret Manager binding check
- Frontend TypeScript check with `npx tsc --noEmit`
- Search for remaining `NotImplementedError` or empty `pass` providers returned no results

Environment limitations:

- Available Python interpreter is 3.10.6; project requires Python 3.11+. The suite still needs verification under Python 3.11+
- The local `psql` CLI is not installed; migration validation used a temporary PostgreSQL 16 Docker container with Supabase compatibility objects
- No live Supabase, Redis, OpenAI, or Cloud Run integration test has run
- Frontend dependencies are installed; `npm audit` reports one moderate and one high vulnerability through `next`/`postcss`. The available fix is a major Next.js upgrade and has not been applied automatically
- The workspace is not a Git repository, so no commit/diff history is available

## Required Next Work

### Highest Priority Correctness Fixes

1. Install/select Python 3.11+, then rerun all tests under `tests/` with the supported interpreter.
2. Run `001_initial_schema.sql` against a real Supabase project and fix any Supabase-specific compatibility issues.
3. Review the event upsert `ON CONFLICT` expression target. PostgreSQL expression-index conflict targets may require exact expression syntax or a named constraint/index strategy.
4. Add real Supabase integration tests for:
   - `readonly_app` mutation denial
   - `user_turns` feedback-only column updates
   - RLS ownership enforcement
   - event ingestion idempotency
5. Add Redis integration tests for concurrent locks, lock expiry, cache hits, quota increments, and exception cleanup.
6. Add API integration tests for authentication, roles, quota behavior, feedback isolation, and HTTP error responses.

### Security Fixes

1. Do not use `NEXT_PUBLIC_ACCESS_TOKEN` for production authentication. Anything prefixed `NEXT_PUBLIC_` is exposed to the browser bundle. Use Supabase client authentication and short-lived browser session tokens instead.
2. Replace the placeholder frontend user ID with the authenticated Supabase user ID. The backend and frontend must hash the exact same canonical input.
3. Confirm the idempotency formula is identical on both sides, including separators and UTC-hour formatting.
4. Validate and constrain all Vision-extracted event fields before database insertion. Current filtering only requires a title.
5. Ensure OpenAI-generated SQL cannot access tables outside the intended event schema and add query timeouts/row limits.
6. Confirm service-role credentials never appear in frontend environment files, build output, logs, or API responses.

### Authentication, Quota, and Feedback Implementation Plan

1. Use Supabase Auth as the application identity provider and enable Google OAuth in the Supabase dashboard. Google is the login method; Supabase remains the issuer of the JWT consumed by the backend.
2. Replace the temporary `NEXT_PUBLIC_ACCESS_TOKEN`, `NEXT_PUBLIC_USER_ID`, and `NEXT_PUBLIC_USER_ROLE` frontend values with a browser Supabase client and short-lived session access tokens.
3. Treat the verified JWT `sub` claim as the only user identity. The backend must ignore any user ID supplied by the browser.
4. Add Supabase-backed profile, monthly usage, and feedback audit tables. Keep quota enforcement server-side and atomic; Redis remains suitable for the current fast counter, while the database usage table provides durable reporting and future reconciliation.
5. Return the persisted `user_turns.id` from each chat query. Feedback requests must include that turn ID, and the backend must require that the turn belongs to the authenticated user.
6. Record feedback edits in an append-only audit table so feedback can be attributed to a user and reviewed later.
7. Test anonymous rejection, authenticated chat, quota persistence, cross-user feedback rejection, duplicate feedback behavior, and Google/Supabase session refresh before production rollout.

Completed implementation items:
- Implemented Supabase ES256/RS256 JWKS verification in `app/core/auth.py`.
- Added Google OAuth provider token verification endpoint `POST /api/v1/chat/auth/verify-admin`.
- Added admin bypass for question quotas and locks.
- Upgraded Admin Calendar Ingestion into a two-stage extract-and-review workflow (`POST /api/v1/admin/calendar/extract` & `POST /api/v1/admin/calendar/batch-upsert`).
- Added week navigation in `CalendarBoard.tsx` (previous week, this week, next week) with month auto-fetch.
- Added 1000ms frontend submit debounce in `frontend/app/page.tsx`.
- Enforced table-level query restrictions (`users`, `user_turns`, `profiles`, `monthly_usage`, `feedback_audit`, `information_schema`), 5-second query timeouts, and 100-row limits in `app/modules/chat/sql_guard.py`.
- Persisted full execution latency, tokens used, and model name telemetry into `user_turns` via `app/modules/chat/repository.py`.
- Anchored calendar exports (Google Calendar & Apple Calendar `.ics`) around Georgetown, TX.
- Replaced cell hover expansion with direct modal detail view.

### Backend Completion

1. Add robust SQL generation prompts with schema context, row limits, query timeouts, and safe UTC timestamp translation.
2. Persist `generated_sql`, latency, token counts, model name, refined question, and PII status into `user_turns` rather than only a partial payload.
3. Ensure quota increments are rolled back or otherwise handled when a request is rejected by the lock or PII check; current ordering should be reviewed against the intended quota semantics.
4. Add explicit handling for database errors, OpenAI timeouts, malformed Vision JSON, client disconnects, and Redis failures.
5. Implement a real Supabase auth/user synchronization strategy for the local `users` table.
6. Add event validation models using Pydantic and normalize all dates/times to UTC at the ingestion boundary.
7. Verify SSE framing and heartbeat behavior through an actual HTTP client, not only unit-level generator tests.

### Frontend Completion

1. Add a real Supabase auth flow and obtain the current user ID/session token securely.
2. Implement the required 1000 ms debounce on submission events; current UI locking exists but debounce behavior is not yet implemented.
3. Add feedback comment editing UI. Current buttons submit ratings but do not provide comment editing.
4. Return the assistant `user_turns.id` and use that ID for feedback. Current row fallback IDs are not guaranteed to identify a conversation turn.
5. Implement functional Google Calendar links populated from event fields.
6. Implement actual `.ics` file generation and download.
7. Add tests for SSE chunk boundaries, comments, named events, malformed payloads, aborts, and error states.
8. Run a browser-level smoke test at desktop and mobile sizes.
9. Review the visual design for accessibility, focus states, keyboard navigation, and screen-reader labels.

### Infrastructure Completion

1. Publish the validated `wolf-ranch-calendar:test` image through the staging deployment pipeline.
2. Validate `infra/service.yaml` with Google Cloud tooling.
3. Create/configure the referenced Secret Manager secrets and deploy to a non-production Cloud Run service.
4. Confirm Cloud Run streaming behavior with an ingestion request lasting longer than five seconds.
5. Add health/readiness checks and structured production logging.
6. Run `npm audit` and resolve or document the two reported frontend vulnerabilities without blindly applying breaking `--force` upgrades.

## Handoff Order

The safest continuation order is:

1. Fix security and contract issues listed above.
2. Provision Python 3.11+, pytest, PostgreSQL, Redis, and test credentials.
3. Execute migration and backend unit/integration tests.
4. Complete real Supabase authentication and frontend session handling.
5. Test the chat lifecycle end to end.
6. Test Vision ingestion and SSE heartbeats end to end.
7. Build and deploy the container to a staging Cloud Run service.
8. Run browser and production-like smoke tests.

## Current Assessment

The repository has a broad implementation skeleton covering the requested architecture, but it is not yet production-ready. The highest-risk unvalidated areas are database permission correctness, live authentication, frontend token handling, exact idempotency parity, event upsert SQL compatibility, and end-to-end SSE behavior.
