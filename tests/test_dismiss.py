from __future__ import annotations

from collections.abc import Generator
from pathlib import Path
from unittest.mock import patch

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

import incognito.core.sessions as _sessions_module
from incognito.core.sessions import Session
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


def _detection(
    *, page: int = 1, start: int = 0, end: int = 11, entity_type: EntityType = EntityType.PERSON
) -> Detection:
    return Detection(
        text="Jean Dupont",
        entity_type=entity_type,
        page=page,
        start=start,
        end=end,
        bbox=_bbox(),
    )


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
# AC1 — DELETE returns 200 + {"status": "dismissed"}, GET confirms dismissed=true
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dismiss_marks_dismissed(client: AsyncClient) -> None:
    d = _detection()
    session = Session(id="sid_dismiss", state=SessionState.REVIEWING, detections=[d])
    _sessions_module._sessions["sid_dismiss"] = session

    resp = await client.delete(f"/api/detections/sid_dismiss/{d.id}")

    assert resp.status_code == 200
    assert resp.json() == {"status": "dismissed"}

    get_resp = await client.get("/api/detections/sid_dismiss")
    assert get_resp.status_code == 200
    items = get_resp.json()["detections"]
    assert len(items) == 1
    assert items[0]["id"] == d.id
    assert items[0]["dismissed"] is True


# ---------------------------------------------------------------------------
# AC4 — DELETE on already-dismissed detection returns 200 idempotently
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dismiss_idempotent(client: AsyncClient) -> None:
    d = Detection(
        text="Marie Curie",
        entity_type=EntityType.PERSON,
        page=1,
        start=0,
        end=11,
        bbox=_bbox(),
        dismissed=True,
    )
    session = Session(id="sid_idem", state=SessionState.REVIEWING, detections=[d])
    _sessions_module._sessions["sid_idem"] = session

    resp = await client.delete(f"/api/detections/sid_idem/{d.id}")

    assert resp.status_code == 200
    assert resp.json() == {"status": "dismissed"}


# ---------------------------------------------------------------------------
# 404 for unknown detection ID within a known session
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dismiss_unknown_detection_returns_404(client: AsyncClient) -> None:
    session = Session(id="sid_nodet", state=SessionState.REVIEWING, detections=[])
    _sessions_module._sessions["sid_nodet"] = session

    resp = await client.delete("/api/detections/sid_nodet/nonexistent_id")

    assert resp.status_code == 404
    body = resp.json()
    assert "error" in body


# ---------------------------------------------------------------------------
# 404 for unknown session
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dismiss_unknown_session_returns_404(client: AsyncClient) -> None:
    resp = await client.delete("/api/detections/ghost_session/some_detection_id")

    assert resp.status_code == 404
    body = resp.json()
    assert body.get("error") == "Session not found"


# ---------------------------------------------------------------------------
# 409 when session is still in PROCESSING state
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dismiss_during_processing_returns_409(client: AsyncClient) -> None:
    d = _detection()
    session = Session(id="sid_proc", state=SessionState.PROCESSING, detections=[d])
    _sessions_module._sessions["sid_proc"] = session

    resp = await client.delete(f"/api/detections/sid_proc/{d.id}")

    assert resp.status_code == 409


# ---------------------------------------------------------------------------
# AC2 — active (non-dismissed) count decreases after dismiss
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dismiss_active_count_decreases(client: AsyncClient) -> None:
    d1 = _detection(page=1, start=0, end=5)
    d2 = _detection(page=1, start=10, end=20)
    d3 = _detection(page=2, start=0, end=8)
    session = Session(id="sid_count", state=SessionState.REVIEWING, detections=[d1, d2, d3])
    _sessions_module._sessions["sid_count"] = session

    resp = await client.delete(f"/api/detections/sid_count/{d1.id}")
    assert resp.status_code == 200

    get_resp = await client.get("/api/detections/sid_count")
    assert get_resp.status_code == 200
    items = get_resp.json()["detections"]
    active = [item for item in items if not item["dismissed"]]
    assert len(active) == 2
