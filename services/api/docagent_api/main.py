"""DocAgent HTTP API: application factory and routes."""

from typing import Literal

from fastapi import FastAPI
from pydantic import BaseModel

from docagent_core import __version__ as docagent_version


class HealthResponse(BaseModel):
    status: Literal["ok"]
    version: str


def create_app() -> FastAPI:
    app = FastAPI(
        title="DocAgent API",
        version=docagent_version,
    )

    @app.get("/health", response_model=HealthResponse)
    async def health_check() -> HealthResponse:
        return HealthResponse(status="ok", version=docagent_version)

    return app


app = create_app()
