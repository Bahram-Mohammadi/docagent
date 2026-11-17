"""Render PDF pages to PNG images."""

import hashlib
import re
import shutil
import uuid
from pathlib import Path
from typing import Any

import pypdfium2 as pdfium
from pydantic import BaseModel, ConfigDict, ValidationError

DEFAULT_DPI = 144
POINTS_PER_INCH = 72
DEFAULT_MAX_PAGES = 500
MAX_PIXELS_PER_PAGE = 50_000_000
MANIFEST_NAME = "manifest.json"
DOC_ID_PATTERN = r"^[0-9a-f]{64}$"  # lowercase SHA-256 hex, as compute_doc_id returns


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


def _load_manifest(path: Path) -> RenderedDocument | None:
    """Return the saved result at path, or None if it is missing or unreadable."""
    try:
        return RenderedDocument.model_validate_json(path.read_bytes())
    except (OSError, ValidationError):
        return None


def load_rendered_document(output_dir: Path, doc_id: str, *, dpi: int) -> RenderedDocument | None:
    """Return the saved render of doc_id at dpi, or None if there is no complete one.

    A saved render counts only if its manifest parses, matches doc_id and dpi,
    and every page image it lists exists.

    Raises:
        ValueError: doc_id is not a lowercase SHA-256 hex digest.
    """
    if re.fullmatch(DOC_ID_PATTERN, doc_id) is None:
        raise ValueError(f"Invalid document ID: {doc_id!r}")

    saved = _load_manifest(output_dir / doc_id / MANIFEST_NAME)

    if (
        saved is not None
        and saved.doc_id == doc_id
        and saved.dpi == dpi
        and all((output_dir / page.path).is_file() for page in saved.pages)
    ):
        return saved
    return None


def _render_page(
    page: Any,
    *,
    page_number: int,
    scale: float,
    dpi: int,
    write_dir: Path,
    doc_id: str,
    pdf_name: str,
) -> RenderedPage:
    """Check one page's size, render it as PNG into write_dir, and describe it.

    The caller owns `page` and must close it; this function closes only the bitmap it creates.
    """
    width_pt, height_pt = page.get_size()
    width_px = round(width_pt * scale)
    height_px = round(height_pt * scale)
    if width_px * height_px > MAX_PIXELS_PER_PAGE:
        raise InvalidPDFError(
            f"{pdf_name} page {page_number} is too large ({width_px}x{height_px} px at {dpi} DPI)"
        )

    filename = f"page-{page_number:04d}.png"
    bitmap = page.render(scale=scale)
    try:
        image = bitmap.to_pil()
        image.save(write_dir / filename, "PNG")
        width, height = image.size
    finally:
        bitmap.close()

    return RenderedPage(
        page_number=page_number,
        path=Path(doc_id) / filename,
        width=width,
        height=height,
    )


def render_pdf(
    pdf_path: Path,
    output_dir: Path,
    dpi: int = DEFAULT_DPI,
    max_pages: int = DEFAULT_MAX_PAGES,
) -> RenderedDocument:
    """Render every page of a PDF to PNG under output_dir/<doc_id>/.

    If a complete render already exists at this DPI (see load_rendered_document),
    it is returned without opening the PDF.

    Otherwise, pages are written to a temporary folder inside output_dir and moved
    into place only after every page succeeds, so output_dir/<doc_id>/ is either
    complete or absent. An earlier render (a different DPI, or one with missing images)
    is replaced, and the old one is kept until the new one is in place.

    Page paths in the result are relative to output_dir, so the result stays valid
    if the output directory is moved or mounted somewhere else.

    Raises:
        ValueError: dpi or max_pages is not positive.
        InvalidPDFError: the file cannot be opened as a PDF, has more than
            max_pages pages, or has a page larger than MAX_PIXELS_PER_PAGE
            when rendered at this DPI.
    """
    if dpi <= 0:
        raise ValueError(f"dpi must be positive, got {dpi}")
    if max_pages <= 0:
        raise ValueError(f"max_pages must be positive, got {max_pages}")

    doc_id = compute_doc_id(pdf_path)
    doc_dir = output_dir / doc_id

    saved = load_rendered_document(output_dir, doc_id, dpi=dpi)
    if saved is not None:
        return saved

    scale = dpi / POINTS_PER_INCH

    try:
        pdf = pdfium.PdfDocument(pdf_path)
    except pdfium.PdfiumError as exc:
        raise InvalidPDFError(f"Cannot open {pdf_path.name} as a PDF") from exc

    try:
        page_count = len(pdf)
        if page_count > max_pages:
            raise InvalidPDFError(
                f"{pdf_path.name} has {page_count} pages; the limit is {max_pages}"
            )

        # Same filesystem as doc_dir, so the final rename is atomic.
        output_dir.mkdir(parents=True, exist_ok=True)
        tmp_dir = output_dir / f".tmp-{doc_id}-{uuid.uuid4().hex}"
        tmp_dir.mkdir()

        pages: list[RenderedPage] = []
        try:
            for index in range(page_count):
                page = pdf[index]
                try:
                    pages.append(
                        _render_page(
                            page,
                            page_number=index + 1,
                            scale=scale,
                            dpi=dpi,
                            write_dir=tmp_dir,
                            doc_id=doc_id,
                            pdf_name=pdf_path.name,
                        )
                    )
                finally:
                    page.close()

            # The manifest is written last: its presence marks the folder as complete.
            document = RenderedDocument(doc_id=doc_id, dpi=dpi, pages=pages)
            (tmp_dir / MANIFEST_NAME).write_text(
                document.model_dump_json(indent=2), encoding="utf-8"
            )

            # Replace an earlier render only once the new one is fully written.
            backup_dir: Path | None = None
            if doc_dir.exists():
                backup_dir = output_dir / f".old-{doc_id}-{uuid.uuid4().hex}"
                doc_dir.rename(backup_dir)
            try:
                tmp_dir.rename(doc_dir)
            except BaseException:
                if backup_dir is not None:
                    backup_dir.rename(doc_dir)  # put the old render back
                raise
            if backup_dir is not None:
                shutil.rmtree(backup_dir, ignore_errors=True)

        except BaseException:
            # Leave nothing behind, then let the original error propagate unchanged.
            shutil.rmtree(tmp_dir, ignore_errors=True)
            raise
    finally:
        pdf.close()

    return document
