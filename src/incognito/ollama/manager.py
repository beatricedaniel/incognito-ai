from __future__ import annotations

import logging
from typing import Final

import httpx

from incognito.core.config import OLLAMA_BASE_URL, OLLAMA_HOST, OLLAMA_MODEL
from incognito.core.exceptions import OllamaError

logger: Final = logging.getLogger(__name__)

_TIMEOUT: Final[float] = 120.0


def _enforce_localhost() -> None:
    if OLLAMA_HOST != "127.0.0.1":
        raise OllamaError(f"OLLAMA_HOST must be 127.0.0.1, got {OLLAMA_HOST}")


_enforce_localhost()


def check_ready() -> bool:
    try:
        resp = httpx.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5.0)
        resp.raise_for_status()
        models = resp.json().get("models", [])
        return any(m.get("name", "").startswith(OLLAMA_MODEL) for m in models)
    except httpx.HTTPError:
        return False


def generate(prompt: str, system: str = "") -> str:
    payload: dict[str, object] = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
    }
    if system:
        payload["system"] = system

    try:
        resp = httpx.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json=payload,
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        result: str = resp.json().get("response", "")
    except (httpx.HTTPError, ValueError) as exc:
        raise OllamaError("Ollama inference request failed") from exc
    return result
