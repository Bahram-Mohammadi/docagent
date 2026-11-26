"""Tests for the document upload and lookup endpoints."""

import hashlib
import io
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from docagent_api.documents import UPLOADS_DIR_NAME
from docagent_api.main import app
from docagent_core.config import Settings, get_settings


def pdf_bytes(page_count: int = 1) -> bytes:
    """Return a PDF of blank 100 x 200 pt pages."""
    buffer = io.BytesIO()
    pages = [Image.new("RGB", (100, 200), "white") for _ in range(page_count)]
    pages[0].save(buffer, format="PDF", save_all=True, append_images=pages[1:], resolution=72)
    return buffer.getvalue()


def staged_uploads(settings: Settings) -> list[Path]:
    """Return whatever is left in the upload staging folder."""
    return sorted((settings.pages_dir / UPLOADS_DIR_NAME).glob("*"))


@pytest.fixture
def settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Settings:
    """Small limits so 413 and too-many-pages cases need only tiny files."""
    monkeypatch.chdir(tmp_path)  # no .env here, so the developer's own .env is not read
    return Settings(
        pages_dir=tmp_path / "pages",
        max_upload_bytes=10_000,
        render_dpi=72,
        max_pages=2,
    )


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    """A test client whose requests use the test settings."""
    app.dependency_overrides[get_settings] = lambda: settings
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


def upload(client: TestClient, content: bytes) -> httpx.Response:
    """POST content as the `file` field, the way a browser form would."""
    return client.post("/documents", files={"file": ("report.pdf", content, "application/pdf")})


# --- POST /documents -----------------------------------------------------------


def test_upload_document_renders_a_new_pdf(client: TestClient, settings: Settings) -> None:
    content = pdf_bytes(page_count=2)

    response = upload(client, content)

    assert response.status_code == 201
    body = response.json()
    assert body["doc_id"] == hashlib.sha256(content).hexdigest()
    assert response.headers["location"] == f"/documents/{body['doc_id']}"
    assert body["dpi"] == settings.render_dpi
    assert body["page_count"] == 2
    assert [page["page_number"] for page in body["pages"]] == [1, 2]
    assert (body["pages"][0]["width"], body["pages"][0]["height"]) == (100, 200)
    assert "path" not in body["pages"][0]
    for number in (1, 2):
        assert (settings.pages_dir / body["doc_id"] / f"page-{number:04d}.png").is_file()


def test_upload_document_returns_existing_render_for_same_content(client: TestClient) -> None:
    content = pdf_bytes()
    first = upload(client, content)

    second = upload(client, content)

    assert first.status_code == 201
    assert second.status_code == 200
    assert second.json() == first.json()
    assert "location" not in second.headers


def test_upload_document_rejects_a_file_over_the_size_limit(
    client: TestClient, settings: Settings
) -> None:
    content = b"x" * (settings.max_upload_bytes + 1)

    response = upload(client, content)

    assert response.status_code == 413
    assert f"{settings.max_upload_bytes} bytes" in response.json()["detail"]


def test_upload_document_rejects_a_file_that_is_not_a_pdf(client: TestClient) -> None:
    content = b"Not a PDF"

    response = upload(client, content)

    assert response.status_code == 422
    assert "Cannot open" in response.json()["detail"]


def test_upload_document_rejects_a_pdf_with_too_many_pages(
    client: TestClient, settings: Settings
) -> None:
    content = pdf_bytes(page_count=settings.max_pages + 1)

    response = upload(client, content)

    assert response.status_code == 422
    assert "limit" in response.json()["detail"]


def test_upload_document_requires_a_file_field(client: TestClient) -> None:
    response = client.post("/documents")

    assert response.status_code == 422


def test_upload_document_leaves_no_staged_uploads(client: TestClient, settings: Settings) -> None:
    created = upload(client, pdf_bytes())
    too_large = upload(client, b"x" * (settings.max_upload_bytes + 1))
    not_a_pdf = upload(client, b"not a pdf")

    assert [created.status_code, too_large.status_code, not_a_pdf.status_code] == [201, 413, 422]
    assert (settings.pages_dir / UPLOADS_DIR_NAME).is_dir()
    assert staged_uploads(settings) == []


# --- GET /documents/{doc_id} ---------------------------------------------------


def test_get_document_returns_the_uploaded_render(client: TestClient) -> None:
    uploaded = upload(client, pdf_bytes(page_count=2))
    assert uploaded.status_code == 201

    response = client.get(f"/documents/{uploaded.json()['doc_id']}")

    assert response.status_code == 200
    assert response.json() == uploaded.json()


def test_get_document_returns_404_for_an_unknown_id(client: TestClient) -> None:
    content = pdf_bytes()
    upload(client, content)

    response = client.get(f"/documents/{hashlib.sha256(b'other content').hexdigest()}")

    assert response.status_code == 404


def test_get_document_rejects_a_malformed_id(client: TestClient) -> None:
    response = client.get("/documents/not-a-valid-sha256")

    assert response.status_code == 422
