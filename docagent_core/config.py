"""Central settings, read from environment variables or a `.env` file.

Every service imports `get_settings()` instead of reading `os.environ` directly,
so all configuration is typed, validated and documented in one place.
"""

from functools import lru_cache
from pathlib import Path
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

    # Document ingestion
    pages_dir: Path = Path("data/pages")  # containers set PAGES_DIR to a mounted volume
    max_upload_bytes: int = Field(default=50 * 1024 * 1024, gt=0)  # 50 MB
    render_dpi: int = Field(default=144, gt=0, le=600)  # 144 = scale 2 (PDF points are 1/72 in)
    max_pages: int = Field(default=500, gt=0)


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings, read and validated once on first use."""
    return Settings()
