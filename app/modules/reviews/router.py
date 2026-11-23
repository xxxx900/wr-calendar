from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.core.auth import get_current_user, get_optional_current_user
from app.modules.chat.service import AuthenticatedUser
from app.modules.reviews.schemas import (
    EventInteractionsResponse,
    ReactionToggleRequest,
    ReactionToggleResponse,
    ReviewListResponse,
    ReviewResponse,
    ReviewUpsertRequest,
)
from app.modules.reviews.service import ReviewsService

router = APIRouter(prefix="/api/v1/events", tags=["reviews"])


def get_reviews_service(request: Request) -> ReviewsService:
    pools = getattr(request.app.state, "pools", None)
    redis = getattr(request.app.state, "redis", None)
    if pools is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database pools unavailable.",
        )
    return ReviewsService(
        admin_pool=pools.admin,
        redis=redis,
    )


@router.get("/{event_id}/interactions", response_model=EventInteractionsResponse)
async def get_event_interactions(
    event_id: str,
    user: AuthenticatedUser | None = Depends(get_optional_current_user),
    service: ReviewsService = Depends(get_reviews_service),
) -> EventInteractionsResponse:
    user_id = user.id if user else None
    return await service.get_interactions(event_id, user_id=user_id)


@router.get("/{event_id}/reviews", response_model=ReviewListResponse)
async def get_event_reviews(
    event_id: str,
    sort: Literal["rating_desc", "recent", "recent_attendees_first"] = Query("rating_desc"),
    star_filter: int | None = Query(None, ge=1, le=5),
    limit: int = Query(5, ge=1, le=50),
    offset: int = Query(0, ge=0),
    user: AuthenticatedUser | None = Depends(get_optional_current_user),
    service: ReviewsService = Depends(get_reviews_service),
) -> ReviewListResponse:
    user_id = user.id if user else None
    return await service.get_reviews(
        event_id,
        user_id=user_id,
        sort=sort,
        star_filter=star_filter,
        limit=limit,
        offset=offset,
    )


@router.post("/{event_id}/reviews", response_model=ReviewResponse)
async def post_event_review(
    event_id: str,
    payload: ReviewUpsertRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    service: ReviewsService = Depends(get_reviews_service),
) -> ReviewResponse:
    return await service.post_review(event_id, user_id=user.id, payload=payload)


@router.delete("/{event_id}/reviews")
async def delete_event_review(
    event_id: str,
    user: AuthenticatedUser = Depends(get_current_user),
    service: ReviewsService = Depends(get_reviews_service),
) -> dict[str, str]:
    is_admin = user.role in {"admin", "calendar_admin"}
    return await service.delete_review(event_id, user_id=user.id, is_admin=is_admin)


@router.post("/{event_id}/reactions", response_model=ReactionToggleResponse)
async def toggle_event_reaction(
    event_id: str,
    payload: ReactionToggleRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    service: ReviewsService = Depends(get_reviews_service),
) -> ReactionToggleResponse:
    return await service.toggle_event_reaction(
        event_id,
        user_id=user.id,
        reaction_type=payload.reaction_type,
    )
