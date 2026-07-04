from datetime import date, datetime, timezone

from app.generators import generate_events_for_day, generate_weather, generate_weather_history
from app.regions import REGIONS

CISO = REGIONS["CISO"]


def test_generate_weather_is_pure_function_of_hour():
    at = datetime(2026, 7, 4, 14, 22, tzinfo=timezone.utc)
    a = generate_weather(CISO, at)
    b = generate_weather(CISO, at.replace(minute=59, second=59))
    assert a == b


def test_generate_weather_differs_across_regions():
    at = datetime(2026, 7, 4, 14, 0, tzinfo=timezone.utc)
    ciso = generate_weather(REGIONS["CISO"], at)
    swpp = generate_weather(REGIONS["SWPP"], at)
    assert ciso.region_code != swpp.region_code


def test_generate_weather_history_covers_requested_hours_in_order():
    at = datetime(2026, 3, 1, 5, 0, tzinfo=timezone.utc)
    history = generate_weather_history(CISO, at, hours=5)
    assert len(history) == 5
    assert history[-1].observation_time == at
    for earlier, later in zip(history, history[1:]):
        assert earlier.observation_time < later.observation_time


def test_generate_events_for_day_is_deterministic():
    day = date(2026, 6, 1)
    first = generate_events_for_day(CISO, day)
    second = generate_events_for_day(CISO, day)
    assert first == second


def test_generate_events_use_valid_region_code():
    day = date(2026, 6, 1)
    for event in generate_events_for_day(CISO, day):
        assert event.region_code == "CISO"
        assert event.affected_capacity_mw >= 0
        assert event.estimated_duration_minutes >= 0
