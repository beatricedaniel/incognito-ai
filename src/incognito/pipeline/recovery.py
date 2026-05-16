from __future__ import annotations

import logging
import struct
import unicodedata
import zlib
from pathlib import Path
from typing import Final

import argon2.low_level
import fitz
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from incognito.core.config import (
    AESGCM_NONCE_LENGTH,
    ARGON2_KEY_LENGTH,
    ARGON2_MEMORY_KIB,
    ARGON2_PARALLELISM,
    ARGON2_SALT_LENGTH,
    ARGON2_TIME_COST,
    KEYFILE_ATTACHMENT_NAME,
    KEYFILE_FORMAT_VERSION,
    MAX_DECOMPRESSED_RECOVERY_BYTES,
)
from incognito.core.exceptions import RecoveryError

logger: Final = logging.getLogger(__name__)

_HEADER_LENGTH: Final[int] = 2 + ARGON2_SALT_LENGTH + AESGCM_NONCE_LENGTH

_MSG_AUTH_FAILED: Final[str] = (
    "Incorrect passphrase or the recovery data has been modified. "
    "The redacted document remains readable."
)
_MSG_NOT_FOUND: Final[str] = (
    "Recovery data not found. This file may be a regular redacted PDF, or the recovery data "
    "was removed by a PDF tool or email filter. The redacted document remains readable."
)
_MSG_DAMAGED: Final[str] = (
    "Recovery data is damaged and cannot be read. The redacted document remains readable."
)


def recover(pdfkey_path: Path, passphrase: str) -> bytes:
    """Extract and decrypt original PDF from .pdfkey file."""
    payload = _extract_payload(pdfkey_path)
    return _decrypt_payload(payload, passphrase)


def _extract_payload(pdfkey_path: Path) -> bytes:
    try:
        doc = fitz.open(pdfkey_path)
    except Exception as exc:
        raise RecoveryError(_MSG_DAMAGED) from exc

    try:
        if KEYFILE_ATTACHMENT_NAME not in doc.embfile_names():
            raise RecoveryError(_MSG_NOT_FOUND)
        return bytes(doc.embfile_get(KEYFILE_ATTACHMENT_NAME))
    finally:
        doc.close()


def _decrypt_payload(payload: bytes, passphrase: str) -> bytes:
    if len(payload) < _HEADER_LENGTH:
        raise RecoveryError(_MSG_DAMAGED)

    version = struct.unpack(">H", payload[:2])[0]
    if version != KEYFILE_FORMAT_VERSION:
        raise RecoveryError(
            f"Unsupported recovery data version (v{version}). "
            "Please update incognito to recover this file. "
            "The redacted document remains readable."
        )

    salt = payload[2 : 2 + ARGON2_SALT_LENGTH]
    nonce = payload[2 + ARGON2_SALT_LENGTH : _HEADER_LENGTH]
    ciphertext = payload[_HEADER_LENGTH:]

    if not ciphertext:
        raise RecoveryError(_MSG_DAMAGED)

    passphrase_bytes = unicodedata.normalize("NFC", passphrase).encode("utf-8")
    key = argon2.low_level.hash_secret_raw(
        secret=passphrase_bytes,
        salt=salt,
        time_cost=ARGON2_TIME_COST,
        memory_cost=ARGON2_MEMORY_KIB,
        parallelism=ARGON2_PARALLELISM,
        hash_len=ARGON2_KEY_LENGTH,
        type=argon2.low_level.Type.ID,
    )

    try:
        compressed = AESGCM(key).decrypt(nonce, ciphertext, associated_data=None)
    except InvalidTag as exc:
        raise RecoveryError(_MSG_AUTH_FAILED) from exc

    try:
        dobj = zlib.decompressobj()
        result = dobj.decompress(compressed, MAX_DECOMPRESSED_RECOVERY_BYTES)
        if dobj.unconsumed_tail:
            raise RecoveryError(_MSG_DAMAGED)
    except zlib.error as exc:
        raise RecoveryError(_MSG_DAMAGED) from exc

    if not result.startswith(b"%PDF-"):
        raise RecoveryError(_MSG_DAMAGED)

    logger.info("Recovery successful: %d bytes", len(result))
    return result
