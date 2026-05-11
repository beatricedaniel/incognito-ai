from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import fitz
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from incognito.core.exceptions import DetectionError, PdfError
from incognito.core.sessions import create_session, get_session
from incognito.core.tempfiles import TempFileManager
from incognito.models import BBox, Detection, EntityType, RawDetection, SessionState, TextBlock

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_pdf_bytes() -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Jean Dupont habite au 12 rue de la Paix.")
    b = doc.tobytes()
    doc.close()
    return b


def _make_app(tmp_path: Path) -> FastAPI:
    static_dir = tmp_path / "static"
    static_dir.mkdir()
    (static_dir / "index.html").write_text("<html></html>")

    with (
        patch("incognito.app.STATIC_DIR", static_dir),
        patch("incognito.app.cleanup_orphaned_temp_dirs"),
    ):
        from incognito.app import create_app

        return create_app()


def _parse_sse(raw: str) -> list[dict[str, object]]:
    """Parse raw SSE text into list of {event, data} dicts. Skips comments and blanks."""
    events: list[dict[str, object]] = []
    current_event: str | None = None
    current_data: str | None = None

    for line in raw.splitlines():
        if line.startswith(":"):
            continue
        if line.startswith("event:"):
            current_event = line[len("event:") :].strip()
        elif line.startswith("data:"):
            current_data = line[len("data:") :].strip()
        elif line == "":
            if current_event is not None and current_data is not None:
                events.append({"event": current_event, "data": json.loads(current_data)})
            current_event = None
            current_data = None

    return events


_SAMPLE_BLOCK = TextBlock(
    text="Jean Dupont habite au 12 rue de la Paix.",
    page=0,
    bbox=BBox(x=72.0, y=72.0, width=300.0, height=12.0),
    block_index=0,
)

_SAMPLE_RAW_DETECTION = RawDetection(
    text="Jean Dupont",
    entity_type=EntityType.PERSON,
    start=0,
    end=11,
)

_SAMPLE_DETECTION = Detection(
    text="Jean Dupont",
    entity_type=EntityType.PERSON,
    page=0,
    start=0,
    end=11,
    bbox=BBox(x=72.0, y=72.0, width=300.0, height=12.0),
)

# patch targets: incognito.api.events will import these when implemented
_PATCH_EXTRACT = "incognito.api.events.extract_blocks"
_PATCH_DETECT = "incognito.api.events.detect_entities"
_PATCH_VALIDATE = "incognito.api.events.validate_detections"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def app(tmp_path: Path) -> FastAPI:
    return _make_app(tmp_path)


@pytest.fixture
async def client(app: FastAPI) -> AsyncClient:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


@pytest.fixture
def uploading_session() -> tuple[str, Path]:
    """Create a session in UPLOADING state with a real PDF on disk."""
    pdf_bytes = _make_pdf_bytes()
    temp = TempFileManager()
    pdf_path = temp.create_file("upload.pdf")
    pdf_path.write_bytes(pdf_bytes)
    session = create_session(
        pdf_path=pdf_path,
        original_pdf_bytes=pdf_bytes,
        temp=temp,
    )
    return session.id, pdf_path


# ---------------------------------------------------------------------------
# SSE parse helper unit tests (pure, no I/O)
# ---------------------------------------------------------------------------


def test_parse_sse_extracts_events() -> None:
    raw = (
        "event: stage_update\n"
        'data: {"stage": "extracting", "message": "Extracting text from PDF\u2026"}\n'
        "\n"
        "event: pipeline_complete\n"
        'data: {"session_id": "abc123", "total_detections": 2}\n'
        "\n"
    )
    events = _parse_sse(raw)
    assert len(events) == 2
    assert events[0]["event"] == "stage_update"
    assert events[1]["event"] == "pipeline_complete"
    assert events[1]["data"] == {"session_id": "abc123", "total_detections": 2}  # type: ignore[comparison-overlap]


def test_parse_sse_skips_comments() -> None:
    raw = ': keepalive\n\nevent: stage_update\ndata: {"stage": "extracting"}\n\n'
    events = _parse_sse(raw)
    assert len(events) == 1


# ---------------------------------------------------------------------------
# AC1 — 404 for unknown session
# ---------------------------------------------------------------------------


async def test_events_404_for_unknown_session(client: AsyncClient) -> None:
    resp = await client.get("/api/events/nonexistent")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# AC2 — Happy path: 3 stage_updates then pipeline_complete, session → reviewing
# ---------------------------------------------------------------------------


async def test_events_happy_path_streams_all_stages_and_complete(
    client: AsyncClient,
    uploading_session: tuple[str, Path],
) -> None:
    session_id, _ = uploading_session

    with (
        patch(_PATCH_EXTRACT, return_value=[_SAMPLE_BLOCK], create=True),
        patch(_PATCH_DETECT, return_value=[_SAMPLE_RAW_DETECTION], create=True),
        patch(_PATCH_VALIDATE, return_value=[_SAMPLE_DETECTION], create=True),
    ):
        async with client.stream("GET", f"/api/events/{session_id}") as resp:
            assert resp.status_code == 200
            raw = await resp.aread()

    events = _parse_sse(raw.decode())

    stage_updates = [e for e in events if e["event"] == "stage_update"]
    assert len(stage_updates) == 3, f"Expected 3 stage_update events, got: {stage_updates}"

    stages = [e["data"]["stage"] for e in stage_updates]  # type: ignore[index]
    assert stages == ["extracting", "detecting", "validating"]

    complete_events = [e for e in events if e["event"] == "pipeline_complete"]
    assert len(complete_events) == 1
    complete_data = complete_events[0]["data"]
    assert complete_data["session_id"] == session_id  # type: ignore[index]
    assert complete_data["total_detections"] == 1  # type: ignore[index]

    session = get_session(session_id)
    assert session.state == SessionState.REVIEWING


