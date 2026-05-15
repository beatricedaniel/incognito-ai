from __future__ import annotations

from collections.abc import Generator
from pathlib import Path
from unittest.mock import patch

import fitz
import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

import incognito.core.sessions as _sessions_module
from incognito.core.sessions import Session
from incognito.models import SessionState

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_pdf() -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Sample text for testing.")
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


@pytest.fixture(autouse=True)
def _clean_sessions() -> Generator[None]:
    _sessions_module._sessions.clear()
    yield
    _sessions_module._sessions.clear()


# ---------------------------------------------------------------------------
# GET /api/pdf/{session_id} — returns PDF bytes for reviewing session
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_pdf_returns_bytes_when_reviewing(client: AsyncClient, pdf_bytes: bytes) -> None:
    session = Session(
        id="sid_review",
        state=SessionState.REVIEWING,
        original_pdf_bytes=pdf_bytes,
    )
    _sessions_module._sessions["sid_review"] = session

    resp = await client.get("/api/pdf/sid_review")

    assert resp.status_code == 200
    assert resp.content == pdf_bytes


@pytest.mark.asyncio
async def test_get_pdf_content_type_is_application_pdf(
    client: AsyncClient, pdf_bytes: bytes
) -> None:
    session = Session(
        id="sid_ct",
        state=SessionState.REVIEWING,
        original_pdf_bytes=pdf_bytes,
    )
    _sessions_module._sessions["sid_ct"] = session

    resp = await client.get("/api/pdf/sid_ct")

    assert resp.headers["content-type"] == "application/pdf"


@pytest.mark.asyncio
async def test_get_pdf_cache_control_no_store(client: AsyncClient, pdf_bytes: bytes) -> None:
    session = Session(
        id="sid_cache",
        state=SessionState.REVIEWING,
        original_pdf_bytes=pdf_bytes,
    )
    _sessions_module._sessions["sid_cache"] = session

    resp = await client.get("/api/pdf/sid_cache")

    assert resp.headers["cache-control"] == "no-store"


# ---------------------------------------------------------------------------
# 409 — pipeline not yet complete
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_pdf_returns_409_while_processing(client: AsyncClient) -> None:
    session = Session(id="sid_proc", state=SessionState.PROCESSING)
    _sessions_module._sessions["sid_proc"] = session

    resp = await client.get("/api/pdf/sid_proc")

    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_get_pdf_returns_409_while_uploading(client: AsyncClient) -> None:
    session = Session(id="sid_up", state=SessionState.UPLOADING)
    _sessions_module._sessions["sid_up"] = session

    resp = await client.get("/api/pdf/sid_up")

    assert resp.status_code == 409


# ---------------------------------------------------------------------------
# 404 — unknown session
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_pdf_returns_404_for_unknown_session(client: AsyncClient) -> None:
    resp = await client.get("/api/pdf/does_not_exist")

    assert resp.status_code == 404
    body = resp.json()
    assert body.get("error") == "Session not found"
