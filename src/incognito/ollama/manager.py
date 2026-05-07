from __future__ import annotations

import logging
from typing import Final

import httpx

from incognito.core.config import OLLAMA_BASE_URL, OLLAMA_MODEL
from incognito.core.exceptions import OllamaError

logger: Final = logging.getLogger(__name__)

_TIMEOUT: Final[float] = 120.0


def check_ready() -> bool:
    try:
        resp = httpx.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5.0)
        resp.raise_for_status()
        models = resp.json().get("models", [])
        return any(m.get("name", "").startswith(OLLAMA_MODEL) for m in models)
    except httpx.HTTPError:
        return False


def generate(prompt: str) -> str:
    try:
        resp = httpx.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False},
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        result: str = resp.json().get("response", "")
        return result
    except httpx.HTTPError as exc:
        raise OllamaError("Ollama inference request failed") from exc
