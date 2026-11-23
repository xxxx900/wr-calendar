from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, Field

HostType = Literal["hoa_event", "food_truck", "paid_fitness", "homeowner_hosted", "hoa_announcement", "community"]
AudienceTag = Literal["kids_friendly", "adult_friendly", "all_ages", "unspecified"]


class CalendarEventSchema(BaseModel):
    id: str | None = None
    community_id: str = "wolf_ranch"
    event_date: str
    day_of_week: str = ""
    start_time_utc: str | None = None
    end_time_utc: str | None = None
    is_all_day: bool = False
    title: str = Field(min_length=1)
    description: str = ""
    location: str = ""
    host_type: HostType = "community"
    fee_required: bool = False
    rsvp_required: bool = False
    audience_tag: AudienceTag = "unspecified"
    is_kids_friendly: bool = False
    is_adult_friendly: bool = False
    notes: str = ""
    review_count: int = 0
    average_rating: float | None = None
    attended_count: int = 0
    reaction_counts: dict[str, int] = Field(default_factory=lambda: {"going": 0, "love": 0, "helpful": 0})


class ExtractionResponse(BaseModel):
    events: list[CalendarEventSchema]
    count: int


class BatchUpsertRequest(BaseModel):
    events: list[CalendarEventSchema] = Field(min_length=1)


class BatchUpsertResponse(BaseModel):
    inserted: int
    updated: int
