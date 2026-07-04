from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.main import app
from app.regions import REGIONS

client = TestClient(app)


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "timestamp" in body


def test_list_regions_matches_region_table():
    resp = client.get("/regions")
    assert resp.status_code == 200
    codes = {r["code"] for r in resp.json()}
    assert codes == set(REGIONS.keys())


def test_current_weather_known_region():
    resp = client.get("/weather/CISO")
    assert resp.status_code == 200
    body = resp.json()
    assert body["region_code"] == "CISO"
    assert -50 <= body["temperature_f"] <= 150
    assert 0 <= body["humidity_pct"] <= 100


def test_current_weather_unknown_region_returns_404():
    resp = client.get("/weather/NOPE")
    assert resp.status_code == 404


def test_weather_is_deterministic_within_the_same_hour():
    as_of = "2026-01-15T10:30:00Z"
    first = client.get("/weather/ERCO", params={"as_of": as_of}).json()
    second = client.get("/weather/ERCO", params={"as_of": as_of}).json()
    assert first == second


def test_weather_history_length_and_ordering():
    resp = client.get("/weather/PJM/history", params={"hours": 6})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 6
    timestamps = [datetime.fromisoformat(o["observation_time"]) for o in body]
    assert timestamps == sorted(timestamps)


def test_weather_history_rejects_out_of_range_hours():
    resp = client.get("/weather/PJM/history", params={"hours": 0})
    assert resp.status_code == 422


def test_grid_events_deterministic_and_scoped_to_region():
    as_of = "2026-02-01T00:00:00Z"
    first = client.get("/grid-events/MISO", params={"days": 14, "as_of": as_of}).json()
    second = client.get("/grid-events/MISO", params={"days": 14, "as_of": as_of}).json()
    assert first == second
    assert all(e["region_code"] == "MISO" for e in first)


def test_grid_events_all_regions_are_sorted_by_time():
    resp = client.get("/grid-events", params={"days": 7})
    assert resp.status_code == 200
    body = resp.json()
    timestamps = [datetime.fromisoformat(e["event_time"]) for e in body]
    assert timestamps == sorted(timestamps)


def test_weather_all_regions_returns_one_per_region():
    resp = client.get("/weather")
    assert resp.status_code == 200
    assert len(resp.json()) == len(REGIONS)
