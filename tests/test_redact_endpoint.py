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
from incognito.core.exceptions import RedactionError
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


def _bbox() -> BBox:
    return BBox(x=10.0, y=20.0, width=100.0, height=15.0)


def _detection(*, dismissed: bool = False) -> Detection:
    return Detection(
        text="Jean Dupont",
        entity_type=EntityType.PERSON,
        page=0,
        start=0,
        end=11,
        bbox=_bbox(),
        dismissed=dismissed,
    )


def _reviewing_session_with_pdf(
    pii: str = "Jean Dupont",
    safe: str = "Republique Francaise",
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
        id="sid_redact",
        state=SessionState.REVIEWING,
        pdf_path=pdf_path,
        original_pdf_bytes=pdf_bytes,
        temp=temp,
        detections=[det],
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
# 404 — unknown session
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_redact_unknown_session_returns_404(client: AsyncClient) -> None:
    resp = await client.post("/api/redact/ghost_session", json={"mode": "irreversible"})

    assert resp.status_code == 404
    assert resp.json().get("error") == "Session not found"


# ---------------------------------------------------------------------------
# 409 — wrong session state
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_redact_wrong_state_returns_409(client: AsyncClient) -> None:
    session = Session(id="sid_proc", state=SessionState.PROCESSING, detections=[_detection()])
    _sessions_module._sessions["sid_proc"] = session

    resp = await client.post("/api/redact/sid_proc", json={"mode": "irreversible"})

    assert resp.status_code == 409


# ---------------------------------------------------------------------------
# 409 — all detections dismissed
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_redact_all_dismissed_returns_409(client: AsyncClient) -> None:
    d = _detection(dismissed=True)
    session = Session(id="sid_all_dismissed", state=SessionState.REVIEWING, detections=[d])
    _sessions_module._sessions["sid_all_dismissed"] = session

    resp = await client.post("/api/redact/sid_all_dismissed", json={"mode": "irreversible"})

    assert resp.status_code == 409
    body = resp.json()
    assert "No detections" in body.get("error", "") or "No detections" in body.get("detail", "")


# ---------------------------------------------------------------------------
# 400 — reversible with passphrase too short
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_redact_reversible_short_passphrase_returns_400(client: AsyncClient) -> None:
    session, _ = _reviewing_session_with_pdf()
    _sessions_module._sessions[session.id] = session

    resp = await client.post(
        f"/api/redact/{session.id}",
        json={"mode": "reversible", "passphrase": "short"},
    )

    assert resp.status_code == 400
    body_str = str(resp.json()).lower()
    assert "passphrase" in body_str


# ---------------------------------------------------------------------------
# 400 — reversible with passphrase missing
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_redact_reversible_missing_passphrase_returns_400(client: AsyncClient) -> None:
    session, _ = _reviewing_session_with_pdf()
    _sessions_module._sessions[session.id] = session

    resp = await client.post(
        f"/api/redact/{session.id}",
        json={"mode": "reversible"},
    )

    assert resp.status_code == 400
    body_str = str(resp.json()).lower()
    assert "passphrase" in body_str


# ---------------------------------------------------------------------------
# 500 — reversible with valid passphrase (not yet implemented)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_redact_reversible_valid_passphrase_returns_pdfkey(
    client: AsyncClient,
) -> None:
    session, _ = _reviewing_session_with_pdf()
    _sessions_module._sessions[session.id] = session

    resp = await client.post(
        f"/api/redact/{session.id}",
        json={"mode": "reversible", "passphrase": "a]b2c3d4e5f6g"},
    )

    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert ".pdfkey" in resp.headers.get("content-disposition", "")


# ---------------------------------------------------------------------------
# 200 — irreversible happy path returns PDF bytes
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_redact_irreversible_returns_pdf(client: AsyncClient) -> None:
    session, _ = _reviewing_session_with_pdf()
    _sessions_module._sessions[session.id] = session

    resp = await client.post(
        f"/api/redact/{session.id}",
        json={"mode": "irreversible"},
    )

    assert resp.status_code == 200
    assert "application/pdf" in resp.headers.get("content-type", "")
    assert resp.content[:5] == b"%PDF-"