# ---------------------------------------------------------------------------
# AC3 — stage_update messages match spec (non-empty strings)
# ---------------------------------------------------------------------------


async def test_events_stage_update_messages(
    client: AsyncClient,
    uploading_session: tuple[str, Path],
) -> None:
    session_id, _ = uploading_session

    with (
        patch(_PATCH_EXTRACT, return_value=[_SAMPLE_BLOCK], create=True),
        patch(_PATCH_DETECT, return_value=[], create=True),
        patch(_PATCH_VALIDATE, return_value=[], create=True),
    ):
        async with client.stream("GET", f"/api/events/{session_id}") as resp:
            raw = await resp.aread()

    events = _parse_sse(raw.decode())
    stage_updates = [e for e in events if e["event"] == "stage_update"]
    assert len(stage_updates) == 3

    extracting, detecting, validating = stage_updates
    assert extracting["data"]["stage"] == "extracting"  # type: ignore[index]
    assert extracting["data"]["message"]  # type: ignore[index]
    assert detecting["data"]["stage"] == "detecting"  # type: ignore[index]
    assert detecting["data"]["message"]  # type: ignore[index]
    assert validating["data"]["stage"] == "validating"  # type: ignore[index]
    assert validating["data"]["message"]  # type: ignore[index]


# ---------------------------------------------------------------------------
# AC4 — Extraction failure → pipeline_error with stage "extracting", session → error
# ---------------------------------------------------------------------------


async def test_events_extraction_failure_emits_pipeline_error(
    client: AsyncClient,
    uploading_session: tuple[str, Path],
) -> None:
    session_id, _ = uploading_session

    with patch(_PATCH_EXTRACT, side_effect=PdfError("Failed to open PDF"), create=True):
        async with client.stream("GET", f"/api/events/{session_id}") as resp:
            assert resp.status_code == 200
            raw = await resp.aread()

    events = _parse_sse(raw.decode())

    stage_updates = [e for e in events if e["event"] == "stage_update"]
    assert len(stage_updates) >= 1
    assert stage_updates[0]["data"]["stage"] == "extracting"  # type: ignore[index]

    error_events = [e for e in events if e["event"] == "pipeline_error"]
    assert len(error_events) == 1
    error_data = error_events[0]["data"]
    assert error_data["stage"] == "extracting"  # type: ignore[index]
    assert "error" in error_data  # type: ignore[arg-type]

    session = get_session(session_id)
    assert session.state == SessionState.ERROR


# ---------------------------------------------------------------------------
# AC5 — Detection failure → pipeline_error with stage "detecting", session → error
# ---------------------------------------------------------------------------


async def test_events_detection_failure_emits_pipeline_error(
    client: AsyncClient,
    uploading_session: tuple[str, Path],
) -> None:
    session_id, _ = uploading_session

    with (
        patch(_PATCH_EXTRACT, return_value=[_SAMPLE_BLOCK], create=True),
        patch(_PATCH_DETECT, side_effect=DetectionError("NER inference failed"), create=True),
    ):
        async with client.stream("GET", f"/api/events/{session_id}") as resp:
            assert resp.status_code == 200
            raw = await resp.aread()

    events = _parse_sse(raw.decode())

    stage_updates = [e for e in events if e["event"] == "stage_update"]
    stages_seen = [e["data"]["stage"] for e in stage_updates]  # type: ignore[index]
    assert "extracting" in stages_seen
    assert "detecting" in stages_seen

    error_events = [e for e in events if e["event"] == "pipeline_error"]
    assert len(error_events) == 1
    assert error_events[0]["data"]["stage"] == "detecting"  # type: ignore[index]

    session = get_session(session_id)
    assert session.state == SessionState.ERROR


# ---------------------------------------------------------------------------
# AC6 — Zero detections: pipeline_complete with total_detections 0, session → reviewing
# ---------------------------------------------------------------------------


async def test_events_zero_detections_complete(
    client: AsyncClient,
    uploading_session: tuple[str, Path],
) -> None:
    session_id, _ = uploading_session

    with (
        patch(_PATCH_EXTRACT, return_value=[_SAMPLE_BLOCK], create=True),
        patch(_PATCH_DETECT, return_value=[], create=True),
        patch(_PATCH_VALIDATE, return_value=[], create=True),
    ):
        async with client.stream("GET", f"/api/events/{session_id}") as resp:
            raw = await resp.aread()

    events = _parse_sse(raw.decode())

    complete_events = [e for e in events if e["event"] == "pipeline_complete"]
    assert len(complete_events) == 1
    assert complete_events[0]["data"]["total_detections"] == 0  # type: ignore[index]

    session = get_session(session_id)
    assert session.state == SessionState.REVIEWING


# ---------------------------------------------------------------------------
# AC7 — 409 on duplicate pipeline run (session no longer in UPLOADING state)
# ---------------------------------------------------------------------------


async def test_events_409_on_duplicate_run(
    client: AsyncClient,
    uploading_session: tuple[str, Path],
) -> None:
    session_id, _ = uploading_session

    with (
        patch(_PATCH_EXTRACT, return_value=[_SAMPLE_BLOCK], create=True),
        patch(_PATCH_DETECT, return_value=[], create=True),
        patch(_PATCH_VALIDATE, return_value=[], create=True),
    ):
        async with client.stream("GET", f"/api/events/{session_id}") as resp:
            await resp.aread()

    # Session is now in REVIEWING state — second call must be rejected
    resp2 = await client.get(f"/api/events/{session_id}")
    assert resp2.status_code == 409
