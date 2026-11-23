from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, Field

ReactionType = Literal["going", "love", "helpful"]


class ReactionToggleRequest(BaseModel):
    reaction_type: ReactionType


class ReactionToggleResponse(BaseModel):
    event_id: str
    reaction_type: ReactionType | None
    reaction_counts: dict[str, int]
    toggled_off: bool = False


class ReviewUpsertRequest(BaseModel):
    rating: int = Field(..., ge=1, le=5, description="1 to 5 star rating")
    comment: str | None = Field(default=None, max_length=3000, description="Optional text review up to 3000 chars")
    attended_event: bool = Field(default=False, description="Whether the resident attended the event")
    is_anonymous: bool = Field(default=False, description="Whether the review is posted anonymously to neighbors")


class ReviewResponse(BaseModel):
    id: str
    event_id: str
    rating: int
    comment: str | None = None
    attended_event: bool = False
    is_anonymous: bool = False
    is_author: bool = False
    author_name: str = "Neighbor"
    author_avatar: str | None = None
    created_at: str
    updated_at: str
    is_edited: bool = False


class ReviewListResponse(BaseModel):
    event_id: str
    total_reviews: int
    average_rating: float | None = None
    star_distribution: dict[str, int] = Field(default_factory=lambda: {"1": 0, "2": 0, "3": 0, "4": 0, "5": 0})
    reviews: list[ReviewResponse]
    user_review: ReviewResponse | None = None


class EventInteractionsResponse(BaseModel):
    event_id: str
    review_count: int = 0
    average_rating: float | None = None
    attended_count: int = 0
    reaction_counts: dict[str, int] = Field(default_factory=lambda: {"going": 0, "love": 0, "helpful": 0})
    user_reaction: str | None = None
    user_review: ReviewResponse | None = None
