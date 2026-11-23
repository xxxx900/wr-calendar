from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from typing import Any


async def upsert_events(admin_pool: Any, events: list[dict[str, Any]]) -> dict[str, int]:
    inserted = 0
    updated = 0
    async with admin_pool.acquire() as connection:
        for event in events:
            raw_date = event["event_date"]
            event_date_val = date.fromisoformat(raw_date[:10]) if isinstance(raw_date, str) else raw_date
            
            raw_start = event.get("start_time_utc")
            start_time_val = (
                datetime.fromisoformat(raw_start.replace("Z", "+00:00"))
                if isinstance(raw_start, str) and raw_start
                else raw_start
            )
            
            raw_end = event.get("end_time_utc")
            end_time_val = (
                datetime.fromisoformat(raw_end.replace("Z", "+00:00"))
                if isinstance(raw_end, str) and raw_end
                else raw_end
            )

            result = await connection.execute(
                """
                INSERT INTO events (
                    community_id, event_date, day_of_week, start_time_utc, end_time_utc,
                    is_all_day, title, description, location, host_type, fee_required,
                    rsvp_required, audience_tag, is_kids_friendly, is_adult_friendly,
                    notes, created_at, updated_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $17)
                ON CONFLICT (community_id, event_date, title, COALESCE(start_time_utc, TIMESTAMPTZ '1970-01-01 00:00:00+00'))
                DO UPDATE SET
                    day_of_week = EXCLUDED.day_of_week,
                    end_time_utc = EXCLUDED.end_time_utc,
                    is_all_day = EXCLUDED.is_all_day,
                    description = EXCLUDED.description,
                    location = EXCLUDED.location,
                    host_type = EXCLUDED.host_type,
                    fee_required = EXCLUDED.fee_required,
                    rsvp_required = EXCLUDED.rsvp_required,
                    audience_tag = EXCLUDED.audience_tag,
                    is_kids_friendly = EXCLUDED.is_kids_friendly,
                    is_adult_friendly = EXCLUDED.is_adult_friendly,
                    notes = EXCLUDED.notes,
                    updated_at = EXCLUDED.updated_at
                """,
                event.get("community_id", "wolf_ranch"),
                event_date_val,
                event.get("day_of_week", ""),
                start_time_val,
                end_time_val,
                event.get("is_all_day", False),
                event["title"],
                event.get("description", ""),
                event.get("location", ""),
                event.get("host_type", "community"),
                event.get("fee_required", False),
                event.get("rsvp_required", False),
                event.get("audience_tag", "unspecified"),
                event.get("is_kids_friendly", False),
                event.get("is_adult_friendly", False),
                event.get("notes", ""),
                datetime.now(timezone.utc),
            )
            if result.startswith("INSERT"):
                inserted += 1
            else:
                updated += 1
    return {"inserted": inserted, "updated": updated}


async def fetch_current_month_events(
    readonly_pool: Any,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    current_date = (now or datetime.now(timezone.utc)).date()
    return await fetch_month_events(readonly_pool, current_date.replace(day=1))


async def fetch_month_events(readonly_pool: Any, month_start: date) -> list[dict[str, Any]]:
    month_start = month_start.replace(day=1)
    next_month = (month_start + timedelta(days=32)).replace(day=1)

    async with readonly_pool.acquire() as connection:
        rows = await connection.fetch(
            """
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
                popularity_score,
                review_count,
                average_rating,
                reaction_counts
            FROM events
            WHERE event_date >= $1
              AND event_date < $2
              AND is_deleted = FALSE
            ORDER BY event_date, start_time_utc NULLS FIRST, title
            """,
            month_start,
            next_month,
        )
    results = []
    for row in rows:
        d = dict(row)
        if d.get("average_rating") is not None:
            try:
                d["average_rating"] = float(d["average_rating"])
            except Exception:
                d["average_rating"] = None
        else:
            d["average_rating"] = None

        rc = d.get("reaction_counts")
        if isinstance(rc, str):
            try:
                d["reaction_counts"] = json.loads(rc)
            except Exception:
                d["reaction_counts"] = {"going": 0, "love": 0, "helpful": 0}
        elif not rc:
            d["reaction_counts"] = {"going": 0, "love": 0, "helpful": 0}
        results.append(d)
    return results
