"""Tests for saving uploads with a size limit."""

import io
from pathlib import Path

import pytest

from docagent_api.uploads import UploadTooLargeError, save_upload


@pytest.fixture
def destination(tmp_path: Path) -> Path:
    """Where the upload is saved. Not created here: save_upload must create it."""
    return tmp_path / "upload.pdf"


class FailingSource(io.BytesIO):
    """Returns its first chunk normally, then fails, like a dropped connection."""

    def read(self, size: int | None = -1, /) -> bytes:
        if self.tell() > 0:
            raise OSError("connection lost")
        return super().read(size)


def test_save_upload_writes_content_and_returns_size(destination: Path) -> None:
    content = b"%PDF-1.7 example"

    written = save_upload(io.BytesIO(content), destination, max_bytes=100)

    assert written == len(content)
    assert destination.read_bytes() == content


def test_save_upload_accepts_max_bytes(destination: Path) -> None:
    content = b"x" * 10

    written = save_upload(io.BytesIO(content), destination, max_bytes=10)

    assert written == len(content)
    assert destination.read_bytes() == content


def test_save_upload_rejects_more_than_max_bytes(destination: Path) -> None:
    content = b"x" * 11

    with pytest.raises(UploadTooLargeError, match="limit of 10 bytes"):
        save_upload(io.BytesIO(content), destination, max_bytes=10)

    assert not destination.exists()


def test_save_upload_across_several_chunks(destination: Path) -> None:
    content = b"0123456789"

    written = save_upload(io.BytesIO(content), destination, max_bytes=100, chunk_size=4)

    assert written == len(content)
    assert destination.read_bytes() == content


def test_save_upload_stops_reading_once_over_the_limit(destination: Path) -> None:
    source = io.BytesIO(b"x" * 1000)

    with pytest.raises(UploadTooLargeError, match="limit of 10 bytes"):
        save_upload(source, destination, max_bytes=10, chunk_size=4)

    assert source.tell() <= 10 + 4
    assert not destination.exists()


def test_save_upload_never_overwrites_an_existing_file(destination: Path) -> None:
    destination.write_bytes(b"original")

    with pytest.raises(FileExistsError):
        save_upload(io.BytesIO(b"new"), destination, max_bytes=100)

    assert destination.read_bytes() == b"original"


def test_save_upload_removes_partial_file_when_reading_fails(destination: Path) -> None:
    source = FailingSource(b"abcdefgh")

    with pytest.raises(OSError, match="connection lost"):
        save_upload(source, destination, max_bytes=100, chunk_size=4)

    assert not destination.exists()


@pytest.mark.parametrize(
    ("max_bytes", "chunk_size", "message"),
    [
        pytest.param(0, 4, "max_bytes must be positive, got 0", id="zero-max-bytes"),
        pytest.param(-1, 4, "max_bytes must be positive, got -1", id="negative-max-bytes"),
        pytest.param(10, 0, "chunk_size must be positive, got 0", id="zero-chunk-size"),
        pytest.param(10, -1, "chunk_size must be positive, got -1", id="negative-chunk-size"),
    ],
)
def test_save_upload_rejects_non_positive_arguments(
    destination: Path, max_bytes: int, chunk_size: int, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        save_upload(io.BytesIO(b"data"), destination, max_bytes=max_bytes, chunk_size=chunk_size)

    assert not destination.exists()
