from __future__ import annotations

import re
from typing import Any

from fastapi.encoders import jsonable_encoder


class UnsafeSqlError(ValueError):
    """Raised when generated SQL is outside the read-only query contract."""


class ReadOnlySqlGuard:
    _leading_comment = re.compile(r"^(?:--[^\n]*(?:\n|$)|/\*.*?\*/\s*)*", re.DOTALL)
    _statement_start = re.compile(r"^(SELECT|WITH)\b", re.IGNORECASE)
    _forbidden = re.compile(
        r"\b(?:INSERT|UPDATE|DELETE|UPSERT|MERGE|DROP|ALTER|TRUNCATE|CREATE|GRANT|REVOKE|"
        r"CALL|DO|COPY|VACUUM|SET|RESET|EXECUTE|PREPARE)\b",
        re.IGNORECASE,
    )
    _invalid_date_arithmetic = re.compile(
        r"\b(?:[a-z_]+\.)?event_date\s*[+-]\s*\d+(?:\.\d+)?\b",
        re.IGNORECASE,
    )
    _forbidden_tables = re.compile(
        r"\b(?:users|user_turns|profiles|monthly_usage|feedback_audit|pg_\w+|information_schema)\b",
        re.IGNORECASE,
    )

    @classmethod
    def validate(cls, query: str) -> str:
        normalized = cls._leading_comment.sub("", query).strip()
        if not normalized:
            raise UnsafeSqlError("Generated SQL is empty.")
        if normalized.endswith(";"):
            normalized = normalized[:-1].rstrip()
        if ";" in normalized:
            raise UnsafeSqlError("Multiple SQL statements are not allowed.")
        if not cls._statement_start.match(normalized):
            raise UnsafeSqlError("Only SELECT queries are allowed.")
        if cls._forbidden.search(normalized):
            raise UnsafeSqlError("Generated SQL contains a forbidden operation.")
        if cls._forbidden_tables.search(normalized):
            raise UnsafeSqlError("Queries can only access the events table.")
        if cls._invalid_date_arithmetic.search(normalized):
            raise UnsafeSqlError("Date arithmetic must use an interval, not a numeric value.")
        return normalized


async def execute_readonly(
    readonly_pool: Any,
    query: str,
    *parameters: Any,
    max_rows: int = 100,
    timeout: float = 5.0,
) -> list[dict[str, Any]]:
    safe_query = ReadOnlySqlGuard.validate(query)
    async with readonly_pool.acquire() as connection:
        rows = await connection.fetch(safe_query, *parameters, timeout=timeout)
    limited_rows = rows[:max_rows]
    return [jsonable_encoder(dict(row)) for row in limited_rows]
