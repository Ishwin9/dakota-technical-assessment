import logging

import httpx
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential_jitter

logger = logging.getLogger("dakota.ingestion")

_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, httpx.TransportError):
        return True
    return isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code in _RETRYABLE_STATUS_CODES


@retry(
    retry=retry_if_exception(_is_retryable),
    stop=stop_after_attempt(5),
    wait=wait_exponential_jitter(initial=1, max=30),
    reraise=True,
)
def get(client: httpx.Client, path: str, params: dict | None = None) -> httpx.Response:
    safe_params = {k: ("***" if k == "api_key" else v) for k, v in (params or {}).items()}
    logger.info("GET %s params=%s", path, safe_params)
    resp = client.get(path, params=params)
    resp.raise_for_status()
    return resp
