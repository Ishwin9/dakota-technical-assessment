import httpx
import pytest

from ingestion import enrichment


def _patch_transport(monkeypatch, handler):
    real_client = httpx.Client
    monkeypatch.setattr(httpx, "Client", lambda **kw: real_client(transport=httpx.MockTransport(handler), **kw))


def test_fetch_regions(monkeypatch):
    def handler(request):
        assert request.url.path == "/regions"
        return httpx.Response(200, json=[{"code": "CISO", "name": "California ISO"}])

    _patch_transport(monkeypatch, handler)
    assert enrichment.fetch_regions() == [{"code": "CISO", "name": "California ISO"}]


def test_fetch_current_weather_for_region(monkeypatch):
    def handler(request):
        assert request.url.path == "/weather/CISO"
        return httpx.Response(200, json={"region_code": "CISO", "temperature_f": 70.0})

    _patch_transport(monkeypatch, handler)
    body = enrichment.fetch_current_weather("CISO")
    assert body["region_code"] == "CISO"


def test_fetch_weather_history_passes_hours_param(monkeypatch):
    def handler(request):
        assert request.url.path == "/weather/ERCO/history"
        assert dict(request.url.params)["hours"] == "48"
        return httpx.Response(200, json=[])

    _patch_transport(monkeypatch, handler)
    enrichment.fetch_weather_history("ERCO", hours=48)


def test_fetch_grid_events_unknown_region_raises(monkeypatch):
    def handler(request):
        return httpx.Response(404, text="unknown region")

    _patch_transport(monkeypatch, handler)
    with pytest.raises(httpx.HTTPStatusError):
        enrichment.fetch_grid_events("NOPE")


def test_fetch_grid_events_retries_then_succeeds(monkeypatch):
    attempts = {"count": 0}

    def handler(request):
        attempts["count"] += 1
        if attempts["count"] == 1:
            return httpx.Response(503, text="unavailable")
        return httpx.Response(200, json=[{"event_id": "abc"}])

    _patch_transport(monkeypatch, handler)
    events = enrichment.fetch_grid_events(days=3)
    assert attempts["count"] == 2
    assert events == [{"event_id": "abc"}]
