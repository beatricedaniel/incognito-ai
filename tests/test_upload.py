from __future__ import annotations

import stat
from pathlib import Path
from unittest.mock import patch

import fitz
import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from incognito.core.config import TEMP_PREFIX
from incognito.core.sessions import get_session

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_pdf() -> bytes:
    doc = fitz.open()
    doc.new_page()
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


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def pdf_bytes() -> bytes:
    return _make_pdf()


@pytest.fixture
def app(tmp_path: Path) -> FastAPI:
    return _make_app(tmp_path)


@pytest_asyncio.fixture()
async def client(app: FastAPI) -> AsyncClient:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture()
async def uploaded_session_id(client: AsyncClient, pdf_bytes: bytes) -> str:
    with (
        patch("incognito.api.routes.extract_blocks", return_value=[], create=True),
        patch("incognito.api.routes.detect_entities", return_value=[], create=True),
        patch("incognito.api.routes.validate_detections", return_value=[], create=True),
    ):
        resp = await client.post(
            "/api/upload",
            files={"file": ("test.pdf", pdf_bytes, "application/pdf")},
        )
    assert resp.status_code == 201
    return resp.json()["session_id"]


# ---------------------------------------------------------------------------
# AC3 — upload creates session, stores PDF in secure temp dir, returns session_id
# ---------------------------------------------------------------------------


async def test_upload_returns_session_id_and_events_url(
    client: AsyncClient, pdf_bytes: bytes
) -> None:
    with (
        patch("incognito.api.routes.extract_blocks", return_value=[], create=True),
        patch("incognito.api.routes.detect_entities", return_value=[], create=True),
        patch("incognito.api.routes.validate_detections", return_value=[], create=True),
    ):
        resp = await client.post(
            "/api/upload",
            files={"file": ("test.pdf", pdf_bytes, "application/pdf")},
        )

    assert resp.status_code == 201
    body = resp.json()
    assert "session_id" in body
    session_id = body["session_id"]
    assert isinstance(session_id, str)
    assert session_id
    assert "events_url" in body
    assert body["events_url"] == f"/api/events/{session_id}"


async def test_upload_saves_pdf_to_temp_dir(client: AsyncClient, pdf_bytes: bytes) -> None:
    with (
        patch("incognito.api.routes.extract_blocks", return_value=[], create=True),
        patch("incognito.api.routes.detect_entities", return_value=[], create=True),
        patch("incognito.api.routes.validate_detections", return_value=[], create=True),
    ):
        resp = await client.post(
            "/api/upload",
            files={"file": ("test.pdf", pdf_bytes, "application/pdf")},
        )

    assert resp.status_code == 201
    session_id = resp.json()["session_id"]
    session = get_session(session_id)

    assert session.pdf_path is not None
    assert session.pdf_path.exists()
    temp_dir = session.pdf_path.parent
    assert temp_dir.name.startswith(TEMP_PREFIX)
    perms = stat.S_IMODE(temp_dir.stat().st_mode)
    assert perms == 0o700, f"Expected 0o700, got {oct(perms)}"


async def test_upload_rejects_non_pdf(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/upload",
        files={"file": ("note.txt", b"not a pdf", "text/plain")},
    )

    assert resp.status_code not in (200, 201)


# ---------------------------------------------------------------------------
# AC4 — original PDF bytes stored in session; cleanup removes temp files
# ---------------------------------------------------------------------------


async def test_upload_stores_original_pdf_bytes_in_session(
    client: AsyncClient, pdf_bytes: bytes
) -> None:
    with (
        patch("incognito.api.routes.extract_blocks", return_value=[], create=True),
        patch("incognito.api.routes.detect_entities", return_value=[], create=True),
        patch("incognito.api.routes.validate_detections", return_value=[], create=True),
    ):
        resp = await client.post(
            "/api/upload",
            files={"file": ("test.pdf", pdf_bytes, "application/pdf")},
        )

    assert resp.status_code == 201
    session_id = resp.json()["session_id"]
    session = get_session(session_id)

    assert hasattr(
        session, "original_pdf_bytes"
    ), "Session must have 'original_pdf_bytes' field (AC4)"
    assert session.original_pdf_bytes == pdf_bytes


async def test_session_cleanup_removes_temp_files(
    uploaded_session_id: str,
) -> None:
    session = get_session(uploaded_session_id)
    assert session.pdf_path is not None
    temp_dir = session.pdf_path.parent

    assert hasattr(session, "temp"), "Session must have 'temp' (TempFileManager) field (AC4)"
    session.temp.cleanup()

    assert not temp_dir.exists(), f"Temp dir {temp_dir} should be gone after cleanup"


# ---------------------------------------------------------------------------
# AC5 — SSE endpoint streams events; 404 for unknown session
# ---------------------------------------------------------------------------


async def test_events_endpoint_returns_sse_stream(
    client: AsyncClient, uploaded_session_id: str
) -> None:
    async with client.stream("GET", f"/api/events/{uploaded_session_id}") as resp:
        assert resp.status_code == 200
        content_type = resp.headers.get("content-type", "")
        assert "text/event-stream" in content_type


async def test_events_endpoint_404_for_unknown_session(client: AsyncClient) -> None:
    resp = await client.get("/api/events/nonexistent-session-id")
    assert resp.status_code == 404
