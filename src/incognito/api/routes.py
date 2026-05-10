from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import Final

from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from incognito.core.config import MAX_UPLOAD_BYTES, OLLAMA_MODEL
from incognito.core.exceptions import PdfError, SessionError
from incognito.core.sessions import create_session, get_session
from incognito.core.tempfiles import TempFileManager
from incognito.ollama.manager import check_ready

router: Final = APIRouter(prefix="/api")
logger: Final = logging.getLogger(__name__)


@router.get("/status")
def status() -> dict[str, object]:
    return {"ollama_ready": check_ready(), "model": OLLAMA_MODEL}


@router.post("/upload", status_code=201)
async def upload_pdf(file: UploadFile) -> dict[str, str]:
    if file.content_type != "application/pdf":
        raise PdfError("Expected a PDF file")

    pdf_bytes = await file.read()
    if len(pdf_bytes) > MAX_UPLOAD_BYTES:
        raise PdfError("File exceeds maximum size")

    temp = TempFileManager()
    pdf_path = temp.create_file("upload.pdf")
    pdf_path.write_bytes(pdf_bytes)

    session = create_session(
        pdf_path=pdf_path,
        original_pdf_bytes=pdf_bytes,
        temp=temp,
    )

    logger.info("Session %s created", session.id)
    return {"session_id": session.id, "events_url": f"/api/events/{session.id}"}


@router.get("/events/{session_id}")
async def events(session_id: str) -> StreamingResponse:
    try:
        get_session(session_id)
    except SessionError:
        raise HTTPException(status_code=404, detail="Session not found") from None

    async def _stream() -> AsyncIterator[str]:
        yield ""

    return StreamingResponse(_stream(), media_type="text/event-stream")


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
