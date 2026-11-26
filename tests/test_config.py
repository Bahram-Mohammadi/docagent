"""Tests for the shared settings module."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from docagent_core import __version__
from docagent_core.config import Settings, get_settings


def test_version_is_set() -> None:
    assert __version__


# --- General settings ----------------------------------------------------------


def test_defaults_use_mock_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("VLM_MODE", raising=False)
    monkeypatch.delenv("TOP_K", raising=False)

    settings = Settings(_env_file=None)  # type: ignore[call-arg]

    assert settings.vlm_mode == "mock"
    assert settings.top_k == 5


def test_reads_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VLM_MODE", "live")
    monkeypatch.setenv("TOP_K", "10")
    monkeypatch.setenv("HF_TOKEN", "hf_test_value")

    settings = Settings(_env_file=None)  # type: ignore[call-arg]

    assert settings.vlm_mode == "live"
    assert settings.top_k == 10
    assert settings.hf_token is not None
    assert "hf_test_value" not in repr(settings)


def test_rejects_invalid_values(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TOP_K", "0")

    with pytest.raises(ValidationError, match="top_k"):
        Settings(_env_file=None)  # type: ignore[call-arg]


# --- Document ingestion settings -----------------------------------------------


def test_ingestion_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("PAGES_DIR", "MAX_UPLOAD_BYTES", "RENDER_DPI", "MAX_PAGES"):
        monkeypatch.delenv(name, raising=False)

    settings = Settings(_env_file=None)  # type: ignore[call-arg]

    assert settings.pages_dir == Path("data/pages")
    assert settings.max_upload_bytes == 50 * 1024 * 1024
    assert settings.render_dpi == 144
    assert settings.max_pages == 500


def test_reads_ingestion_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    # Smallest valid limits (1) and the largest valid DPI (600): the accepted side of each boundary.
    monkeypatch.setenv("PAGES_DIR", "/srv/docagent/pages")
    monkeypatch.setenv("MAX_UPLOAD_BYTES", "1")
    monkeypatch.setenv("RENDER_DPI", "600")
    monkeypatch.setenv("MAX_PAGES", "1")

    settings = Settings(_env_file=None)  # type: ignore[call-arg]

    assert settings.pages_dir == Path("/srv/docagent/pages")
    assert settings.max_upload_bytes == 1
    assert settings.render_dpi == 600
    assert settings.max_pages == 1


@pytest.mark.parametrize(
    ("name", "value"),
    [
        pytest.param("MAX_UPLOAD_BYTES", "0", id="zero-upload-limit"),
        pytest.param("RENDER_DPI", "0", id="zero-dpi"),
        pytest.param("RENDER_DPI", "601", id="dpi-above-600"),
        pytest.param("MAX_PAGES", "0", id="zero-max-pages"),
    ],
)
def test_rejects_invalid_ingestion_values(
    monkeypatch: pytest.MonkeyPatch, name: str, value: str
) -> None:
    monkeypatch.setenv(name, value)

    # Pydantic names the failing field, so this proves *this* setting was rejected.
    with pytest.raises(ValidationError, match=name.lower()):
        Settings(_env_file=None)  # type: ignore[call-arg]


# --- get_settings ----------------------------------------------------------------


def test_get_settings_returns_one_cached_instance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)  # no .env here, so the developer's own .env is not read
    get_settings.cache_clear()
    try:
        first = get_settings()

        assert isinstance(first, Settings)
        assert get_settings() is first
    finally:
        get_settings.cache_clear()
