from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any


def _parse_reaction_counts(val: Any) -> dict[str, int]:
    default_counts = {"going": 0, "love": 0, "helpful": 0}
    if not val:
        return default_counts
    if isinstance(val, str):
        try:
            val = json.loads(val)
        except Exception:
            return default_counts
    if isinstance(val, dict):
        return {
            "going": int(val.get("going", 0)),
            "love": int(val.get("love", 0)),
            "helpful": int(val.get("helpful", 0)),
        }
    return default_counts


async def get_event_by_id(pool: Any, event_id: str) -> dict[str, Any] | None:
    async with pool.acquire() as connection:
        row = await connection.fetchrow(
            """
            SELECT
                id::text,
                event_date,
                title,
                review_count,
                average_rating,
                attended_count,
                reaction_counts
            FROM events
            WHERE id = $1 AND is_deleted = FALSE
            """,
            event_id,
        )
        if not row:
            return None
        return {
            "id": row["id"],
            "event_date": str(row["event_date"]),
            "title": row["title"],
            "review_count": int(row["review_count"] or 0),
            "average_rating": float(row["average_rating"]) if row["average_rating"] is not None else None,
            "attended_count": int(row["attended_count"] or 0),
            "reaction_counts": _parse_reaction_counts(row["reaction_counts"]),
        }


async def fetch_interactions_summary(
    pool: Any,
    event_id: str,
    user_id: str | None = None,
) -> dict[str, Any] | None:
    event = await get_event_by_id(pool, event_id)
    if not event:
        return None

    user_reaction: str | None = None
    user_review: dict[str, Any] | None = None

    if user_id:
        async with pool.acquire() as connection:
            reaction_row = await connection.fetchrow(
                "SELECT reaction_type FROM event_reactions WHERE event_id = $1 AND user_id = $2",
                event_id,
                user_id,
            )
            if reaction_row:
                user_reaction = reaction_row["reaction_type"]

            review_row = await connection.fetchrow(
                """
                SELECT
                    id::text,
                    event_id::text,
                    rating,
                    comment,
                    attended_event,
                    is_anonymous,
                    created_at,
                    updated_at
                FROM event_reviews
                WHERE event_id = $1 AND user_id = $2 AND is_deleted = FALSE
                """,
                event_id,
                user_id,
            )
            if review_row:
                created_dt = review_row["created_at"]
                updated_dt = review_row["updated_at"]
                is_edited = (updated_dt - created_dt).total_seconds() > 2 if (created_dt and updated_dt) else False
                user_review = {
                    "id": review_row["id"],
                    "event_id": review_row["event_id"],
                    "rating": int(review_row["rating"]),
                    "comment": review_row["comment"],
                    "attended_event": bool(review_row["attended_event"]),
                    "is_anonymous": bool(review_row["is_anonymous"]),
                    "is_author": True,
                    "author_name": "You" + (" (Anonymous to neighbors)" if review_row["is_anonymous"] else ""),
                    "author_avatar": None,
                    "created_at": review_row["created_at"].isoformat() if review_row["created_at"] else "",
                    "updated_at": review_row["updated_at"].isoformat() if review_row["updated_at"] else "",
                    "is_edited": is_edited,
                }

    return {
        "event_id": event_id,
        "review_count": event["review_count"],
        "average_rating": event["average_rating"],
        "attended_count": event["attended_count"],
        "reaction_counts": event["reaction_counts"],
        "user_reaction": user_reaction,
        "user_review": user_review,
    }


