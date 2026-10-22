import pytest
from pydantic import ValidationError

from docagent_core import __version__
from docagent_core.config import Settings


def test_version_is_set() -> None:
    assert __version__


def test_defaults_use_mock_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("VLM_MODE", raising=False)
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
    with pytest.raises(ValidationError):
        Settings(_env_file=None)  # type: ignore[call-arg]
