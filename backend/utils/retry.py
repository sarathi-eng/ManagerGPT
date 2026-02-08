"""Retry helper with exponential backoff for rate-limited API calls."""
from __future__ import annotations

import asyncio
import logging
from typing import TypeVar, Callable, Any

import httpx

logger = logging.getLogger(__name__)

T = TypeVar("T")

MAX_RETRIES = 3
INITIAL_DELAY = 2.0  # seconds
BACKOFF_FACTOR = 2.0


async def post_with_retry(
    url: str,
    *,
    headers: dict[str, str],
    json_body: dict[str, Any],
    timeout: float = 30.0,
    max_retries: int = MAX_RETRIES,
) -> dict[str, Any]:
    """POST to an API with exponential backoff on 429 / 5xx errors.

    Returns the parsed JSON response on success.
    Raises httpx.HTTPStatusError on permanent failure.
    """
    delay = INITIAL_DELAY
    last_exc: Exception | None = None

    for attempt in range(max_retries + 1):
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(url, headers=headers, json=json_body)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            last_exc = exc
            if status == 429 or status >= 500:
                if attempt < max_retries:
                    # Try to read Retry-After header
                    retry_after = exc.response.headers.get("Retry-After")
                    wait = float(retry_after) if retry_after and retry_after.isdigit() else delay
                    logger.warning(
                        "API %s returned %s, retrying in %.1fs (attempt %d/%d)",
                        url, status, wait, attempt + 1, max_retries,
                    )
                    await asyncio.sleep(wait)
                    delay *= BACKOFF_FACTOR
                    continue
            raise
        except (httpx.ConnectError, httpx.ReadTimeout) as exc:
            last_exc = exc
            if attempt < max_retries:
                logger.warning(
                    "API connection error, retrying in %.1fs (attempt %d/%d)",
                    delay, attempt + 1, max_retries,
                )
                await asyncio.sleep(delay)
                delay *= BACKOFF_FACTOR
                continue
            raise

    # Should not reach here, but just in case
    raise last_exc  # type: ignore[misc]
