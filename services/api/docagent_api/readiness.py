"""Readiness checks for the services the API depends on."""

import httpx

READINESS_TIMEOUT_SECONDS = 2.0


async def is_qdrant_ready(url: str, client: httpx.AsyncClient | None = None) -> bool:
    """Return True if Qdrant's /readyz endpoint answers with a 2xx status.

    Never raises: connection errors, timeouts and non-2xx responses all count
    as "not ready", so a failing dependency is reported instead of crashing
    the caller.

    Args:
        url: Base URL of Qdrant, e.g. "http://qdrant:6333".
        client: Optional HTTP client. Tests pass one backed by
            httpx.MockTransport. When omitted, a short-lived client with a
            timeout is created and closed here.
    """
    if client is None:
        async with httpx.AsyncClient(timeout=READINESS_TIMEOUT_SECONDS) as own_client:
            return await is_qdrant_ready(url, own_client)

    try:
        response = await client.get(f"{url}/readyz")
        response.raise_for_status()
    except httpx.HTTPError:
        return False
    return True
