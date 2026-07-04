import logging

import httpx

from . import _http
from .config import settings
from .models import NaturalGasImportRecord

logger = logging.getLogger("dakota.ingestion.eia")


def fetch_natural_gas_imports(
    start: str | None = None,
    end: str | None = None,
    frequency: str = "monthly",
    max_records: int | None = None,
    api_key: str | None = None,
) -> list[NaturalGasImportRecord]:
    api_key = api_key or settings.eia_api_key
    if not api_key:
        raise RuntimeError("EIA_API_KEY is not set")

    records: list[NaturalGasImportRecord] = []
    offset = 0

    with httpx.Client(base_url=settings.eia_base_url, timeout=settings.request_timeout_seconds) as client:
        while True:
            page_length = min(settings.eia_page_size, max_records - len(records)) if max_records else settings.eia_page_size
            params = {
                "api_key": api_key,
                "frequency": frequency,
                "data[0]": "value",
                "sort[0][column]": "period",
                "sort[0][direction]": "desc",
                "offset": offset,
                "length": page_length,
            }
            if start:
                params["start"] = start
            if end:
                params["end"] = end

            body = _http.get(client, "/natural-gas/move/impc/data/", params).json()
            for warning in body.get("warnings", []):
                logger.warning("EIA API warning: %s", warning.get("description", warning))

            response = body["response"]
            page = response["data"]
            records.extend(NaturalGasImportRecord.model_validate(row) for row in page)

            total = int(response["total"])
            offset += len(page)
            logger.info("fetched %d/%s natural gas import rows", offset, total)

            if not page or offset >= total:
                break
            if max_records and len(records) >= max_records:
                return records[:max_records]

    return records
