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

STAGE_EXTRACTING: Final[str] = "extracting"
STAGE_DETECTING: Final[str] = "detecting"
STAGE_VALIDATING: Final[str] = "validating"
SSE_QUEUE_TIMEOUT_SECONDS: Final[float] = 30.0

PASSPHRASE_MIN_LENGTH: Final[int] = 12

STATIC_DIR: Final[Path] = Path(__file__).resolve().parent.parent / "static"

GLINER_MODEL: Final[str] = "urchade/gliner_multi-v2.1"
GLINER_LABELS: Final[tuple[str, ...]] = ("person", "address")
GLINER_THRESHOLD_PERSON: Final[float] = float(
    os.environ.get("INCOGNITO_GLINER_THRESHOLD_PERSON", "0.5")
)
GLINER_THRESHOLD_ADDRESS: Final[float] = float(
    os.environ.get("INCOGNITO_GLINER_THRESHOLD_ADDRESS", "0.3")
)

GEMMA_CONFIRM_SYSTEM: Final[str] = (
    "You validate PII candidates in French administrative text.\n"
    "For each numbered candidate, answer 1 (real PII) or 0 (not PII).\n"
    "Real PII: personal names of individuals, residential/personal postal addresses.\n"
    "Not PII: organization names, facility names, job titles, institutional addresses "
    "(headquarters, offices), legal references, department names, city names used as "
    "facility identifiers.\n"
    "Answer format: one line per candidate, ID: 0 or 1. Nothing else."
)
