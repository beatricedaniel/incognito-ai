from __future__ import annotations

import json
import logging
import queue
import time
from collections.abc import Callable, Iterator
from typing import Final

from incognito.core.config import (
    STAGE_DETECTING,
    STAGE_EXTRACTING,
    STAGE_VALIDATING,
)
from incognito.core.exceptions import IncognitoError
from incognito.core.sessions import Session
from incognito.models import Detection, RawDetection, SessionState, TextBlock
from incognito.pipeline.detector import detect_entities
from incognito.pipeline.extractor import extract_blocks
from incognito.pipeline.validator import validate_detections

STAGE_UPDATE: Final[str] = "stage_update"
PIPELINE_ERROR: Final[str] = "pipeline_error"
PIPELINE_COMPLETE: Final[str] = "pipeline_complete"

_DONE: Final = None

_STAGE_MESSAGES: Final[dict[str, str]] = {
    STAGE_EXTRACTING: "Extracting text from PDF\u2026",
    STAGE_DETECTING: "Detecting PII entities\u2026",
    STAGE_VALIDATING: "Validating detections\u2026",
}

_UNEXPECTED_DETAIL: Final[str] = "An unexpected error occurred"

logger: Final = logging.getLogger(__name__)


def sse_event(event_type: str, data: dict[str, object]) -> str:
    return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"


def stage_updates(stages: Iterator[tuple[str, str]]) -> Iterator[str]:
    for stage, message in stages:
        yield sse_event(STAGE_UPDATE, {"stage": stage, "message": message})


def run_pipeline(
    session: Session,
    event_queue: queue.Queue[str | None],
) -> None:
    if session.pdf_path is None:
        _emit_error(
            event_queue,
            session,
            STAGE_EXTRACTING,
            "Internal error",
            "Session has no PDF",
        )
        return

    session.state = SessionState.PROCESSING
    session.updated_at = time.time()

    pdf_path = session.pdf_path

    # --- extract ---
    _emit_stage(event_queue, STAGE_EXTRACTING)
    blocks = _run_stage(
        event_queue,
        session,
        STAGE_EXTRACTING,
        lambda: extract_blocks(pdf_path),
    )
    if blocks is None:
        return

    # --- detect ---
    _emit_stage(event_queue, STAGE_DETECTING)
    block_raws: list[tuple[TextBlock, list[RawDetection]]] = []
    for block in blocks:
        raws = _run_stage(
            event_queue,
            session,
            STAGE_DETECTING,
            _detect_fn(block),
        )
        if raws is None:
            return
        block_raws.append((block, raws))

    # --- validate ---
    _emit_stage(event_queue, STAGE_VALIDATING)
    all_detections: list[Detection] = []
    for block, raws in block_raws:
        valid = _run_stage(
            event_queue,
            session,
            STAGE_VALIDATING,
            _validate_fn(block, raws),
        )
        if valid is None:
            return
        all_detections.extend(valid)

    session.detections = all_detections
    session.state = SessionState.REVIEWING
    session.updated_at = time.time()

    event_queue.put(
        sse_event(
            PIPELINE_COMPLETE,
            {
                "session_id": session.id,
                "total_detections": len(all_detections),
            },
        )
    )
    event_queue.put(_DONE)


def _detect_fn(
    block: TextBlock,
) -> Callable[[], list[RawDetection]]:
    def _call() -> list[RawDetection]:
        return detect_entities(block)

    return _call


def _validate_fn(
    block: TextBlock,
    raws: list[RawDetection],
) -> Callable[[], list[Detection]]:
    def _call() -> list[Detection]:
        return validate_detections(block, raws)

    return _call


def _emit_stage(
    event_queue: queue.Queue[str | None],
    stage: str,
) -> None:
    event_queue.put(
        sse_event(
            STAGE_UPDATE,
            {"stage": stage, "message": _STAGE_MESSAGES[stage]},
        )
    )


def _run_stage[T](
    event_queue: queue.Queue[str | None],
    session: Session,
    stage: str,
    fn: Callable[[], T],
) -> T | None:
    try:
        return fn()
    except IncognitoError as exc:
        _emit_error(event_queue, session, stage, exc.error, exc.detail)
    except Exception:
        logger.exception("Unexpected error in %s", stage)
        _emit_error(
            event_queue,
            session,
            stage,
            "Internal error",
            _UNEXPECTED_DETAIL,
        )
    return None


def _emit_error(
    event_queue: queue.Queue[str | None],
    session: Session,
    stage: str,
    error: str,
    detail: str,
) -> None:
    event_queue.put(
        sse_event(
            PIPELINE_ERROR,
            {
                "error": error,
                "stage": stage,
                "detail": detail,
            },
        )
    )
    session.state = SessionState.ERROR
    session.updated_at = time.time()
    event_queue.put(_DONE)
