from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from docagent_api.main import create_app
from docagent_core import __version__ as docagent_version


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(create_app()) as test_client:
        yield test_client


def test_health_returns_200(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200


def test_health_returns_status_and_version(client: TestClient) -> None:
    response = client.get("/health")

    assert response.json() == {
        "status": "ok",
        "version": docagent_version,
    }


def test_unknown_path_returns_404(client: TestClient) -> None:
    response = client.get("/does_not_exist")

    assert response.status_code == 404
