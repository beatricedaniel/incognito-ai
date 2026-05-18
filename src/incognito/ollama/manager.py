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


def check_status() -> dict[str, object]:
    try:
        resp = httpx.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=2.0)
        resp.raise_for_status()
    except httpx.HTTPError:
        return {"ollama_reachable": False, "model_ready": False, "model": OLLAMA_MODEL}
    models = resp.json().get("models", [])
    model_found = any(m.get("name", "").startswith(OLLAMA_MODEL) for m in models)
    return {"ollama_reachable": True, "model_ready": model_found, "model": OLLAMA_MODEL}


def check_ready() -> bool:
    result: bool = bool(check_status()["model_ready"])
    return result


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
