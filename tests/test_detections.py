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
    *, page: int, start: int, end: int, entity_type: EntityType = EntityType.PERSON
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
# AC1 — returns JSON array with required fields for completed detection session
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_detections_returns_array_with_required_fields(client: AsyncClient) -> None:
    d = _detection(page=1, start=0, end=11)
    session = Session(id="abc123", state=SessionState.REVIEWING, detections=[d])
    _sessions_module._sessions["abc123"] = session

    resp = await client.get("/api/detections/abc123")

    assert resp.status_code == 200
    body = resp.json()
    assert "detections" in body
    items = body["detections"]
    assert len(items) == 1
    item = items[0]
    for key in ("id", "text", "entity_type", "page", "start", "end", "bbox", "dismissed"):
        assert key in item, f"Missing key: {key}"
    assert item["id"] == d.id
    assert item["text"] == "Jean Dupont"
    assert item["entity_type"] == "person"
    assert item["page"] == 1
    assert item["start"] == 0
    assert item["end"] == 11
    assert item["dismissed"] is False
    assert item["bbox"] == {"x": 10.0, "y": 20.0, "width": 100.0, "height": 15.0}


# ---------------------------------------------------------------------------
# AC2 — detections ordered by page then by position within page
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_detections_ordered_by_page_then_start(client: AsyncClient) -> None:
    d1 = _detection(page=2, start=50, end=60)
    d2 = _detection(page=1, start=80, end=90)
    d3 = _detection(page=1, start=10, end=20)
    session = Session(id="sid_order", state=SessionState.REVIEWING, detections=[d1, d2, d3])
    _sessions_module._sessions["sid_order"] = session

    resp = await client.get("/api/detections/sid_order")

    assert resp.status_code == 200
    items = resp.json()["detections"]
    assert len(items) == 3
    pages = [i["page"] for i in items]
    assert pages == sorted(pages), f"Pages not sorted: {pages}"
    page1_items = [i for i in items if i["page"] == 1]
    starts = [i["start"] for i in page1_items]
    assert starts == sorted(starts), f"Start offsets not sorted within page: {starts}"


# ---------------------------------------------------------------------------
# AC3 — 404 for unknown or expired session ID
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_detections_unknown_session_returns_404(client: AsyncClient) -> None:
    resp = await client.get("/api/detections/does_not_exist")

    assert resp.status_code == 404
    body = resp.json()
    assert body.get("error") == "Session not found"


# ---------------------------------------------------------------------------
# Additional failure mode — 409 while pipeline is running
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_detections_returns_409_while_processing(client: AsyncClient) -> None:
    session = Session(id="sid_proc", state=SessionState.PROCESSING, detections=[])
    _sessions_module._sessions["sid_proc"] = session

    resp = await client.get("/api/detections/sid_proc")

    assert resp.status_code == 409


# ---------------------------------------------------------------------------
# Additional failure mode — 200 with empty list when session has no detections
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_detections_empty_list_valid_when_reviewing(client: AsyncClient) -> None:
    session = Session(id="sid_empty", state=SessionState.REVIEWING, detections=[])
    _sessions_module._sessions["sid_empty"] = session

    resp = await client.get("/api/detections/sid_empty")

    assert resp.status_code == 200
    body = resp.json()
    assert "detections" in body
    assert body["detections"] == []
