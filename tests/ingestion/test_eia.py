import httpx
import pytest

from ingestion import eia
from ingestion.config import settings


def _row(period="2026-04", value="216770"):
    return {
        "period": period,
        "duoarea": "NUS-Z00",
        "area-name": "U.S.",
        "product": "EPG0",
        "product-name": "Natural Gas",
        "process": "IM0",
        "process-name": "Imports",
        "series": "N9100US2",
        "series-description": "U.S. Natural Gas Imports (MMcf)",
        "value": value,
        "units": "MMCF",
    }


def _page(rows, total):
    return {"response": {"total": str(total), "data": rows}, "warnings": []}


def _patch_transport(monkeypatch, handler):
    real_client = httpx.Client
    monkeypatch.setattr(httpx, "Client", lambda **kw: real_client(transport=httpx.MockTransport(handler), **kw))


def test_fetch_natural_gas_imports_single_page(monkeypatch):
    def handler(request):
        return httpx.Response(200, json=_page([_row(), _row(period="2026-03")], total=2))

    _patch_transport(monkeypatch, handler)
    records = eia.fetch_natural_gas_imports(api_key="k")
    assert len(records) == 2
    assert records[0].value == 216770.0
    assert records[0].area_name == "U.S."


def test_fetch_natural_gas_imports_paginates(monkeypatch):
    calls = []

    def handler(request):
        offset = int(dict(request.url.params).get("offset", 0))
        calls.append(offset)
        row = _row(period="2026-04" if offset == 0 else "2026-03")
        return httpx.Response(200, json=_page([row], total=2))

    monkeypatch.setattr(settings, "eia_page_size", 1)
    _patch_transport(monkeypatch, handler)
    records = eia.fetch_natural_gas_imports(api_key="k")
    assert calls == [0, 1]
    assert len(records) == 2


def test_fetch_natural_gas_imports_retries_on_500_then_succeeds(monkeypatch):
    attempts = {"count": 0}

    def handler(request):
        attempts["count"] += 1
        if attempts["count"] == 1:
            return httpx.Response(500, text="server error")
        return httpx.Response(200, json=_page([_row()], total=1))

    _patch_transport(monkeypatch, handler)
    records = eia.fetch_natural_gas_imports(api_key="k")
    assert attempts["count"] == 2
    assert len(records) == 1


def test_fetch_natural_gas_imports_raises_on_bad_request(monkeypatch):
    def handler(request):
        return httpx.Response(400, text="bad request")

    _patch_transport(monkeypatch, handler)
    with pytest.raises(httpx.HTTPStatusError):
        eia.fetch_natural_gas_imports(api_key="k")


def test_fetch_natural_gas_imports_requires_api_key(monkeypatch):
    monkeypatch.setattr(settings, "eia_api_key", "")
    with pytest.raises(RuntimeError):
        eia.fetch_natural_gas_imports(api_key=None)
