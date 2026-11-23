from __future__ import annotations

from datetime import date, datetime, timezone
import logging
import re
from time import perf_counter
from typing import Any, Awaitable, Callable

import asyncpg

from app.modules.chat.service import AuthenticatedUser
from app.modules.chat.sql_guard import execute_readonly


GenerateSql = Callable[[str], Awaitable[str]]
logger = logging.getLogger(__name__)


class InvalidGeneratedQueryError(ValueError):
    """Raised when a generated query cannot be executed safely."""


class DeterministicEventQueryPlanner:
    _kids_friendly = re.compile(r"\b(?:kid|kids|child|children)[ -]?friendly\b", re.IGNORECASE)
    _adult_friendly = re.compile(r"\b(?:adult|adults)[ -]?friendly\b", re.IGNORECASE)

    @staticmethod
    def _month_bounds(now: datetime) -> tuple[date, date]:
        month_start = now.astimezone(timezone.utc).date().replace(day=1)
        if month_start.month == 12:
            next_month = month_start.replace(year=month_start.year + 1, month=1)
        else:
            next_month = month_start.replace(month=month_start.month + 1)
        return month_start, next_month

    def plan(self, question: str, now: datetime) -> tuple[str, tuple[date, date]] | None:
        if self._kids_friendly.search(question):
            audience_clause = "(is_kids_friendly = TRUE OR audience_tag IN ('kids_friendly', 'all_ages'))"
        elif self._adult_friendly.search(question):
            audience_clause = "(is_adult_friendly = TRUE OR audience_tag IN ('adult_friendly', 'all_ages'))"
        else:
            return None
        month_start, next_month = self._month_bounds(now)
        return (
            f"""
            SELECT
                id,
                community_id,
                event_date,
                day_of_week,
                start_time_utc,
                end_time_utc,
                is_all_day,
                title,
                description,
                location,
                host_type,
                fee_required,
                rsvp_required,
                audience_tag,
                is_kids_friendly,
                is_adult_friendly,
                notes,
                capacity,
                registered_count,
                attended_count,
                popularity_score
            FROM public.events
            WHERE is_deleted = FALSE
              AND event_date >= $1::date
              AND event_date < $2::date
              AND {audience_clause}
            ORDER BY event_date, start_time_utc NULLS FIRST, title
            """,
            (month_start, next_month),
        )


class ReadOnlyChatPipeline:
    def __init__(self, readonly_pool: Any, generate_sql: GenerateSql) -> None:
        self._readonly_pool = readonly_pool
        self._generate_sql = generate_sql
        self._planner = DeterministicEventQueryPlanner()

    async def __call__(self, question: str, user: AuthenticatedUser) -> dict[str, Any]:
        started = perf_counter()
        planned = self._planner.plan(question, datetime.now(timezone.utc))
        if planned is None:
            generated_sql = await self._generate_sql(question)
            parameters: tuple[Any, ...] = ()
        else:
            generated_sql, parameters = planned
        try:
            rows = await execute_readonly(self._readonly_pool, generated_sql, *parameters)
        except asyncpg.PostgresError as exc:
            logger.exception(
                "Invalid generated calendar query; generated_sql=%s; parameters=%r",
                generated_sql,
                parameters,
            )
            raise InvalidGeneratedQueryError("The calendar search could not be generated safely.") from exc
        return {
            "answer": self._format_answer(rows),
            "rows": rows,
            "generated_sql": generated_sql,
            "execution_latency_ms": round((perf_counter() - started) * 1000),
            "executed_at": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def _format_answer(rows: list[dict[str, Any]]) -> str:
        if not rows:
            return "No matching community events were found."
        return f"Found {len(rows)} matching community event(s)."
