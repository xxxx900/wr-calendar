from app.modules.chat.openai_provider import EVENTS_SQL_SYSTEM_PROMPT


def test_sql_prompt_matches_events_schema_and_rejects_invented_columns() -> None:
    required_columns = {
        "id",
        "community_id",
        "event_date",
        "day_of_week",
        "start_time_utc",
        "end_time_utc",
        "is_all_day",
        "title",
        "description",
        "location",
        "host_type",
        "fee_required",
        "rsvp_required",
        "audience_tag",
        "is_kids_friendly",
        "is_adult_friendly",
        "notes",
        "is_deleted",
        "created_by",
        "capacity",
        "registered_count",
        "attended_count",
        "popularity_score",
        "created_at",
        "updated_at",
    }

    assert all(f"- {column} " in EVENTS_SQL_SYSTEM_PROMPT for column in required_columns)
    assert "There is no age_restriction column" in EVENTS_SQL_SYSTEM_PROMPT
    assert "current UTC month and current UTC year" in EVENTS_SQL_SYSTEM_PROMPT
    assert "July 2025" in EVENTS_SQL_SYSTEM_PROMPT
    assert "first day of the following month exclusive" in EVENTS_SQL_SYSTEM_PROMPT
    assert "Always add WHERE is_deleted = FALSE" in EVENTS_SQL_SYSTEM_PROMPT
    assert "information_schema" in EVENTS_SQL_SYSTEM_PROMPT
