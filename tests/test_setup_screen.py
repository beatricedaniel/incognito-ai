from __future__ import annotations

from pathlib import Path
from typing import Final
from unittest.mock import MagicMock, patch

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

_TAGS_URL: Final[str] = "http://127.0.0.1:11434/api/tags"


def _mock_response(body: dict[str, object], status_code: int = 200) -> MagicMock:
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = body
    resp.raise_for_status = MagicMock()
    return resp


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


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    return TestClient(_make_app(tmp_path))


# ---------------------------------------------------------------------------
# test_status_returns_structured_dict
# ---------------------------------------------------------------------------


def test_status_returns_structured_dict(client: TestClient) -> None:
    resp_mock = _mock_response({"models": [{"name": "gemma4:e4b"}]})
    with patch("incognito.ollama.manager.httpx.get", return_value=resp_mock):
        resp = client.get("/api/status")

    assert resp.status_code == 200
    body = resp.json()
    assert "ollama_reachable" in body
    assert "model_ready" in body
    assert "model" in body
    assert isinstance(body["ollama_reachable"], bool)
    assert isinstance(body["model_ready"], bool)
    assert isinstance(body["model"], str)


# ---------------------------------------------------------------------------
# test_status_ollama_unreachable
# ---------------------------------------------------------------------------


def test_status_ollama_unreachable(client: TestClient) -> None:
    with patch(
        "incognito.ollama.manager.httpx.get",
        side_effect=httpx.ConnectError("Connection refused"),
    ):
        resp = client.get("/api/status")

    assert resp.status_code == 200
    body = resp.json()
    assert body["ollama_reachable"] is False
    assert body["model_ready"] is False


# ---------------------------------------------------------------------------
# test_status_ollama_reachable_model_missing
# ---------------------------------------------------------------------------


def test_status_ollama_reachable_model_missing(client: TestClient) -> None:
    resp_mock = _mock_response({"models": []})
    with patch("incognito.ollama.manager.httpx.get", return_value=resp_mock):
        resp = client.get("/api/status")

    assert resp.status_code == 200
    body = resp.json()
    assert body["ollama_reachable"] is True
    assert body["model_ready"] is False


# ---------------------------------------------------------------------------
# test_status_both_ready
# ---------------------------------------------------------------------------


def test_status_both_ready(client: TestClient) -> None:
    resp_mock = _mock_response({"models": [{"name": "gemma4:e4b:latest"}]})
    with patch("incognito.ollama.manager.httpx.get", return_value=resp_mock):
        resp = client.get("/api/status")

    assert resp.status_code == 200
    body = resp.json()
    assert body["ollama_reachable"] is True
    assert body["model_ready"] is True
    assert body["model"] == "gemma4:e4b"
