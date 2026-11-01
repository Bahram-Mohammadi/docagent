"""DocAgent HTTP API: application factory and routes."""

from collections.abc import Awaitable, Callable
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, Response, status
from pydantic import BaseModel

from docagent_api.readiness import is_qdrant_ready
from docagent_core import __version__ as docagent_version
from docagent_core.config import Settings, get_settings

# An async function that takes Qdrant's base URL and reports whether it is ready.
QdrantChecker = Callable[[str], Awaitable[bool]]


class HealthResponse(BaseModel):
    status: Literal["ok"]
    version: str


class ReadinessResponse(BaseModel):
    status: Literal["ready", "not_ready"]
    checks: dict[str, bool]


def get_qdrant_checker() -> QdrantChecker:
    """Provide the Qdrant readiness check as a FastAPI dependency.

    Returns the function itself, not its result, so tests can swap in a fake
    with app.dependency_overrides[get_qdrant_checker].
    """
    return is_qdrant_ready


def create_app() -> FastAPI:
    app = FastAPI(
        title="DocAgent API",
        version=docagent_version,
    )

    @app.get("/health", response_model=HealthResponse)
    async def health_check() -> HealthResponse:
        return HealthResponse(status="ok", version=docagent_version)

    @app.get(
        "/ready",
        response_model=ReadinessResponse,
        responses={
            status.HTTP_503_SERVICE_UNAVAILABLE: {
                "model": ReadinessResponse,
                "description": "At least one dependency is not ready",
            },
        },
    )
    async def readiness_check(
        response: Response,
        settings: Annotated[Settings, Depends(get_settings)],
        check_qdrant: Annotated[QdrantChecker, Depends(get_qdrant_checker)],
    ) -> ReadinessResponse:
        checks = {"qdrant": await check_qdrant(settings.qdrant_url)}
        all_ready = all(checks.values())

        if not all_ready:
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

        return ReadinessResponse(
            status="ready" if all_ready else "not_ready",
            checks=checks,
        )

    return app


app = create_app()
