from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any


async def persist_turn(
    admin_pool: Any,
    user_id: str,
    raw_question: str,
    idempotency_hash: str,
    payload: dict[str, Any],
) -> str:
    async with admin_pool.acquire() as connection:
        turn_id = await connection.fetchval(
            """
            INSERT INTO user_turns (
                user_id, raw_question, generated_sql, raw_answer, structured_payload,
                execution_latency_ms, tokens_used, model_used, flagged_pii,
                idempotency_hash, created_at
            )
            VALUES ($1, $2, $3, $4, $5::jsonb, $6, $7, $8, $9, $10, $11)
            ON CONFLICT (idempotency_hash) DO UPDATE SET
                generated_sql = EXCLUDED.generated_sql,
                raw_answer = EXCLUDED.raw_answer,
                structured_payload = EXCLUDED.structured_payload,
                execution_latency_ms = EXCLUDED.execution_latency_ms,
                tokens_used = EXCLUDED.tokens_used,
                model_used = EXCLUDED.model_used
            RETURNING id
            """,
            user_id,
            raw_question,
            payload.get("generated_sql") if isinstance(payload.get("generated_sql"), str) else None,
            str(payload.get("answer", "")),
            json.dumps(payload),
            payload.get("execution_latency_ms"),
            payload.get("tokens_used"),
            payload.get("model_used"),
            payload.get("flagged_pii", False),
            idempotency_hash,
            datetime.now(timezone.utc),
        )
    return str(turn_id)


async def update_feedback_columns(
    admin_pool: Any,
    turn_id: str,
    user_id: str,
    rating: str,
    comment: str | None,
) -> None:
    async with admin_pool.acquire() as connection:
        result = await connection.execute(
            """
            UPDATE user_turns
            SET feedback_rating = $1::feedback_rating,
                feedback_comment = $2,
                feedback_timestamp = $3
            WHERE id = $4 AND user_id = $5
            """,
            rating,
            comment,
            datetime.now(timezone.utc),
            turn_id,
            user_id,
        )
    if result == "UPDATE 0":
        raise LookupError("Conversation turn was not found.")
    async with admin_pool.acquire() as connection:
        await connection.execute(
            """
            INSERT INTO feedback_audit (turn_id, user_id, rating, comment)
            VALUES ($1, $2, $3::feedback_rating, $4)
            """,
            turn_id,
            user_id,
            rating,
            comment,
        )


async def increment_monthly_usage(admin_pool: Any, user_id: str, usage_month: datetime) -> int:
    async with admin_pool.acquire() as connection:
        count = await connection.fetchval(
            """
            INSERT INTO monthly_usage (user_id, usage_month, query_count, updated_at)
            VALUES ($1, $2::date, 1, $3)
            ON CONFLICT (user_id, usage_month) DO UPDATE SET
                query_count = monthly_usage.query_count + 1,
                updated_at = EXCLUDED.updated_at
            RETURNING query_count
            """,
            user_id,
            usage_month.strftime("%Y-%m-01"),
            datetime.now(timezone.utc),
        )
    return int(count)
