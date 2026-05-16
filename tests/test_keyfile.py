from __future__ import annotations

import ast
import shutil
import struct
import subprocess
import unicodedata
import zlib
from pathlib import Path
from typing import Final

import fitz
import pytest

from incognito.core.config import (
    AESGCM_NONCE_LENGTH,
    ARGON2_KEY_LENGTH,
    ARGON2_MEMORY_KIB,
    ARGON2_PARALLELISM,
    ARGON2_SALT_LENGTH,
    ARGON2_TIME_COST,
    KEYFILE_ATTACHMENT_NAME,
    KEYFILE_FORMAT_VERSION,
    PASSPHRASE_MIN_LENGTH,
)
from incognito.core.exceptions import KeyfileError, PassphraseError
from incognito.pipeline.keyfile import embed

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_VALID_PASSPHRASE: Final[str] = "correct-horse-battery"
_VERSION_BYTES: Final[int] = 2
_HEADER_LENGTH: Final[int] = _VERSION_BYTES + ARGON2_SALT_LENGTH + AESGCM_NONCE_LENGTH

# ---------------------------------------------------------------------------
# PDF helpers
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


# ---------------------------------------------------------------------------
# Roundtrip decrypt helper (test-internal only)
# ---------------------------------------------------------------------------


def _decrypt_payload(recovery_bin: bytes, passphrase: str) -> bytes:
    from argon2.low_level import Type, hash_secret_raw
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    if len(recovery_bin) < _HEADER_LENGTH:
        raise ValueError("recovery.bin too short")

    version = struct.unpack(">H", recovery_bin[:_VERSION_BYTES])[0]
    assert version == KEYFILE_FORMAT_VERSION

    salt = recovery_bin[_VERSION_BYTES : _VERSION_BYTES + ARGON2_SALT_LENGTH]
    nonce = recovery_bin[
        _VERSION_BYTES + ARGON2_SALT_LENGTH : _VERSION_BYTES
        + ARGON2_SALT_LENGTH
        + AESGCM_NONCE_LENGTH
    ]
    ciphertext = recovery_bin[_HEADER_LENGTH:]

    key = hash_secret_raw(
        secret=passphrase.encode("utf-8"),
        salt=salt,
        time_cost=ARGON2_TIME_COST,
        memory_cost=ARGON2_MEMORY_KIB,
        parallelism=ARGON2_PARALLELISM,
        hash_len=ARGON2_KEY_LENGTH,
        type=Type.ID,
    )

    aesgcm = AESGCM(key)
    compressed = aesgcm.decrypt(nonce, ciphertext, None)
    return zlib.decompress(compressed)


# ---------------------------------------------------------------------------
# AC1 — output is a valid PDF with matching page count
# ---------------------------------------------------------------------------


def test_output_is_valid_pdf(tmp_path: Path) -> None:
    redacted_path, original_bytes = _make_pdf(tmp_path, "Contenu quelconque", "redacted.pdf")

    result = embed(redacted_path, original_bytes, _VALID_PASSPHRASE)

    assert result.suffix == ".pdfkey"
    with fitz.open(result) as doc:
        assert len(doc) >= 1


def test_output_page_count_matches_redacted(tmp_path: Path) -> None:
    redacted_path, original_bytes = _make_pdf(tmp_path, "Page unique", "redacted.pdf")

    with fitz.open(redacted_path) as src:
        expected_pages = len(src)

    result = embed(redacted_path, original_bytes, _VALID_PASSPHRASE)

    with fitz.open(result) as doc:
        assert len(doc) == expected_pages


