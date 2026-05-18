from __future__ import annotations

import time
from pathlib import Path
from typing import Final
from unittest.mock import patch

import pytest
import pytest_asyncio
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from httpx import ASGITransport, AsyncClient

from incognito.core.exceptions import (
    DetectionError,
    IncognitoError,
    OllamaError,
    PdfError,
    RecoveryError,
    RedactionError,
    SessionError,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_EXPECTED_ROUTES: Final[list[tuple[str, str]]] = [
    ("GET", "/api/status"),
    ("POST", "/api/upload"),
    ("GET", "/api/events/{session_id}"),
    ("GET", "/api/detections/{session_id}"),
    ("DELETE", "/api/detections/{session_id}/{detection_id}"),
    ("POST", "/api/redact/{session_id}"),
    ("POST", "/api/recover"),
]


def _make_app(tmp_path: Path) -> FastAPI:
    """Create the app with a real static dir so StaticFiles doesn't crash."""
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
def app(tmp_path: Path) -> FastAPI:
    return _make_app(tmp_path)


@pytest_asyncio.fixture()
async def client(app: FastAPI) -> AsyncClient:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


# ---------------------------------------------------------------------------
# AC2 — GET /api/status returns structured status dict
# ---------------------------------------------------------------------------

_STATUS_READY: Final[dict[str, object]] = {
    "ollama_reachable": True,
    "model_ready": True,
    "model": "gemma4:e4b",
}
_STATUS_DOWN: Final[dict[str, object]] = {
    "ollama_reachable": False,
    "model_ready": False,
    "model": "gemma4:e4b",
}


@pytest.mark.asyncio
async def test_status_returns_ollama_ready_true(client: AsyncClient) -> None:
    with patch("incognito.api.routes.check_status", return_value=_STATUS_READY):
        resp = await client.get("/api/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ollama_reachable"] is True
    assert body["model_ready"] is True
    assert body["model"] == "gemma4:e4b"


@pytest.mark.asyncio
async def test_status_returns_ollama_ready_false(client: AsyncClient) -> None:
    with patch("incognito.api.routes.check_status", return_value=_STATUS_DOWN):
        resp = await client.get("/api/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ollama_reachable"] is False
    assert body["model_ready"] is False


@pytest.mark.asyncio
async def test_status_has_no_legacy_status_key(client: AsyncClient) -> None:
    with patch("incognito.api.routes.check_status", return_value=_STATUS_READY):
        resp = await client.get("/api/status")
    assert "status" not in resp.json()


# ---------------------------------------------------------------------------
# AC3 — 7 routes registered
# ---------------------------------------------------------------------------


def test_all_seven_routes_registered(app: FastAPI) -> None:
    registered: set[tuple[str, str]] = set()
    for route in app.routes:
        path = getattr(route, "path", None)
        methods = getattr(route, "methods", None)
        if path and methods:
            for method in methods:
                registered.add((method.upper(), path))

    for method, path in _EXPECTED_ROUTES:
        assert (method, path) in registered, f"{method} {path} not registered"


def test_exactly_eight_api_routes(app: FastAPI) -> None:
    api_routes: list[tuple[str, str]] = []
    for route in app.routes:
        path = getattr(route, "path", None)
        methods = getattr(route, "methods", None)
        if path and methods and path.startswith("/api/"):
            for method in methods:
                api_routes.append((method.upper(), path))
    assert len(api_routes) == 8, f"Expected 8 API routes, found {len(api_routes)}: {api_routes}"


def test_events_route_registered(app: FastAPI) -> None:
    paths = {getattr(r, "path", "") for r in app.routes}
    assert "/api/events/{session_id}" in paths


def test_recover_route_registered(app: FastAPI) -> None:
    paths = {getattr(r, "path", "") for r in app.routes}
    assert "/api/recover" in paths


# ---------------------------------------------------------------------------
# AC4 — create_app() completes in under 5 seconds
# ---------------------------------------------------------------------------


def test_create_app_startup_time(tmp_path: Path) -> None:
    start = time.monotonic()
    _make_app(tmp_path)
    elapsed = time.monotonic() - start
    assert elapsed < 5.0, f"create_app() took {elapsed:.2f}s, expected < 5s"


# ---------------------------------------------------------------------------
# AC5 — IncognitoError subclasses caught and returned as structured JSON
# ---------------------------------------------------------------------------


def _make_app_with_probe(tmp_path: Path, exc_class: type[IncognitoError]) -> FastAPI:
    """Create app with a probe route registered before the static mount."""
    static_dir = tmp_path / "static"
    static_dir.mkdir(exist_ok=True)
    (static_dir / "index.html").write_text("<html></html>")

    # We build the app manually so the probe route sits in the router
    # before StaticFiles swallows everything under "/".
    from fastapi import FastAPI as _FastAPI
    from fastapi.staticfiles import StaticFiles as _StaticFiles

    from incognito.api.routes import router as _router
    from incognito.core.exceptions import IncognitoError as _IncognitoError

    app = _FastAPI()

    @app.exception_handler(_IncognitoError)
    async def _handler(request: Request, exc: _IncognitoError) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content={"error": type(exc).__name__, "detail": str(exc)},
        )

    app.include_router(_router)

    # Probe route must come before the static mount
    @app.get("/api/probe/error")
    async def _probe(request: Request) -> JSONResponse:
        raise exc_class("test message")

    app.mount("/", _StaticFiles(directory=static_dir, html=True), name="static")
    return app


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "exc_class",
    [
        IncognitoError,
        PdfError,
        DetectionError,
        RedactionError,
        OllamaError,
        SessionError,
        RecoveryError,
    ],
)
async def test_incognito_error_handler_returns_structured_json(
    tmp_path: Path, exc_class: type[IncognitoError]
) -> None:
    app = _make_app_with_probe(tmp_path, exc_class)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/probe/error")

    assert resp.status_code == 500
    body = resp.json()
    assert "error" in body, f"Missing 'error' key in {body}"
    assert "detail" in body, f"Missing 'detail' key in {body}"
    assert body["detail"] == "test message"
    assert body["error"] == exc_class.__name__


@pytest.mark.asyncio
async def test_incognito_error_handler_does_not_leak_raw_exception(
    tmp_path: Path,
) -> None:
    app = _make_app_with_probe(tmp_path, PdfError)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/probe/error")

    body = resp.json()
    assert isinstance(body, dict)
    assert resp.status_code == 500


# ---------------------------------------------------------------------------
# AC1 — main.run() delegates to uvicorn (unit, no real server)
# ---------------------------------------------------------------------------


def test_run_passes_factory_true_to_uvicorn() -> None:
    captured: dict[str, object] = {}

    def _fake_uvicorn(*args: object, **kwargs: object) -> None:
        captured.update(kwargs)

    with patch("incognito.main.uvicorn.run", side_effect=_fake_uvicorn):
        from incognito.main import run

        run()

    assert captured.get("factory") is True


def test_run_binds_to_localhost() -> None:
    captured: dict[str, object] = {}

    def _fake_uvicorn(*args: object, **kwargs: object) -> None:
        captured.update(kwargs)

    with patch("incognito.main.uvicorn.run", side_effect=_fake_uvicorn):
        from incognito.main import run

        run()

    assert captured.get("host") == "127.0.0.1"
