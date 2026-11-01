"""Tests for readiness: the /ready route and the Qdrant check behind it.

Route tests replace the checker with a fake, so they never touch the network.
Checker tests use httpx.MockTransport, so the real request and error-handling
code runs without a real Qdrant.
"""

from collections.abc import Iterator

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from docagent_api.main import QdrantChecker, create_app, get_qdrant_checker
from docagent_api.readiness import is_qdrant_ready
from docagent_core.config import Settings, get_settings

QDRANT_URL = "http://qdrant-test:6333"


def make_settings() -> Settings:
    """Settings that ignore the developer's environment and .env file."""
    return Settings(_env_file=None, qdrant_url=QDRANT_URL)  # type: ignore[call-arg]


def make_fake_checker(result: bool, calls: list[str]) -> QdrantChecker:
    """Build a fake Qdrant checker that records every URL it is called with."""

    async def fake_checker(url: str) -> bool:
        calls.append(url)
        return result

    return fake_checker


@pytest.fixture
def anyio_backend() -> str:
    """Run async tests on asyncio, the event loop uvicorn uses."""
    return "asyncio"


@pytest.fixture
def app() -> FastAPI:
    application = create_app()
    application.dependency_overrides[get_settings] = make_settings
    return application


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


# --- The /ready route (checker replaced by a fake) ---------------------------


@pytest.mark.parametrize(
    ("qdrant_ready", "expected_code", "expected_status"),
    [
        pytest.param(True, 200, "ready", id="ready"),
        pytest.param(False, 503, "not_ready", id="not-ready"),
    ],
)
def test_readiness_reflects_qdrant_state(
    app: FastAPI,
    client: TestClient,
    qdrant_ready: bool,
    expected_code: int,
    expected_status: str,
) -> None:
    calls: list[str] = []
    checker = make_fake_checker(qdrant_ready, calls)
    app.dependency_overrides[get_qdrant_checker] = lambda: checker

    response = client.get("/ready")

    assert response.status_code == expected_code
    assert response.json() == {
        "status": expected_status,
        "checks": {"qdrant": qdrant_ready},
    }
    assert calls == [QDRANT_URL]


def test_health_stays_ok_when_qdrant_is_not_ready(app: FastAPI, client: TestClient) -> None:
    checker = make_fake_checker(False, [])
    app.dependency_overrides[get_qdrant_checker] = lambda: checker

    assert client.get("/ready").status_code == 503
    assert client.get("/health").status_code == 200


def test_default_qdrant_checker_is_the_real_check() -> None:
    assert get_qdrant_checker() is is_qdrant_ready


# --- is_qdrant_ready (network replaced by httpx.MockTransport) ---------------


@pytest.mark.anyio
async def test_is_qdrant_ready_returns_true_on_200() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await is_qdrant_ready(QDRANT_URL, client)

    assert result is True
    assert len(requests) == 1
    assert requests[0].method == "GET"
    assert str(requests[0].url) == f"{QDRANT_URL}/readyz"


@pytest.mark.anyio
async def test_is_qdrant_ready_returns_false_on_503() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        assert await is_qdrant_ready(QDRANT_URL, client) is False


@pytest.mark.anyio
@pytest.mark.parametrize(
    "error_type",
    [
        pytest.param(httpx.ConnectError, id="connect-error"),
        pytest.param(httpx.ReadTimeout, id="read-timeout"),
    ],
)
async def test_is_qdrant_ready_returns_false_on_transport_error(
    error_type: type[httpx.TransportError],
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise error_type("simulated failure", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        assert await is_qdrant_ready(QDRANT_URL, client) is False


@pytest.mark.anyio
async def test_is_qdrant_ready_returns_false_when_nothing_listens() -> None:
    # No client passed: covers the branch that creates its own client.
    # Nothing listens on port 1, so the OS refuses the connection at once.
    assert await is_qdrant_ready("http://127.0.0.1:1") is False
