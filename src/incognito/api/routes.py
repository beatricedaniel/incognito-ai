from __future__ import annotations

import asyncio
import logging
import queue
from collections.abc import AsyncIterator
from typing import Final

from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from incognito.api.events import run_pipeline
from incognito.core.config import MAX_UPLOAD_BYTES, OLLAMA_MODEL, SSE_QUEUE_TIMEOUT_SECONDS
from incognito.core.exceptions import PdfError, SessionError
from incognito.core.sessions import create_session, get_session
from incognito.core.tempfiles import TempFileManager
from incognito.models import SessionState
from incognito.ollama.manager import check_ready
from incognito.pipeline.extractor import validate_pdf

_PDF_MAGIC: Final = b"%PDF-"
_ACCEPTED_CONTENT_TYPES: Final = frozenset({"application/pdf", "application/octet-stream"})

router: Final = APIRouter(prefix="/api")
logger: Final = logging.getLogger(__name__)


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
            temp=temp,
        )
    except Exception:
        temp.cleanup()
        raise

    logger.info("Session %s created", session.id)
    return {"session_id": session.id, "events_url": f"/api/events/{session.id}"}


@router.get("/events/{session_id}")
async def events(session_id: str) -> StreamingResponse:
    try:
        session = get_session(session_id)
    except SessionError:
        raise HTTPException(status_code=404, detail="Session not found") from None

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


@router.get("/detections/{session_id}")
async def get_detections(session_id: str) -> dict[str, object]:
    raise NotImplementedError


@router.delete("/detections/{session_id}/{detection_id}")
async def dismiss_detection(session_id: str, detection_id: str) -> dict[str, str]:
    raise NotImplementedError


@router.post("/redact/{session_id}")
async def redact(session_id: str) -> dict[str, str]:
    raise NotImplementedError


@router.post("/recover")
async def recover() -> dict[str, str]:
    raise NotImplementedError
