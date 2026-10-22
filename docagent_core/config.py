"""Central settings, read from environment variables or a `.env` file.

Every service imports `get_settings()` instead of reading `os.environ` directly,
so all configuration is typed, validated and documented in one place.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Model serving
    vlm_mode: Literal["live", "mock"] = "mock"
    vlm_url: str = "http://vlm:8000/v1"
    vlm_model: str = "Qwen/Qwen2.5-VL-3B-Instruct-AWQ"

    # Retrieval
    qdrant_url: str = "http://qdrant:6333"
    retriever_url: str = "http://retriever:8001"
    top_k: int = Field(default=5, ge=1, le=50)

    # Secrets
    hf_token: SecretStr | None = None

    # Runtime
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
