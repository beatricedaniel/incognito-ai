from __future__ import annotations

from pathlib import Path


def embed(redacted_pdf: Path, original_bytes: bytes, passphrase: str) -> Path:
    raise NotImplementedError("Reversible redaction is not yet implemented")