# ---------------------------------------------------------------------------
# AC2 — pdftotext shows only redacted content (no original text)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(shutil.which("pdftotext") is None, reason="pdftotext not installed")
def test_pdftotext_shows_no_original_text(tmp_path: Path) -> None:
    original_text = "Jean Dupont confidentiel"
    redacted_text = "████ ██████ confidentiel"

    _, original_bytes = _make_pdf(tmp_path, original_text, "original.pdf")
    redacted_path, _ = _make_pdf(tmp_path, redacted_text, "redacted.pdf")

    result = embed(redacted_path, original_bytes, _VALID_PASSPHRASE)

    proc = subprocess.run(
        ["pdftotext", str(result), "-"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert "Jean Dupont" not in proc.stdout


# ---------------------------------------------------------------------------
# AC3 — exactly one attachment named recovery.bin
# ---------------------------------------------------------------------------


def test_exactly_one_attachment(tmp_path: Path) -> None:
    redacted_path, original_bytes = _make_pdf(tmp_path, "Contenu", "redacted.pdf")

    result = embed(redacted_path, original_bytes, _VALID_PASSPHRASE)

    with fitz.open(result) as doc:
        names = doc.embfile_names()
    assert names == [KEYFILE_ATTACHMENT_NAME]


# ---------------------------------------------------------------------------
# AC4 — binary format: version + salt + nonce + ciphertext
# ---------------------------------------------------------------------------


def test_binary_format_version_bytes(tmp_path: Path) -> None:
    redacted_path, original_bytes = _make_pdf(tmp_path, "Contenu", "redacted.pdf")

    result = embed(redacted_path, original_bytes, _VALID_PASSPHRASE)

    with fitz.open(result) as doc:
        recovery_bin = doc.embfile_get(KEYFILE_ATTACHMENT_NAME)

    version = struct.unpack(">H", recovery_bin[:_VERSION_BYTES])[0]
    assert version == KEYFILE_FORMAT_VERSION


def test_binary_format_salt_and_nonce_lengths(tmp_path: Path) -> None:
    redacted_path, original_bytes = _make_pdf(tmp_path, "Contenu", "redacted.pdf")

    result = embed(redacted_path, original_bytes, _VALID_PASSPHRASE)

    with fitz.open(result) as doc:
        recovery_bin = doc.embfile_get(KEYFILE_ATTACHMENT_NAME)

    assert len(recovery_bin) > _HEADER_LENGTH, "no ciphertext after header"
    # salt occupies bytes 2..17, nonce bytes 18..29 — verify total header is extractable
    salt = recovery_bin[_VERSION_BYTES : _VERSION_BYTES + ARGON2_SALT_LENGTH]
    nonce = recovery_bin[
        _VERSION_BYTES + ARGON2_SALT_LENGTH : _VERSION_BYTES
        + ARGON2_SALT_LENGTH
        + AESGCM_NONCE_LENGTH
    ]
    assert len(salt) == ARGON2_SALT_LENGTH
    assert len(nonce) == AESGCM_NONCE_LENGTH


# ---------------------------------------------------------------------------
# AC5 — roundtrip decrypt returns exact original bytes
# ---------------------------------------------------------------------------


def test_roundtrip_decrypt_returns_original(tmp_path: Path) -> None:
    redacted_path, original_bytes = _make_pdf(tmp_path, "Document confidentiel", "redacted.pdf")

    result = embed(redacted_path, original_bytes, _VALID_PASSPHRASE)

    with fitz.open(result) as doc:
        recovery_bin = doc.embfile_get(KEYFILE_ATTACHMENT_NAME)

    recovered = _decrypt_payload(recovery_bin, _VALID_PASSPHRASE)
    assert recovered == original_bytes


def test_wrong_passphrase_does_not_decrypt(tmp_path: Path) -> None:
    redacted_path, original_bytes = _make_pdf(tmp_path, "Contenu", "redacted.pdf")

    result = embed(redacted_path, original_bytes, _VALID_PASSPHRASE)

    with fitz.open(result) as doc:
        recovery_bin = doc.embfile_get(KEYFILE_ATTACHMENT_NAME)

    from cryptography.exceptions import InvalidTag

    with pytest.raises(InvalidTag):
        _decrypt_payload(recovery_bin, "wrong-passphrase-x")


# ---------------------------------------------------------------------------
# AC6 — short passphrase raises PassphraseError
# ---------------------------------------------------------------------------


def test_short_passphrase_raises(tmp_path: Path) -> None:
    redacted_path, original_bytes = _make_pdf(tmp_path, "Contenu", "redacted.pdf")
    short = "a" * (PASSPHRASE_MIN_LENGTH - 1)

    with pytest.raises(PassphraseError):
        embed(redacted_path, original_bytes, short)


def test_passphrase_at_minimum_length_accepted(tmp_path: Path) -> None:
    redacted_path, original_bytes = _make_pdf(tmp_path, "Contenu", "redacted.pdf")
    exact = "a" * PASSPHRASE_MIN_LENGTH

    result = embed(redacted_path, original_bytes, exact)
    assert result.exists()


# ---------------------------------------------------------------------------
# AC7 — nonexistent PDF path raises KeyfileError
# ---------------------------------------------------------------------------


def test_nonexistent_pdf_raises_keyfile_error(tmp_path: Path) -> None:
    missing = tmp_path / "does_not_exist.pdf"
    _, original_bytes = _make_pdf(tmp_path, "Contenu", "original.pdf")

    with pytest.raises(KeyfileError):
        embed(missing, original_bytes, _VALID_PASSPHRASE)


# ---------------------------------------------------------------------------
# AC8 — unicode passphrase (NFC-normalized) works in roundtrip
# ---------------------------------------------------------------------------


def test_unicode_passphrase_roundtrip(tmp_path: Path) -> None:
    redacted_path, original_bytes = _make_pdf(tmp_path, "Contenu", "redacted.pdf")
    # NFD form of "café-sécurité-clé" — implementation must NFC-normalize
    passphrase_nfd = unicodedata.normalize("NFD", "café-sécurité-clé-long")
    passphrase_nfc = unicodedata.normalize("NFC", passphrase_nfd)
    assert passphrase_nfd != passphrase_nfc  # confirm they differ at byte level

    result = embed(redacted_path, original_bytes, passphrase_nfd)

    with fitz.open(result) as doc:
        recovery_bin = doc.embfile_get(KEYFILE_ATTACHMENT_NAME)

    # must decrypt with NFC form (the canonical form the implementation normalizes to)
    recovered = _decrypt_payload(recovery_bin, passphrase_nfc)
    assert recovered == original_bytes


# ---------------------------------------------------------------------------
# AC9 — import isolation: keyfile.py must not import api/, ollama/, other pipeline/
# ---------------------------------------------------------------------------


def test_import_isolation() -> None:
    keyfile_path = Path(__file__).parent.parent / "src" / "incognito" / "pipeline" / "keyfile.py"
    source = keyfile_path.read_text()
    tree = ast.parse(source)

    forbidden_prefixes = (
        "incognito.api",
        "incognito.ollama",
        "incognito.pipeline.extractor",
        "incognito.pipeline.detector",
        "incognito.pipeline.validator",
        "incognito.pipeline.redactor",
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
                    ), f"keyfile.py must not import {alias.name!r}"
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for prefix in forbidden_prefixes:
                assert not module.startswith(prefix), f"keyfile.py must not import from {module!r}"
