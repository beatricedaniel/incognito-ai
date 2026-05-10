from __future__ import annotations

import logging
from typing import Any
from unittest.mock import MagicMock, patch

import httpx
import pytest

from incognito.core.exceptions import OllamaError
from incognito.ollama import manager

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NON_LOCALHOST: str = "192.168.1.1"


def _mock_response(body: dict[str, Any], status_code: int = 200) -> MagicMock:
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = body
    resp.raise_for_status = MagicMock()
    return resp


def _mock_response_text(text: str, status_code: int = 200) -> MagicMock:
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.text = text
    resp.json.side_effect = ValueError("not valid JSON")
    resp.raise_for_status = MagicMock()
    return resp


# ---------------------------------------------------------------------------
# AC1 — generate returns the response field text
# ---------------------------------------------------------------------------


def test_generate_returns_response_text() -> None:
    resp = _mock_response({"response": "Jean Dupont détecté"})
    with patch("httpx.post", return_value=resp) as mock_post:
        result = manager.generate("Trouve les PII", system="Tu es un détecteur de PII")
        assert result == "Jean Dupont détecté"
        mock_post.assert_called_once()


# ---------------------------------------------------------------------------
# AC1 — system message included in POST payload
# ---------------------------------------------------------------------------


def test_generate_sends_system_message_in_payload() -> None:
    resp = _mock_response({"response": "ok"})
    with patch("httpx.post", return_value=resp) as mock_post:
        manager.generate("prompt text", system="You are a PII detector")
        _, kwargs = mock_post.call_args
        payload: dict[str, Any] = kwargs["json"]
        assert "system" in payload
        assert payload["system"] == "You are a PII detector"


# ---------------------------------------------------------------------------
# AC1 — system key absent when system not provided
# ---------------------------------------------------------------------------


def test_generate_omits_system_key_when_not_provided() -> None:
    resp = _mock_response({"response": "ok"})
    with patch("httpx.post", return_value=resp) as mock_post:
        manager.generate("prompt text")
        _, kwargs = mock_post.call_args
        payload: dict[str, Any] = kwargs["json"]
        assert "system" not in payload


# ---------------------------------------------------------------------------
# AC2 — OllamaError on HTTP status error (4xx/5xx)
# ---------------------------------------------------------------------------


def test_generate_raises_ollama_error_on_http_status_error() -> None:
    http_err = httpx.HTTPStatusError(
        "500 Internal Server Error",
        request=MagicMock(),
        response=MagicMock(),
    )
    resp = _mock_response({}, status_code=500)
    resp.raise_for_status.side_effect = http_err
    with patch("httpx.post", return_value=resp), pytest.raises(OllamaError):
        manager.generate("any prompt")


# ---------------------------------------------------------------------------
# AC2 — OllamaError on connection refused
# ---------------------------------------------------------------------------


def test_generate_raises_ollama_error_on_connect_error() -> None:
    with (
        patch("httpx.post", side_effect=httpx.ConnectError("Connection refused")),
        pytest.raises(OllamaError),
    ):
        manager.generate("any prompt")


# ---------------------------------------------------------------------------
# AC2 — OllamaError on malformed JSON (not swallowed as ValueError)
# ---------------------------------------------------------------------------


def test_generate_raises_ollama_error_on_malformed_json() -> None:
    resp = _mock_response_text("not json at all")
    with patch("httpx.post", return_value=resp), pytest.raises(OllamaError):
        manager.generate("any prompt")


# ---------------------------------------------------------------------------
# AC3 — All HTTP calls target 127.0.0.1:11434 exclusively
# ---------------------------------------------------------------------------


def test_generate_targets_only_localhost() -> None:
    resp = _mock_response({"response": "ok"})
    with patch("httpx.post", return_value=resp) as mock_post:
        manager.generate("prompt")
        url: str = mock_post.call_args[0][0]
        assert url.startswith("http://127.0.0.1:11434"), f"unexpected URL: {url}"


def test_check_ready_targets_only_localhost() -> None:
    resp = _mock_response({"models": [{"name": "gemma4:e4b"}]})
    with patch("httpx.get", return_value=resp) as mock_get:
        manager.check_ready()
        url: str = mock_get.call_args[0][0]
        assert url.startswith("http://127.0.0.1:11434"), f"unexpected URL: {url}"


# ---------------------------------------------------------------------------
# AC4 — No PII in log output
# ---------------------------------------------------------------------------


def test_generate_does_not_log_prompt_content(caplog: pytest.LogCaptureFixture) -> None:
    pii_prompt = "Nom: Marie Curie, SS: 2 85 07 75 116 089 42"
    resp = _mock_response({"response": "detected"})
    with (
        patch("httpx.post", return_value=resp),
        caplog.at_level(logging.DEBUG, logger="incognito.ollama.manager"),
    ):
        manager.generate(pii_prompt)
    combined_logs = " ".join(r.getMessage() for r in caplog.records)
    assert "Marie Curie" not in combined_logs
    assert "2 85 07 75 116 089 42" not in combined_logs
    assert pii_prompt not in combined_logs


# ---------------------------------------------------------------------------
# check_ready — True when model present in tags response
# ---------------------------------------------------------------------------


def test_check_ready_returns_true_when_model_present() -> None:
    resp = _mock_response({"models": [{"name": "gemma4:e4b"}, {"name": "other:model"}]})
    with patch("httpx.get", return_value=resp):
        assert manager.check_ready() is True


# ---------------------------------------------------------------------------
# check_ready — False when Ollama is down
# ---------------------------------------------------------------------------


def test_check_ready_returns_false_when_ollama_down() -> None:
    with patch("httpx.get", side_effect=httpx.ConnectError("Connection refused")):
        assert manager.check_ready() is False


# ---------------------------------------------------------------------------
# Localhost enforcement — _enforce_localhost raises OllamaError for non-localhost
# ---------------------------------------------------------------------------


def test_enforce_localhost_raises_for_non_localhost() -> None:
    with (
        patch.object(manager, "OLLAMA_HOST", _NON_LOCALHOST),
        pytest.raises(OllamaError, match=r"127\.0\.0\.1"),
    ):
        manager._enforce_localhost()


def test_enforce_localhost_passes_for_loopback() -> None:
    with patch.object(manager, "OLLAMA_HOST", "127.0.0.1"):
        manager._enforce_localhost()  # must not raise