# ---------------------------------------------------------------------------
# 200 — no JSON body defaults to irreversible
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_redact_no_body_defaults_to_irreversible(client: AsyncClient) -> None:
    session, _ = _reviewing_session_with_pdf()
    _sessions_module._sessions[session.id] = session

    resp = await client.post(f"/api/redact/{session.id}")

    assert resp.status_code == 200
    assert "application/pdf" in resp.headers.get("content-type", "")
    assert resp.content[:5] == b"%PDF-"


# ---------------------------------------------------------------------------
# Dismissed detections filtered: active PII removed, dismissed PII kept
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_redact_filters_out_dismissed_detections(client: AsyncClient) -> None:
    pii_active = "Jean Dupont"
    pii_dismissed = "Marie Curie"
    text = f"{pii_active} {pii_dismissed} Republique Francaise"

    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text, fontsize=12)
    pdf_bytes = doc.tobytes()
    doc.close()

    temp = TempFileManager()
    pdf_path = temp.create_file("upload.pdf")
    pdf_path.write_bytes(pdf_bytes)

    doc2 = fitz.open(str(pdf_path))
    rects_active = doc2[0].search_for(pii_active)
    rects_dismissed = doc2[0].search_for(pii_dismissed)
    doc2.close()
    assert rects_active
    assert rects_dismissed

    ra = rects_active[0]
    rd = rects_dismissed[0]

    det_active = Detection(
        text=pii_active,
        entity_type=EntityType.PERSON,
        page=0,
        start=0,
        end=len(pii_active),
        bbox=BBox(x=ra.x0, y=ra.y0, width=ra.x1 - ra.x0, height=ra.y1 - ra.y0),
        dismissed=False,
    )
    det_dismissed = Detection(
        text=pii_dismissed,
        entity_type=EntityType.PERSON,
        page=0,
        start=len(pii_active) + 1,
        end=len(pii_active) + 1 + len(pii_dismissed),
        bbox=BBox(x=rd.x0, y=rd.y0, width=rd.x1 - rd.x0, height=rd.y1 - rd.y0),
        dismissed=True,
    )

    session = Session(
        id="sid_filter",
        state=SessionState.REVIEWING,
        pdf_path=pdf_path,
        original_pdf_bytes=pdf_bytes,
        temp=temp,
        detections=[det_active, det_dismissed],
    )
    _sessions_module._sessions["sid_filter"] = session

    resp = await client.post("/api/redact/sid_filter", json={"mode": "irreversible"})

    assert resp.status_code == 200
    assert resp.content[:5] == b"%PDF-"

    result_doc = fitz.open(stream=resp.content, filetype="pdf")
    full_text = "".join(result_doc[i].get_text() for i in range(len(result_doc)))
    result_doc.close()

    assert pii_active not in full_text
    assert pii_dismissed in full_text


# ---------------------------------------------------------------------------
# State machine: session becomes COMPLETE after successful redaction
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_redact_cleans_up_session_on_success(client: AsyncClient) -> None:
    session, _ = _reviewing_session_with_pdf()
    _sessions_module._sessions[session.id] = session

    resp = await client.post(
        f"/api/redact/{session.id}",
        json={"mode": "irreversible"},
    )

    assert resp.status_code == 200
    assert session.id not in _sessions_module._sessions


# ---------------------------------------------------------------------------
# Error path: redact_pdf raises RedactionError → session state becomes ERROR
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_redact_state_rolls_back_on_failure(client: AsyncClient) -> None:
    session, _ = _reviewing_session_with_pdf()
    _sessions_module._sessions[session.id] = session

    with patch(
        "incognito.api.routes.redact_pdf",
        side_effect=RedactionError("simulated failure"),
    ):
        resp = await client.post(
            f"/api/redact/{session.id}",
            json={"mode": "irreversible"},
        )

    assert resp.status_code == 500
    assert _sessions_module._sessions[session.id].state == SessionState.ERROR
