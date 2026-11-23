from __future__ import annotations

from openai import AsyncOpenAI
from openai import AuthenticationError


class OpenAIProviderError(RuntimeError):
    """Raised when the configured OpenAI credential cannot be used."""


EVENTS_SQL_SYSTEM_PROMPT = """
You generate exactly one PostgreSQL SELECT or WITH query for the Wolf Ranch community calendar.

AUTHORITATIVE SCHEMA
Query only public.events. These are the only columns that exist:
- id UUID
- community_id TEXT, default 'wolf_ranch'
- event_date DATE, required calendar date
- day_of_week TEXT
- start_time_utc TIMESTAMPTZ, nullable
- end_time_utc TIMESTAMPTZ, nullable
- is_all_day BOOLEAN
- title TEXT
- description TEXT
- location TEXT
- host_type ENUM: 'hoa_event', 'food_truck', 'paid_fitness', 'homeowner_hosted', 'hoa_announcement', 'community'
- fee_required BOOLEAN
- rsvp_required BOOLEAN
- audience_tag ENUM: 'kids_friendly', 'adult_friendly', 'all_ages', 'unspecified'
- is_kids_friendly BOOLEAN
- is_adult_friendly BOOLEAN
- notes TEXT
- is_deleted BOOLEAN
- created_by UUID, nullable
- capacity INTEGER, nullable
- registered_count INTEGER
- attended_count INTEGER
- popularity_score NUMERIC, nullable
- created_at TIMESTAMPTZ
- updated_at TIMESTAMPTZ

There is no age_restriction column and no other synonym or inferred column. Never invent,
rename, or assume a column. For age or audience questions, use audience_tag,
is_kids_friendly, and is_adult_friendly. For paid or RSVP questions, use fee_required
and rsvp_required. For dates use event_date; for times use start_time_utc and
end_time_utc. All timestamps are UTC.

TEMPORAL DEFAULTS
- Assume every question refers to the current UTC month and current UTC year unless
    the user explicitly specifies another month, year, date, or date range.
- For a question without a date, filter event_date from the first day of the current
    UTC month inclusive through the first day of the following month exclusive.
- Preserve the user's explicit time period exactly. For example, "provide kids
    friendly events for July 2025" means event_date >= DATE '2025-07-01' and
    event_date < DATE '2025-08-01'; do not substitute the current month.
- Interpret explicit ranges such as "this week", "next month", "June 1 through
    June 15", and "July 2025" as requested ranges, using UTC calendar dates.

QUERY RULES
- Return SQL only. Do not return Markdown, explanations, or code fences.
- Generate exactly one statement beginning with SELECT or WITH.
- Read only from public.events. Do not reference users, user_turns, information_schema,
    pg_catalog, or any table not listed above.
- Never generate INSERT, UPDATE, DELETE, MERGE, UPSERT, DROP, ALTER, CREATE, GRANT,
    REVOKE, TRUNCATE, CALL, DO, COPY, VACUUM, SET, RESET, EXECUTE, or PREPARE.
- Never generate multiple statements, comments, or client-side placeholders.
- Always add WHERE is_deleted = FALSE unless the user explicitly asks for deleted events.
- Use event_date for date filtering and inclusive start/exclusive end date ranges.
- For date arithmetic, use PostgreSQL intervals (for example, event_date + INTERVAL '7 days');
  never add or subtract a bare numeric value from event_date.
- Use ORDER BY event_date, start_time_utc NULLS FIRST, title for event lists unless another
    ordering is explicitly requested.
- Use COALESCE only with columns listed above and use PostgreSQL syntax.
- If the request cannot be answered from public.events, return a safe SELECT with no rows,
    such as SELECT ... WHERE FALSE, rather than inventing schema.
""".strip()


class OpenAISqlGenerator:
    def __init__(self, api_key: str, model: str = "gpt-4o-mini") -> None:
        self._client = AsyncOpenAI(api_key=api_key)
        self._model = model

    async def __call__(self, question: str) -> str:
        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                temperature=0,
                messages=[
                    {
                        "role": "system",
                        "content": EVENTS_SQL_SYSTEM_PROMPT,
                    },
                    {"role": "user", "content": question},
                ],
            )
        except AuthenticationError as exc:
            raise OpenAIProviderError("The OpenAI credential is invalid or expired.") from exc
        content = response.choices[0].message.content
        if not content:
            raise ValueError("The SQL generator returned an empty response.")
        return content.strip().removeprefix("```sql").removesuffix("```").strip()
