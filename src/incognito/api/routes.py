from __future__ import annotations

import logging
from typing import Final

from fastapi import APIRouter, UploadFile

router: Final = APIRouter(prefix="/api")
logger: Final = logging.getLogger(__name__)


@router.get("/status")
async def status() -> dict[str, object]:
    return {"status": "ok"}


@router.post("/upload")
async def upload_pdf(file: UploadFile) -> dict[str, str]:
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
