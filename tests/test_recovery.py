from __future__ import annotations

import ast
import unicodedata
from pathlib import Path
from typing import Final
from unittest.mock import patch

import fitz
import pytest
from starlette.testclient import TestClient

from incognito.core.config import KEYFILE_ATTACHMENT_NAME
from incognito.core.exceptions import RecoveryError
from incognito.pipeline.keyfile import embed

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_VALID_PASSPHRASE: Final[str] = "correct-horse-battery"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_pdf(tmp_path: Path, text: str, name: str = "source.pdf") -> tuple[Path, bytes]:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text, fontsize=12)
    pdf_bytes = doc.tobytes()
    doc.close()
    pdf_path = tmp_path / name
    pdf_path.write_bytes(pdf_bytes)
    return pdf_path, pdf_bytes


def _make_client(tmp_path: Path) -> TestClient:
    static_dir = tmp_path / "static"
    static_dir.mkdir(exist_ok=True)
    (static_dir / "index.html").write_text("<html></html>")

    with (
        patch("incognito.app.STATIC_DIR", static_dir),
        patch("incognito.app.cleanup_orphaned_temp_dirs"),
    ):
        from incognito.app import create_app

        return TestClient(create_app(), raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# AC1 (also AC8 acceptance) — round-trip: recover returns byte-identical original
# ---------------------------------------------------------------------------


def test_roundtrip_byte_identical(tmp_path: Path) -> None:
    from incognito.pipeline.recovery import recover

    redacted_path, original_bytes = _make_pdf(tmp_path, "Document confidentiel", "redacted.pdf")
    pdfkey_path = embed(redacted_path, original_bytes, _VALID_PASSPHRASE)

    result = recover(pdfkey_path, _VALID_PASSPHRASE)

    assert result == original_bytes


# ---------------------------------------------------------------------------
# AC2 — wrong passphrase raises RecoveryError with prescribed message
# ---------------------------------------------------------------------------


def test_wrong_passphrase_raises_recovery_error(tmp_path: Path) -> None:
    from incognito.pipeline.recovery import recover

    redacted_path, original_bytes = _make_pdf(tmp_path, "Contenu", "redacted.pdf")
    pdfkey_path = embed(redacted_path, original_bytes, _VALID_PASSPHRASE)

    with pytest.raises(RecoveryError) as exc_info:
        recover(pdfkey_path, "wrong-passphrase-xyz")

    assert exc_info.value.detail == (
        "Incorrect passphrase or the recovery data has been modified. "
        "The redacted document remains readable."
    )


# ---------------------------------------------------------------------------
# AC3 — plain PDF (no embedded file) raises RecoveryError with prescribed message
# ---------------------------------------------------------------------------


def test_missing_recovery_bin_raises_recovery_error(tmp_path: Path) -> None:
    from incognito.pipeline.recovery import recover

    plain_path, _ = _make_pdf(tmp_path, "Plain PDF without attachment", "plain.pdf")

    with pytest.raises(RecoveryError) as exc_info:
        recover(plain_path, _VALID_PASSPHRASE)

    assert exc_info.value.detail == (
        "Recovery data not found. This file may be a regular redacted PDF, or the recovery data "
        "was removed by a PDF tool or email filter. The redacted document remains readable."
    )


# ---------------------------------------------------------------------------
# AC4 — payload shorter than 30 bytes raises RecoveryError about damage
# ---------------------------------------------------------------------------


def test_truncated_payload_raises_recovery_error(tmp_path: Path) -> None:
    from incognito.pipeline.recovery import recover

    redacted_path, original_bytes = _make_pdf(tmp_path, "Contenu", "redacted.pdf")
    pdfkey_path = embed(redacted_path, original_bytes, _VALID_PASSPHRASE)

    # Replace the embedded file with garbage shorter than 30 bytes.
    with fitz.open(pdfkey_path) as doc:
        doc.embfile_del(KEYFILE_ATTACHMENT_NAME)
        doc.embfile_add(KEYFILE_ATTACHMENT_NAME, b"\xde\xad\xbe\xef")
        corrupted_path = tmp_path / "corrupted.pdfkey"
        doc.save(str(corrupted_path))

    with pytest.raises(RecoveryError) as exc_info:
        recover(corrupted_path, _VALID_PASSPHRASE)

    assert exc_info.value.detail == (
        "Recovery data is damaged and cannot be read. The redacted document remains readable."
    )


# ---------------------------------------------------------------------------
# AC5 — POST /api/recover with valid .pdfkey + passphrase → 200, PDF bytes
# ---------------------------------------------------------------------------


def test_api_recover_success(tmp_path: Path) -> None:
    redacted_path, original_bytes = _make_pdf(tmp_path, "Document API test", "redacted.pdf")
    pdfkey_path = embed(redacted_path, original_bytes, _VALID_PASSPHRASE)

    client = _make_client(tmp_path)

    with pdfkey_path.open("rb") as fh:
        response = client.post(
            "/api/recover",
            files={"file": ("test.pdfkey", fh, "application/octet-stream")},
            data={"passphrase": _VALID_PASSPHRASE},
        )

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content == original_bytes


# ---------------------------------------------------------------------------
# AC6 — POST /api/recover with missing passphrase → 400
# ---------------------------------------------------------------------------


def test_api_recover_missing_passphrase_returns_400(tmp_path: Path) -> None:
    redacted_path, original_bytes = _make_pdf(tmp_path, "Contenu", "redacted.pdf")
    pdfkey_path = embed(redacted_path, original_bytes, _VALID_PASSPHRASE)

    client = _make_client(tmp_path)

    with pdfkey_path.open("rb") as fh:
        response = client.post(
            "/api/recover",
            files={"file": ("test.pdfkey", fh, "application/octet-stream")},
            # no passphrase field
        )

    assert response.status_code == 400


# ---------------------------------------------------------------------------
# AC7 — import isolation: recovery.py must not import api/, ollama/,
#         or sibling pipeline/ modules
# ---------------------------------------------------------------------------


def test_import_isolation() -> None:
    recovery_path = Path(__file__).parent.parent / "src" / "incognito" / "pipeline" / "recovery.py"
    source = recovery_path.read_text()
    tree = ast.parse(source)

    forbidden_prefixes = (
        "incognito.api",
        "incognito.ollama",
        "incognito.pipeline.extractor",
        "incognito.pipeline.detector",
        "incognito.pipeline.validator",
        "incognito.pipeline.redactor",
        "incognito.pipeline.keyfile",
        "httpx",
        "urllib",
        "requests",
        "aiohttp",
    )

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                for prefix in forbidden_prefixes:
                    assert not alias.name.startswith(
                        prefix
                    ), f"recovery.py must not import {alias.name!r}"
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for prefix in forbidden_prefixes:
                assert not module.startswith(prefix), f"recovery.py must not import from {module!r}"


# ---------------------------------------------------------------------------
# AC8 — unicode passphrase normalization: embed with NFD, recover with NFC
# ---------------------------------------------------------------------------


def test_unicode_passphrase_normalization_roundtrip(tmp_path: Path) -> None:
    from incognito.pipeline.recovery import recover

    redacted_path, original_bytes = _make_pdf(tmp_path, "Contenu unicode", "redacted.pdf")

    base = "café-sécurité-clé-longue"
    passphrase_nfd = unicodedata.normalize("NFD", base)
    passphrase_nfc = unicodedata.normalize("NFC", base)
    assert passphrase_nfd != passphrase_nfc, "test requires NFD != NFC at byte level"

    # embed using NFD form
    pdfkey_path = embed(redacted_path, original_bytes, passphrase_nfd)

    # recover using NFC form — both normalize to the same NFC internally
    result = recover(pdfkey_path, passphrase_nfc)

    assert result == original_bytes
