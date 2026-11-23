from datetime import datetime, timezone

from app.modules.chat.pipeline import DeterministicEventQueryPlanner


UTC_NOW = datetime(2026, 9, 11, 12, tzinfo=timezone.utc)


def test_kids_friendly_planner_uses_known_event_columns_and_date_parameters() -> None:
    planned = DeterministicEventQueryPlanner().plan("Show kids-friendly events", UTC_NOW)

    assert planned is not None
    query, parameters = planned
    assert "SELECT *" not in query
    assert "FROM public.events" in query
    assert "is_kids_friendly = TRUE" in query
    assert parameters == (
        datetime(2026, 9, 1, tzinfo=timezone.utc).date(),
        datetime(2026, 10, 1, tzinfo=timezone.utc).date(),
    )


def test_adult_friendly_planner_handles_year_boundary() -> None:
    planned = DeterministicEventQueryPlanner().plan("adult-friendly events", datetime(2026, 12, 15, tzinfo=timezone.utc))

    assert planned is not None
    _, parameters = planned
    assert parameters[0].isoformat() == "2026-12-01"
    assert parameters[1].isoformat() == "2027-01-01"