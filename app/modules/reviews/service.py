from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import json
from typing import Any

from fastapi import HTTPException, status

from app.modules.reviews.repository import (
    fetch_event_reviews,
    fetch_interactions_summary,
    get_event_by_id,
    soft_delete_review,
    toggle_reaction,
    upsert_review,
)
from app.modules.reviews.schemas import (
    EventInteractionsResponse,
    ReactionToggleResponse,
    ReactionType,
    ReviewListResponse,
    ReviewResponse,
    ReviewUpsertRequest,
)

try:
    from zoneinfo import ZoneInfo
    CENTRAL_TZ = ZoneInfo("America/Chicago")
except Exception:
    CENTRAL_TZ = timezone(timedelta(hours=-5))
CACHE_TTL = 300  # 5 minutes


def get_today_central() -> date:
    return datetime.now(CENTRAL_TZ).date()


def parse_event_date(date_val: str | date) -> date:
    if isinstance(date_val, date):
        return date_val
    return date.fromisoformat(str(date_val)[:10])


class ReviewsService:
    def __init__(self, admin_pool: Any, redis: Any | None = None):
        self.admin_pool = admin_pool
        self.redis = redis

    async def _invalidate_cache(self, event_id: str) -> None:
        if self.redis is not None:
            try:
                await self.redis.delete(f"cache:event_interactions:{event_id}")
            except Exception:
                pass

    async def get_interactions(
        self,
        event_id: str,
        user_id: str | None = None,
    ) -> EventInteractionsResponse:
        cache_key = f"cache:event_interactions:{event_id}"

        # If anonymous viewer and Redis is available, check cache
        if user_id is None and self.redis is not None:
            try:
                cached = await self.redis.get(cache_key)
                if cached:
                    data = json.loads(cached)
                    return EventInteractionsResponse(**data)
            except Exception:
                pass

        summary = await fetch_interactions_summary(self.admin_pool, event_id, user_id)
        if summary is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Event not found.",
            )

        response = EventInteractionsResponse(
            event_id=summary["event_id"],
            review_count=summary["review_count"],
            average_rating=summary["average_rating"],
            attended_count=summary["attended_count"],
            reaction_counts=summary["reaction_counts"],
            user_reaction=summary["user_reaction"],
            user_review=ReviewResponse(**summary["user_review"]) if summary["user_review"] else None,
        )

        # Cache anonymous summary
        if user_id is None and self.redis is not None:
            try:
                await self.redis.set(
                    cache_key,
                    json.dumps(response.model_dump()),
                    ex=CACHE_TTL,
                )
            except Exception:
                pass

        return response

    async def get_reviews(
        self,
        event_id: str,
        user_id: str | None = None,
        sort: str = "rating_desc",
        star_filter: int | None = None,
        limit: int = 5,
        offset: int = 0,
    ) -> ReviewListResponse:
        data = await fetch_event_reviews(
            self.admin_pool,
            event_id,
            user_id=user_id,
            sort=sort,
            star_filter=star_filter,
            limit=limit,
            offset=offset,
        )
        return ReviewListResponse(
            event_id=data["event_id"],
            total_reviews=data["total_reviews"],
            average_rating=data["average_rating"],
            star_distribution=data["star_distribution"],
            reviews=[ReviewResponse(**r) for r in data["reviews"]],
            user_review=ReviewResponse(**data["user_review"]) if data["user_review"] else None,
        )

    async def post_review(
        self,
        event_id: str,
        user_id: str,
        payload: ReviewUpsertRequest,
    ) -> ReviewResponse:
        pool = self.admin_pool
        event = await get_event_by_id(pool, event_id)
        if not event:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Event not found.",
            )

        # Timeline check: cannot review future events
        event_day = parse_event_date(event["event_date"])
        today = get_today_central()
        if event_day > today:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Reviews and attendance unlock once this event occurs on {event_day.isoformat()}.",
            )

        review = await upsert_review(
            pool,
            event_id=event_id,
            user_id=user_id,
            rating=payload.rating,
            comment=payload.comment,
            attended_event=payload.attended_event,
            is_anonymous=payload.is_anonymous,
        )

        await self._invalidate_cache(event_id)
        return ReviewResponse(**review)

    async def delete_review(
        self,
        event_id: str,
        user_id: str,
        is_admin: bool = False,
    ) -> dict[str, str]:
        pool = self.admin_pool
        success = await soft_delete_review(pool, event_id, user_id, is_admin=is_admin)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Review not found or you are not authorized to delete it.",
            )

        await self._invalidate_cache(event_id)
        return {"status": "review_deleted"}

    async def toggle_event_reaction(
        self,
        event_id: str,
        user_id: str,
        reaction_type: ReactionType,
    ) -> ReactionToggleResponse:
        pool = self.admin_pool
        event = await get_event_by_id(pool, event_id)
        if not event:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Event not found.",
            )

        # Timeline check: 'going' is disabled for past events
        event_day = parse_event_date(event["event_date"])
        today = get_today_central()
        if reaction_type == "going" and event_day < today:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The 'Planning to go' reaction is only available for upcoming events.",
            )

        active_reaction, counts, toggled_off = await toggle_reaction(
            pool,
            event_id=event_id,
            user_id=user_id,
            reaction_type=reaction_type,
        )

        await self._invalidate_cache(event_id)
        return ReactionToggleResponse(
            event_id=event_id,
            reaction_type=active_reaction,
            reaction_counts=counts,
            toggled_off=toggled_off,
        )
