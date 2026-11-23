# ROLE: Frontend Engineer (frontend_agent)

Build a modern chic, responsive web application using Next.js (App Router), Tailwind CSS, shadcn-ui, and Lucide icons.

### Requirements:

1. **Anti-Spam & Defensive UI Controls:**
   - **Synchronous Input Locking:** The moment the user presses `Enter` or clicks "Ask", immediately disable the submit button, set the input field to read-only, and trigger a subtle skeleton/spinner loader.
   - **Throttle / Debouncer:** Enforce a strict 1000ms debounce on submission events.
   - **Deterministic Idempotency Header:** Compute `SHA256(user_id + question_text.trim().toLowerCase() + current_utc_hour)` and supply it via the `Idempotency-Key` header.
   - **AbortController:** Bind active fetch calls to an `AbortController` instance. Abort the signal if the user leaves the route.
2. **SSE Streaming Consumer (`/admin` Ingestion):**
   - Implement an EventSource/fetch-based SSE reader for calendar image uploads.
   - Silently ignore incoming comment lines starting with `:` (SSE heartbeats).
   - Parse named events (`event: status`, `event: complete`) and update a dynamic progress bar across extraction stages.
3. **Quota & Feedback UI Separation:**
   - Top banner displays: `Monthly Quota: X / 5 questions used`.
   - **Feedback Controls:** Under each assistant response, render interactive Thumbs Up / Thumbs Down buttons.
   - Clicking allows submitting and editing a feedback comment. Persist state via `POST /api/v1/chat/feedback` without altering the quota visual badge.
4. **Data Visualization & Export:**
   - Render query responses in an interactive shadcn table (`Date & Time`, `Title`, `Location`, `Audience`, `Actions`).
   - Convert incoming UTC timestamps to the browser's local timezone via `Intl.DateTimeFormat`.
   - Row buttons: "Add to Google Calendar" (pre-filled UTC web link) and "Export .ics" file.

Provide clean, modular React components using standard TypeScript interfaces.