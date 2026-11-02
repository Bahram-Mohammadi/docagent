"""Tests for PDF page rendering and document IDs."""

import hashlib
import shutil
from pathlib import Path

import pytest
from PIL import Image

from docagent_core.ingestion.render import InvalidPDFError, compute_doc_id, render_pdf


def make_pdf(
    path: Path,
    page_count: int = 1,
    size: tuple[int, int] = (100, 200),
    resolution: float = 72.0,
) -> Path:
    """Write a PDF of blank pages. Page size in points is size * 72 / resolution."""
    images = [Image.new("RGB", size, "white") for _ in range(page_count)]
    images[0].save(path, "PDF", save_all=True, append_images=images[1:], resolution=resolution)
    return path


@pytest.fixture
def output_dir(tmp_path: Path) -> Path:
    """Where rendered pages go. Not created here: tests check whether render_pdf creates it."""
    return tmp_path / "pages"


# --- compute_doc_id (plain bytes: the hash depends only on the file's content) -


def test_compute_doc_id_returns_sha256_of_content(tmp_path: Path) -> None:
    content = b"%PDF-1.7 example bytes"
    pdf_path = tmp_path / "doc.pdf"
    pdf_path.write_bytes(content)

    doc_id = compute_doc_id(pdf_path)

    assert doc_id == hashlib.sha256(content).hexdigest()


def test_compute_doc_id_is_the_same_for_identical_content(tmp_path: Path) -> None:
    original = tmp_path / "report.pdf"
    original.write_bytes(b"%PDF-1.7 identical bytes")
    copy = tmp_path / "report (1).pdf"
    shutil.copy(original, copy)

    assert compute_doc_id(copy) == compute_doc_id(original)


def test_compute_doc_id_differs_for_different_content(tmp_path: Path) -> None:
    first = tmp_path / "a.pdf"
    second = tmp_path / "b.pdf"
    first.write_bytes(b"%PDF-1.7 content A")
    second.write_bytes(b"%PDF-1.7 content B")

    assert compute_doc_id(first) != compute_doc_id(second)


# --- render_pdf: successful rendering (real PDFs from make_pdf) ---------------


def test_render_pdf_renders_every_page(tmp_path: Path, output_dir: Path) -> None:
    pdf_path = make_pdf(tmp_path / "doc.pdf", page_count=3)

    result = render_pdf(pdf_path, output_dir)

    assert result.doc_id == compute_doc_id(pdf_path)
    assert [page.page_number for page in result.pages] == [1, 2, 3]
    assert [page.path for page in result.pages] == [
        Path(result.doc_id) / f"page-{n:04d}.png" for n in (1, 2, 3)
    ]
    assert all((output_dir / page.path).is_file() for page in result.pages)


@pytest.mark.parametrize(
    ("dpi", "expected_size"),
    [
        pytest.param(72, (100, 200), id="72dpi"),
        pytest.param(144, (200, 400), id="144dpi"),
    ],
)
def test_render_pdf_image_size_follows_dpi(
    tmp_path: Path, output_dir: Path, dpi: int, expected_size: tuple[int, int]
) -> None:
    pdf_path = make_pdf(tmp_path / "doc.pdf")  # one 100 x 200 pt page

    result = render_pdf(pdf_path, output_dir, dpi=dpi)

    page = result.pages[0]
    assert (page.width, page.height) == expected_size
    with Image.open(output_dir / page.path) as image:
        assert image.size == expected_size


# --- render_pdf: limits and invalid input --------------------------------------


def test_render_pdf_accepts_exactly_max_pages(tmp_path: Path, output_dir: Path) -> None:
    pdf_path = make_pdf(tmp_path / "doc.pdf", page_count=2)

    result = render_pdf(pdf_path, output_dir, max_pages=2)

    assert len(result.pages) == 2


def test_render_pdf_rejects_more_than_max_pages(tmp_path: Path, output_dir: Path) -> None:
    pdf_path = make_pdf(tmp_path / "doc.pdf", page_count=3)

    with pytest.raises(InvalidPDFError, match="limit"):
        render_pdf(pdf_path, output_dir, max_pages=2)

    assert not output_dir.exists()


def test_render_pdf_rejects_oversized_page(tmp_path: Path, output_dir: Path) -> None:
    # 100 x 100 px at resolution=1 declares a 100-inch page: 14,400 x 14,400 px at 144 DPI.
    pdf_path = make_pdf(tmp_path / "doc.pdf", size=(100, 100), resolution=1)

    with pytest.raises(InvalidPDFError, match="too large"):
        render_pdf(pdf_path, output_dir)

    assert list(output_dir.rglob("*.png")) == []


@pytest.mark.parametrize(
    "content",
    [
        pytest.param(b"", id="empty"),
        pytest.param(b"not a pdf", id="not-pdf"),
    ],
)
def test_render_pdf_rejects_unreadable_file(
    tmp_path: Path, output_dir: Path, content: bytes
) -> None:
    pdf_path = tmp_path / "doc.pdf"
    pdf_path.write_bytes(content)

    with pytest.raises(InvalidPDFError, match="Cannot open"):
        render_pdf(pdf_path, output_dir)

    assert not output_dir.exists()
