# ROLE: Senior Backend Engineer (backend_agent)

Implement a FastAPI **Modular Monolith** in Python 3.11+ structured into isolated domain packages (`app/modules/auth`, `app/modules/calendar`, `app/modules/chat`).

### Technical Requirements:

1. **Deterministic Idempotency & Zombie-Proof Locking:**
   - On `POST /api/v1/chat/query`, compute deterministic hash: `SHA256(f"{user_id}:{raw_question.strip().lower()}:{datetime.now(timezone.utc).strftime('%Y-%m-%d-%H')}")`.
   - If an entry exists in Redis for this hash, immediately return the cached payload.
   - Acquire Redis lock: `acquired = await redis.set(f"lock:user:{user_id}", 1, nx=True, ex=30)`.
   - If not acquired, return HTTP 429 (`{"detail": "A query is currently processing. Please wait."}`).
   - Wrap the entire downstream execution inside a `try...finally` block that unconditionally executes `await redis.delete(f"lock:user:{user_id}")`.
2. **Quota vs. Feedback Isolation:**
   - **Query Quota:** Enforce strict 5 questions per user per UTC month (`rate_limit:quota:{user_id}:{YYYY-MM}`) via FastAPI dependency *before* invoking LangChain. Non-admins exceeding 5 get HTTP 429.
   - **Feedback Isolation:** `POST /api/v1/chat/feedback` must execute an `UPDATE` on `user_turns` targeting `feedback_rating`, `feedback_comment`, and `feedback_timestamp`. This endpoint must NEVER check or decrement the monthly quota.
3. **Resilient SSE Ingestion with Heartbeat Pings:**
   - Route: `POST /api/v1/admin/calendar/ingest/stream` using `EventSourceResponse` (Server-Sent Events).
   - Restrict to `admin` / `calendar_admin`.
   - Use an asynchronous generator that concurrently invokes the OpenAI `gpt-4o` Vision call while running an active background timer emitting an SSE comment heartbeat (`: ping\n\n`) every 5 seconds. This guarantees intermediate reverse proxies and Cloud Run do not terminate the socket with an HTTP 504.
   - Yield progressive status messages:
     - `event: status, data: {"stage": "upload_received", "pct": 10}`
     - `event: status, data: {"stage": "vision_ocr_processing", "pct": 40}`
     - `event: status, data: {"stage": "parsing_and_validating", "pct": 75}`
     - `event: status, data: {"stage": "database_upsert", "pct": 90}`
     - `event: complete, data: {"inserted": 34, "updated": 2}`
4. **Low-Memory PII Filter:**
   - Pre-compiled regex scanner (`PIISanitizer`) checking for SSN, credit cards, emails, and phone numbers. Reject high-risk inputs before LLM invocation.
5. **Sandboxed Text-to-SQL Pipeline:**
   - Use `readonly_pool` (unprivileged `readonly_app` role) for running LLM-generated `SELECT` queries.
   - Parse and convert all client timestamps to UTC before query execution.
   - Persist full telemetry to `user_turns` via `admin_pool`.

Write complete, functional code with all imports, error handling, and zero omitted logic.