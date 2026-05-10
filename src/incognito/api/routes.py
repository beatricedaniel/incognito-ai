from __future__ import annotations

import logging
from typing import Final

from fastapi import APIRouter, UploadFile

from incognito.core.config import OLLAMA_MODEL
from incognito.ollama.manager import check_ready

router: Final = APIRouter(prefix="/api")
logger: Final = logging.getLogger(__name__)


@router.get("/status")
def status() -> dict[str, object]:
    return {"ollama_ready": check_ready(), "model": OLLAMA_MODEL}


@router.post("/upload")
async def upload_pdf(file: UploadFile) -> dict[str, str]:
    raise NotImplementedError


@router.get("/events/{session_id}")
async def events(session_id: str) -> None:
    raise NotImplementedError


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
