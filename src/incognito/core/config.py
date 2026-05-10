from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Final

HOST: Final[str] = os.environ.get("INCOGNITO_HOST", "127.0.0.1")
PORT: Final[int] = int(os.environ.get("INCOGNITO_PORT", "8642"))
LOG_LEVEL: Final[int] = getattr(logging, os.environ.get("INCOGNITO_LOG_LEVEL", "INFO").upper())

OLLAMA_HOST: Final[str] = "127.0.0.1"
OLLAMA_PORT: Final[int] = 11434
OLLAMA_BASE_URL: Final[str] = f"http://{OLLAMA_HOST}:{OLLAMA_PORT}"
OLLAMA_MODEL: Final[str] = "gemma4:e4b"

TEMP_PREFIX: Final[str] = "incognito-"
TEMP_DIR_PERMISSIONS: Final[int] = 0o700

SESSION_TIMEOUT_SECONDS: Final[int] = int(os.environ.get("INCOGNITO_SESSION_TIMEOUT", "1800"))

MAX_UPLOAD_BYTES: Final[int] = 50 * 1024 * 1024

STATIC_DIR: Final[Path] = Path(__file__).resolve().parent.parent / "static"
