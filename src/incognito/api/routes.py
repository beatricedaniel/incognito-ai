from __future__ import annotations

import asyncio
import logging
import queue
import re
import time
import unicodedata
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Final

from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response, StreamingResponse
from starlette.background import BackgroundTask

from incognito.api.events import run_pipeline
from incognito.core.config import (
    MAX_UPLOAD_BYTES,
    OLLAMA_MODEL,
    PASSPHRASE_MIN_LENGTH,
    SSE_QUEUE_TIMEOUT_SECONDS,
)
from incognito.core.exceptions import (
    DetectionNotFoundError,
    PassphraseError,
    PdfError,
    RedactionError,
)
from incognito.core.sessions import create_session, delete_session, get_session
from incognito.core.tempfiles import TempFileManager
from incognito.models import RedactionMode, RedactRequest, SessionState
from incognito.ollama.manager import check_ready
from incognito.pipeline.extractor import validate_pdf
from incognito.pipeline.keyfile import embed as keyfile_embed
from incognito.pipeline.redactor import redact_pdf

_PDF_MAGIC: Final = b"%PDF-"
_ACCEPTED_CONTENT_TYPES: Final = frozenset({"application/pdf", "application/octet-stream"})
_UNSAFE_CHARS: Final = re.compile(r"[^\w\s\-.]")
_MAX_FILENAME_LEN: Final = 200

router: Final = APIRouter(prefix="/api")
logger: Final = logging.getLogger(__name__)


def _build_download_filename(original: str) -> str:
    if not original:
        return "redacted.pdf"
    stem = Path(original).stem
    stem = unicodedata.normalize("NFKC", stem)
    stem = _UNSAFE_CHARS.sub("", stem).strip()
    if not stem:
        return "redacted.pdf"
    return f"{stem[:_MAX_FILENAME_LEN]}_redacted.pdf"


@router.get("/status")
def status() -> dict[str, object]:
    return {"ollama_ready": check_ready(), "model": OLLAMA_MODEL}


@router.post("/upload", status_code=201)
async def upload_pdf(file: UploadFile) -> dict[str, str]:
    if file.content_type not in _ACCEPTED_CONTENT_TYPES:
        raise PdfError("Only PDF files are supported")

    pdf_bytes = await file.read()
    if len(pdf_bytes) > MAX_UPLOAD_BYTES:
        raise PdfError("File exceeds maximum size")

    if file.content_type == "application/octet-stream" and not pdf_bytes[:5] == _PDF_MAGIC:
        raise PdfError("Only PDF files are supported")

    temp = TempFileManager()
    try:
        pdf_path = temp.create_file("upload.pdf")
        pdf_path.write_bytes(pdf_bytes)
        validate_pdf(pdf_path)
        session = create_session(
            pdf_path=pdf_path,
            original_pdf_bytes=pdf_bytes,
            original_filename=file.filename or "",
            temp=temp,
        )
    except Exception:
        temp.cleanup()
        raise

    logger.info("Session %s created", session.id)
    return {"session_id": session.id, "events_url": f"/api/events/{session.id}"}


@router.get("/events/{session_id}")
async def events(session_id: str) -> StreamingResponse:
    session = get_session(session_id)

    if session.state != SessionState.UPLOADING:
        raise HTTPException(status_code=409, detail="Pipeline already started")

    event_queue: queue.Queue[str | None] = queue.Queue()

    async def _stream() -> AsyncIterator[str]:
        loop = asyncio.get_running_loop()
        pipeline_task = loop.run_in_executor(None, run_pipeline, session, event_queue)
        try:
            yield ": connected\n\n"
            while True:
                try:
                    event = await asyncio.to_thread(
                        event_queue.get,
                        timeout=SSE_QUEUE_TIMEOUT_SECONDS,
                    )
                except queue.Empty:
                    if pipeline_task.done():
                        break
                    yield ": keepalive\n\n"
                    continue
                if event is None:
                    break
                yield event
        finally:
            await pipeline_task

    return StreamingResponse(
        _stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/pdf/{session_id}")
async def get_pdf(session_id: str) -> Response:
    session = get_session(session_id)

    if session.state in {SessionState.UPLOADING, SessionState.PROCESSING}:
        raise HTTPException(status_code=409, detail="Pipeline not yet complete")

    if not session.original_pdf_bytes:
        raise HTTPException(status_code=404, detail="PDF not available")

    return Response(
        content=session.original_pdf_bytes,
        media_type="application/pdf",
        headers={"Cache-Control": "no-store"},
    )


@router.get("/detections/{session_id}")
async def get_detections(session_id: str) -> dict[str, object]:
    session = get_session(session_id)

    if session.state in {SessionState.UPLOADING, SessionState.PROCESSING}:
        raise HTTPException(status_code=409, detail="Pipeline not yet complete")

    sorted_detections = sorted(session.detections, key=lambda d: (d.page, d.start))
    return {"detections": [d.model_dump() for d in sorted_detections]}


@router.delete("/detections/{session_id}/{detection_id}")
async def dismiss_detection(session_id: str, detection_id: str) -> dict[str, str]:
    session = get_session(session_id)

    if session.state in {SessionState.UPLOADING, SessionState.PROCESSING}:
        raise HTTPException(status_code=409, detail="Pipeline not yet complete")

    for det in session.detections:
        if det.id == detection_id:
            det.dismissed = True
            return {"status": "dismissed"}

    raise DetectionNotFoundError(f"Detection {detection_id} not in session")


@router.post("/redact/{session_id}")
async def redact(session_id: str, body: RedactRequest | None = None) -> FileResponse:
    session = get_session(session_id)

    if session.state != SessionState.REVIEWING:
        raise HTTPException(status_code=409, detail="Session not in reviewing state")

    active = [d for d in session.detections if not d.dismissed]
    if not active:
        raise HTTPException(status_code=409, detail="No detections to redact")

    request = body if body is not None else RedactRequest()

    if request.mode == RedactionMode.REVERSIBLE and (
        not request.passphrase or len(request.passphrase) < PASSPHRASE_MIN_LENGTH
    ):
        raise PassphraseError(f"Passphrase must be at least {PASSPHRASE_MIN_LENGTH} characters")

    if session.pdf_path is None or session.temp is None:
        raise RedactionError("Session is missing PDF data")

    session.state = SessionState.REDACTING
    session.updated_at = time.time()

    try:
        output_path = session.temp.create_file("redacted.pdf")
        redact_pdf(session.pdf_path, active, output_path)
    except Exception:
        session.state = SessionState.ERROR
        session.updated_at = time.time()
        raise

    if request.mode == RedactionMode.REVERSIBLE:
        try:
            keyfile_embed(output_path, session.original_pdf_bytes, request.passphrase)  # type: ignore[arg-type]
        except NotImplementedError:
            session.state = SessionState.ERROR
            session.updated_at = time.time()
            raise RedactionError("Reversible redaction is not yet available") from None

    session.state = SessionState.COMPLETE
    session.updated_at = time.time()

    download_name = _build_download_filename(session.original_filename)

    return FileResponse(
        path=output_path,
        media_type="application/pdf",
        filename=download_name,
        background=BackgroundTask(delete_session, session_id),
    )


@router.post("/recover")
async def recover() -> dict[str, str]:
    raise NotImplementedError
