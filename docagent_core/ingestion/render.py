"""Render PDF pages to PNG images."""

import hashlib
from pathlib import Path

import pypdfium2 as pdfium
from pydantic import BaseModel, ConfigDict

DEFAULT_DPI = 144
POINTS_PER_INCH = 72
DEFAULT_MAX_PAGES = 500
MAX_PIXELS_PER_PAGE = 50_000_000


class InvalidPDFError(ValueError):
    """The file is not a usable PDF: unreadable, too many pages, or a page too large to render."""


class RenderedPage(BaseModel):
    """One rendered page. `path` is relative to the output directory."""

    model_config = ConfigDict(frozen=True)

    page_number: int
    path: Path
    width: int
    height: int


class RenderedDocument(BaseModel):
    """All rendered pages of one PDF, identified by its content hash."""

    model_config = ConfigDict(frozen=True)

    doc_id: str
    dpi: int
    pages: list[RenderedPage]


def compute_doc_id(pdf_path: Path) -> str:
    """Return the SHA-256 hex digest of the file's content.

    Identical bytes always give the same ID. A re-exported copy of the same
    document usually differs (for example, in embedded timestamps) and gets a new ID.
    """
    with pdf_path.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def render_pdf(
    pdf_path: Path,
    output_dir: Path,
    dpi: int = DEFAULT_DPI,
    max_pages: int = DEFAULT_MAX_PAGES,
) -> RenderedDocument:
    """Render every page of a PDF to PNG under output_dir/<doc_id>/.

    Page paths in the result are relative to output_dir, so the result stays valid
    if the output directory is moved or mounted somewhere else.

    Raises:
        InvalidPDFError: the file cannot be opened as a PDF, has more than
            max_pages pages, or has a page larger than MAX_PIXELS_PER_PAGE
            when rendered at this DPI.
    """
    doc_id = compute_doc_id(pdf_path)
    doc_dir = output_dir / doc_id
    scale = dpi / POINTS_PER_INCH

    try:
        pdf = pdfium.PdfDocument(pdf_path)
    except pdfium.PdfiumError as exc:
        raise InvalidPDFError(f"Cannot open {pdf_path.name} as a PDF") from exc

    pages: list[RenderedPage] = []
    try:
        page_count = len(pdf)
        if page_count > max_pages:
            raise InvalidPDFError(
                f"{pdf_path.name} has {page_count} pages; the limit is {max_pages}"
            )
        doc_dir.mkdir(parents=True, exist_ok=True)

        for index in range(page_count):
            page_number = index + 1
            page = pdf[index]
            try:
                width_pt, height_pt = page.get_size()
                width_px = round(width_pt * scale)
                height_px = round(height_pt * scale)
                if width_px * height_px > MAX_PIXELS_PER_PAGE:
                    raise InvalidPDFError(
                        f"{pdf_path.name} page {page_number} is too large "
                        f"({width_px}x{height_px} px at {dpi} DPI)"
                    )

                filename = f"page-{page_number:04d}.png"
                bitmap = page.render(scale=scale)
                try:
                    image = bitmap.to_pil()
                    image.save(doc_dir / filename, "PNG")
                finally:
                    bitmap.close()

                pages.append(
                    RenderedPage(
                        page_number=page_number,
                        path=Path(doc_id) / filename,
                        width=image.width,
                        height=image.height,
                    )
                )
            finally:
                page.close()
    finally:
        pdf.close()

    return RenderedDocument(doc_id=doc_id, dpi=dpi, pages=pages)