async def fetch_event_reviews(
    pool: Any,
    event_id: str,
    user_id: str | None = None,
    sort: str = "rating_desc",
    star_filter: int | None = None,
    limit: int = 5,
    offset: int = 0,
) -> dict[str, Any]:
    async with pool.acquire() as connection:
        # 1. Total and star distribution
        dist_rows = await connection.fetch(
            """
            SELECT rating, COUNT(*)::int as count
            FROM event_reviews
            WHERE event_id = $1 AND is_deleted = FALSE
            GROUP BY rating
            """,
            event_id,
        )
        star_distribution = {"1": 0, "2": 0, "3": 0, "4": 0, "5": 0}
        total_reviews = 0
        total_rating_sum = 0
        for r in dist_rows:
            rating_key = str(r["rating"])
            count = int(r["count"])
            if rating_key in star_distribution:
                star_distribution[rating_key] = count
            total_reviews += count
            total_rating_sum += int(r["rating"]) * count

        average_rating = round(total_rating_sum / total_reviews, 2) if total_reviews > 0 else None

        # 2. Build query for paginated reviews
        order_clause = "r.rating DESC, r.created_at DESC"
        if sort == "recent":
            order_clause = "r.created_at DESC"
        elif sort == "recent_attendees_first":
            order_clause = "r.attended_event DESC, r.created_at DESC"

        query_conditions = ["r.event_id = $1", "r.is_deleted = FALSE"]
        query_params: list[Any] = [event_id]

        if star_filter and 1 <= star_filter <= 5:
            query_params.append(star_filter)
            query_conditions.append(f"r.rating = ${len(query_params)}")

        query_params.append(limit)
        limit_placeholder = f"${len(query_params)}"
        query_params.append(offset)
        offset_placeholder = f"${len(query_params)}"

        sql = f"""
            SELECT
                r.id::text,
                r.event_id::text,
                r.user_id::text,
                r.rating,
                r.comment,
                r.attended_event,
                r.is_anonymous,
                r.created_at,
                r.updated_at,
                COALESCE(u.email, '') as user_email
            FROM event_reviews r
            LEFT JOIN users u ON u.id = r.user_id
            WHERE {' AND '.join(query_conditions)}
            ORDER BY {order_clause}
            LIMIT {limit_placeholder} OFFSET {offset_placeholder}
        """

        rows = await connection.fetch(sql, *query_params)

        reviews: list[dict[str, Any]] = []
        user_review: dict[str, Any] | None = None

        for row in rows:
            review_user_id = row["user_id"]
            is_author = bool(user_id and user_id == review_user_id)
            is_anon = bool(row["is_anonymous"])
            created_dt = row["created_at"]
            updated_dt = row["updated_at"]
            is_edited = (updated_dt - created_dt).total_seconds() > 2 if (created_dt and updated_dt) else False

            # Server-side anonymity masking
            if is_anon:
                if is_author:
                    author_name = "You (Anonymous to neighbors)"
                    author_avatar = None
                else:
                    author_name = "Neighbor"
                    author_avatar = None
            else:
                if is_author:
                    author_name = "You"
                    author_avatar = None
                else:
                    email = row["user_email"] or ""
                    if email and "@" in email:
                        prefix = email.split("@")[0]
                        author_name = prefix.capitalize()
                    else:
                        author_name = "Neighbor"
                    author_avatar = None

            item = {
                "id": row["id"],
                "event_id": row["event_id"],
                "rating": int(row["rating"]),
                "comment": row["comment"],
                "attended_event": bool(row["attended_event"]),
                "is_anonymous": is_anon,
                "is_author": is_author,
                "author_name": author_name,
                "author_avatar": author_avatar,
                "created_at": row["created_at"].isoformat() if row["created_at"] else "",
                "updated_at": row["updated_at"].isoformat() if row["updated_at"] else "",
                "is_edited": is_edited,
            }
            reviews.append(item)
            if is_author and user_review is None:
                user_review = item

        # If user has a review that wasn't in this page/filter, query it specifically if user_id is provided
        if user_id and not user_review and offset == 0:
            user_row = await connection.fetchrow(
                """
                SELECT
                    id::text, event_id::text, rating, comment, attended_event,
                    is_anonymous, created_at, updated_at
                FROM event_reviews
                WHERE event_id = $1 AND user_id = $2 AND is_deleted = FALSE
                """,
                event_id,
                user_id,
            )
            if user_row:
                created_dt = user_row["created_at"]
                updated_dt = user_row["updated_at"]
                is_edited = (updated_dt - created_dt).total_seconds() > 2 if (created_dt and updated_dt) else False
                user_review = {
                    "id": user_row["id"],
                    "event_id": user_row["event_id"],
                    "rating": int(user_row["rating"]),
                    "comment": user_row["comment"],
                    "attended_event": bool(user_row["attended_event"]),
                    "is_anonymous": bool(user_row["is_anonymous"]),
                    "is_author": True,
                    "author_name": "You" + (" (Anonymous to neighbors)" if user_row["is_anonymous"] else ""),
                    "author_avatar": None,
                    "created_at": user_row["created_at"].isoformat() if user_row["created_at"] else "",
                    "updated_at": user_row["updated_at"].isoformat() if user_row["updated_at"] else "",
                    "is_edited": is_edited,
                }

        return {
            "event_id": event_id,
            "total_reviews": total_reviews,
            "average_rating": average_rating,
            "star_distribution": star_distribution,
            "reviews": reviews,
            "user_review": user_review,
        }


