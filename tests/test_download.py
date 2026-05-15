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
from incognito.core.tempfiles import TempFileManager
from incognito.models import BBox, Detection, EntityType, SessionState

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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


def _reviewing_session_with_pdf(
    session_id: str = "sid_download",
    pii: str = "Jean Dupont",
    safe: str = "Republique Francaise",
    original_filename: str = "",
) -> tuple[Session, Detection]:
    text = f"{pii} {safe}"

    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text, fontsize=12)
    pdf_bytes = doc.tobytes()
    doc.close()

    temp = TempFileManager()
    pdf_path = temp.create_file("upload.pdf")
    pdf_path.write_bytes(pdf_bytes)

    doc2 = fitz.open(str(pdf_path))
    rects = doc2[0].search_for(pii)
    doc2.close()
    assert rects, f"text '{pii}' not found in generated PDF"
    r = rects[0]

    det = Detection(
        text=pii,
        entity_type=EntityType.PERSON,
        page=0,
        start=0,
        end=len(pii),
        bbox=BBox(x=r.x0, y=r.y0, width=r.x1 - r.x0, height=r.y1 - r.y0),
    )

    session = Session(
        id=session_id,
        state=SessionState.REVIEWING,
        pdf_path=pdf_path,
        original_pdf_bytes=pdf_bytes,
        temp=temp,
        detections=[det],
        original_filename=original_filename,
    )
    return session, det


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


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
# FR24: Content-Disposition filename = {original_stem}_redacted.pdf
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_download_filename_contains_original_stem(client: AsyncClient) -> None:
    session, _ = _reviewing_session_with_pdf(
        session_id="sid_filename",
        original_filename="rapport_medical.pdf",
    )
    _sessions_module._sessions[session.id] = session

    resp = await client.post(f"/api/redact/{session.id}", json={"mode": "irreversible"})

    assert resp.status_code == 200
    content_disposition = resp.headers.get("content-disposition", "")
    assert "rapport_medical_redacted.pdf" in content_disposition


# ---------------------------------------------------------------------------
# FR24: Fallback filename when original_filename is empty
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_download_fallback_filename_when_no_original(client: AsyncClient) -> None:
    session, _ = _reviewing_session_with_pdf(
        session_id="sid_fallback",
        original_filename="",
    )
    _sessions_module._sessions[session.id] = session

    resp = await client.post(f"/api/redact/{session.id}", json={"mode": "irreversible"})

    assert resp.status_code == 200
    content_disposition = resp.headers.get("content-disposition", "")
    assert "redacted.pdf" in content_disposition


# ---------------------------------------------------------------------------
# FR24 regression: original PDF bytes are byte-identical after redaction
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_original_pdf_untouched_after_redaction(client: AsyncClient) -> None:
    session, _ = _reviewing_session_with_pdf(
        session_id="sid_original",
        original_filename="source.pdf",
    )
    original_bytes = session.original_pdf_bytes
    _sessions_module._sessions[session.id] = session

    resp = await client.post(f"/api/redact/{session.id}", json={"mode": "irreversible"})

    assert resp.status_code == 200
    assert session.original_pdf_bytes == original_bytes


# ---------------------------------------------------------------------------
# FR26 / NFR8: temp directory deleted after download
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_temp_files_cleaned_after_download(client: AsyncClient) -> None:
    session, _ = _reviewing_session_with_pdf(
        session_id="sid_cleanup_temp",
        original_filename="doc.pdf",
    )
    assert session.temp is not None
    temp_root = session.temp.root
    assert temp_root.exists()
    _sessions_module._sessions[session.id] = session

    resp = await client.post(f"/api/redact/{session.id}", json={"mode": "irreversible"})

    assert resp.status_code == 200
    assert not temp_root.exists()


# ---------------------------------------------------------------------------
# FR26 / NFR8: session removed from store after download
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_session_removed_after_download(client: AsyncClient) -> None:
    session, _ = _reviewing_session_with_pdf(
        session_id="sid_cleanup_session",
        original_filename="doc.pdf",
    )
    _sessions_module._sessions[session.id] = session

    resp = await client.post(f"/api/redact/{session.id}", json={"mode": "irreversible"})

    assert resp.status_code == 200
    assert session.id not in _sessions_module._sessions
