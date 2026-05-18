from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Final

HOST: Final[str] = os.environ.get("INCOGNITO_HOST", "127.0.0.1")
PORT: Final[int] = int(os.environ.get("INCOGNITO_PORT", "8642"))
LOG_LEVEL: Final[int] = getattr(logging, os.environ.get("INCOGNITO_LOG_LEVEL", "INFO").upper())
NO_BROWSER: Final[bool] = os.environ.get("INCOGNITO_NO_BROWSER", "").lower() in ("1", "true", "yes")

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

KEYFILE_FORMAT_VERSION: Final[int] = 1
KEYFILE_ATTACHMENT_NAME: Final[str] = "recovery.bin"
ARGON2_MEMORY_KIB: Final[int] = 65_536
ARGON2_TIME_COST: Final[int] = 3
ARGON2_PARALLELISM: Final[int] = 1
ARGON2_KEY_LENGTH: Final[int] = 32
ARGON2_SALT_LENGTH: Final[int] = 16
AESGCM_NONCE_LENGTH: Final[int] = 12
MAX_DECOMPRESSED_RECOVERY_BYTES: Final[int] = MAX_UPLOAD_BYTES * 4

STATIC_DIR: Final[Path] = Path(__file__).resolve().parent.parent / "static"

GLINER_MODEL: Final[str] = "knowledgator/gliner-pii-large-v1.0"
GLINER_LABELS: Final[tuple[str, ...]] = ("person", "address")
GLINER_THRESHOLD_PERSON: Final[float] = float(
    os.environ.get("INCOGNITO_GLINER_THRESHOLD_PERSON", "0.5")
)
GLINER_THRESHOLD_ADDRESS: Final[float] = float(
    os.environ.get("INCOGNITO_GLINER_THRESHOLD_ADDRESS", "0.3")
)

GEMMA_CONFIRM_SYSTEM: Final[str] = """\
You validate PII candidates in French administrative/medical text.

For each numbered candidate, answer 1 (real personal PII) or 0 (not personal PII).

Real PII (answer 1):
- Personal names of individuals (patients, citizens, relatives, doctors)
- Residential or personal postal addresses

NOT PII (answer 0):
- Organization names, company names, facility names (hospitals, administrations, companies)
- Job titles, professional roles
- Institutional/official addresses (company addresses, administration addresses)
- Legal references, law citations, decree numbers
- City/department names used as geographic identifiers, not personal addresses

Examples:
Text: "Mr. Peter Lawson, residing at 412 Maple Lane, Cincinnati, OH 45208"
1. "Mr. Peter Lawson," [PERSON] \u2192 1
2. "412 Maple Lane, Cincinnati, OH 45208" [ADDRESS] \u2192 1

Text: "Saint Joseph Medical Center, 2614 Lakewood Boulevard, Cleveland, OH 44104"
1. "Saint Joseph" [PERSON] \u2192 0
2. "Medical Center" [PERSON] \u2192 0
3. "2614 Lakewood Boulevard, Cleveland, OH 44104" [ADDRESS] \u2192 0

Answer format: one line per candidate, ID: 0 or 1. Nothing else."""