async def upsert_review(
    pool: Any,
    event_id: str,
    user_id: str,
    rating: int,
    comment: str | None,
    attended_event: bool,
    is_anonymous: bool,
) -> dict[str, Any]:
    async with pool.acquire() as connection:
        # Check if an active review exists
        existing_id = await connection.fetchval(
            "SELECT id::text FROM event_reviews WHERE event_id = $1 AND user_id = $2 AND is_deleted = FALSE",
            event_id,
            user_id,
        )
        if existing_id:
            row = await connection.fetchrow(
                """
                UPDATE event_reviews
                SET
                    rating = $1,
                    comment = $2,
                    attended_event = $3,
                    is_anonymous = $4,
                    updated_at = timezone('utc'::text, now())
                WHERE id = $5
                RETURNING id::text, event_id::text, rating, comment, attended_event, is_anonymous, created_at, updated_at
                """,
                rating,
                comment,
                attended_event,
                is_anonymous,
                existing_id,
            )
        else:
            row = await connection.fetchrow(
                """
                INSERT INTO event_reviews (
                    event_id, user_id, rating, comment, attended_event, is_anonymous
                ) VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING id::text, event_id::text, rating, comment, attended_event, is_anonymous, created_at, updated_at
                """,
                event_id,
                user_id,
                rating,
                comment,
                attended_event,
                is_anonymous,
            )

        created_dt = row["created_at"]
        updated_dt = row["updated_at"]
        is_edited = (updated_dt - created_dt).total_seconds() > 2 if (created_dt and updated_dt) else False

        return {
            "id": row["id"],
            "event_id": row["event_id"],
            "rating": int(row["rating"]),
            "comment": row["comment"],
            "attended_event": bool(row["attended_event"]),
            "is_anonymous": bool(row["is_anonymous"]),
            "is_author": True,
            "author_name": "You" + (" (Anonymous to neighbors)" if row["is_anonymous"] else ""),
            "author_avatar": None,
            "created_at": row["created_at"].isoformat() if row["created_at"] else "",
            "updated_at": row["updated_at"].isoformat() if row["updated_at"] else "",
            "is_edited": is_edited,
        }


async def soft_delete_review(
    pool: Any,
    event_id: str,
    user_id: str,
    is_admin: bool = False,
) -> bool:
    async with pool.acquire() as connection:
        if is_admin:
            deleted_id = await connection.fetchval(
                """
                UPDATE event_reviews
                SET
                    is_deleted = TRUE,
                    deleted_at = timezone('utc'::text, now()),
                    updated_at = timezone('utc'::text, now())
                WHERE event_id = $1 AND is_deleted = FALSE
                RETURNING id::text
                """,
                event_id,
            )
        else:
            deleted_id = await connection.fetchval(
                """
                UPDATE event_reviews
                SET
                    is_deleted = TRUE,
                    deleted_at = timezone('utc'::text, now()),
                    updated_at = timezone('utc'::text, now())
                WHERE event_id = $1 AND user_id = $2 AND is_deleted = FALSE
                RETURNING id::text
                """,
                event_id,
                user_id,
            )
        return deleted_id is not None


async def toggle_reaction(
    pool: Any,
    event_id: str,
    user_id: str,
    reaction_type: str,
) -> tuple[str | None, dict[str, int], bool]:
    async with pool.acquire() as connection:
        existing = await connection.fetchval(
            "SELECT reaction_type FROM event_reactions WHERE event_id = $1 AND user_id = $2",
            event_id,
            user_id,
        )

        if existing == reaction_type:
            # Toggle off
            await connection.execute(
                "DELETE FROM event_reactions WHERE event_id = $1 AND user_id = $2",
                event_id,
                user_id,
            )
            # Fetch latest counts from event
            counts_val = await connection.fetchval(
                "SELECT reaction_counts FROM events WHERE id = $1",
                event_id,
            )
            return None, _parse_reaction_counts(counts_val), True

        # Insert or update to new reaction
        await connection.execute(
            """
            INSERT INTO event_reactions (event_id, user_id, reaction_type)
            VALUES ($1, $2, $3)
            ON CONFLICT (event_id, user_id)
            DO UPDATE SET reaction_type = EXCLUDED.reaction_type, created_at = timezone('utc'::text, now())
            """,
            event_id,
            user_id,
            reaction_type,
        )
        counts_val = await connection.fetchval(
            "SELECT reaction_counts FROM events WHERE id = $1",
            event_id,
        )
        return reaction_type, _parse_reaction_counts(counts_val), False
