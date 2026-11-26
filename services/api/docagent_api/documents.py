"""Endpoints for uploading PDFs and reading their rendered pages."""

import shutil
import threading
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, UploadFile, status
from fastapi import Path as PathParam
from pydantic import BaseModel

from docagent_api.uploads import UploadTooLargeError, save_upload
from docagent_core.config import Settings, get_settings
from docagent_core.ingestion.render import (
    DOC_ID_PATTERN,
    InvalidPDFError,
    RenderedDocument,
    compute_doc_id,
    load_rendered_document,
    render_pdf,
)

UPLOADS_DIR_NAME = ".uploads"  # staging area for requests in progress, inside pages_dir

router = APIRouter(prefix="/documents", tags=["documents"])

# PDFium is not thread-safe (ADR-008), and def routes run in a thread pool:
# only one render may run at a time in this process.
_render_lock = threading.Lock()

SettingsDep = Annotated[Settings, Depends(get_settings)]


class PageResponse(BaseModel):
    """One rendered page, as returned by the API."""

    page_number: int
    width: int
    height: int


class DocumentResponse(BaseModel):
    """A rendered document, as returned by the API. Storage paths are not exposed."""

    doc_id: str
    dpi: int
    page_count: int
    pages: list[PageResponse]

    @classmethod
    def from_rendered(cls, document: RenderedDocument) -> "DocumentResponse":
        """Convert the stored render into the API's response shape."""
        pages = [
            PageResponse(
                page_number=page.page_number,
                width=page.width,
                height=page.height,
            )
            for page in document.pages
        ]
        return cls(
            doc_id=document.doc_id,
            dpi=document.dpi,
            page_count=len(pages),
            pages=pages,
        )


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    responses={
        200: {"model": DocumentResponse, "description": "Already rendered"},
        413: {"description": "Upload too large"},
        422: {"description": "Not a usable PDF"},
    },
)
def upload_document(
    file: UploadFile, settings: SettingsDep, response: Response
) -> DocumentResponse:
    """Upload a PDF and render its pages, or return the existing render of the same file."""
    request_dir = settings.pages_dir / UPLOADS_DIR_NAME / uuid.uuid4().hex
    request_dir.mkdir(parents=True)
    staged = request_dir / "document.pdf"
    try:
        try:
            save_upload(file.file, staged, max_bytes=settings.max_upload_bytes)
        except UploadTooLargeError as exc:
            raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, detail=str(exc)) from exc
        with _render_lock:
            doc_id = compute_doc_id(staged)
            document = load_rendered_document(settings.pages_dir, doc_id, dpi=settings.render_dpi)
            if document is not None:
                response.status_code = status.HTTP_200_OK
            else:
                try:
                    document = render_pdf(
                        staged,
                        settings.pages_dir,
                        dpi=settings.render_dpi,
                        max_pages=settings.max_pages,
                    )
                except InvalidPDFError as exc:
                    raise HTTPException(
                        status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
                    ) from exc
                response.headers["Location"] = f"/documents/{document.doc_id}"
    finally:
        shutil.rmtree(request_dir, ignore_errors=True)
    return DocumentResponse.from_rendered(document)


@router.get("/{doc_id}", responses={404: {"description": "Not rendered"}})
def get_document(
    doc_id: Annotated[str, PathParam(pattern=DOC_ID_PATTERN)],
    settings: SettingsDep,
) -> DocumentResponse:
    """Return the rendered pages of a previously uploaded PDF."""
    document = load_rendered_document(settings.pages_dir, doc_id, dpi=settings.render_dpi)
    if document is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Document not found")
    return DocumentResponse.from_rendered(document)
