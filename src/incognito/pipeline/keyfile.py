from __future__ import annotations

import logging
import os
import struct
import unicodedata
import zlib
from pathlib import Path
from typing import Final

import argon2.low_level
import fitz
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
    PASSPHRASE_MIN_LENGTH,
)
from incognito.core.exceptions import KeyfileError, PassphraseError

logger: Final = logging.getLogger(__name__)


def embed(redacted_pdf_path: Path, original_pdf_bytes: bytes, passphrase: str) -> Path:
    """Embed encrypted original into redacted PDF. Returns .pdfkey path."""
    if len(passphrase) < PASSPHRASE_MIN_LENGTH:
        raise PassphraseError(f"Passphrase must be at least {PASSPHRASE_MIN_LENGTH} characters")

    compressed = zlib.compress(original_pdf_bytes, level=9)

    salt = os.urandom(ARGON2_SALT_LENGTH)
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

    nonce = os.urandom(AESGCM_NONCE_LENGTH)
    ciphertext = AESGCM(key).encrypt(nonce, compressed, associated_data=None)
    del compressed

    payload = struct.pack(">H", KEYFILE_FORMAT_VERSION) + salt + nonce + ciphertext
    del ciphertext

    output_path = redacted_pdf_path.with_suffix(".pdfkey")
    _embed_payload(redacted_pdf_path, payload, output_path)

    logger.info("Keyfile created: %d-byte payload embedded", len(payload))
    return output_path


def _embed_payload(src_pdf: Path, payload: bytes, dest: Path) -> None:
    tmp_path = dest.with_suffix(".pdfkey.tmp")

    try:
        doc = fitz.open(src_pdf)
    except Exception as exc:
        raise KeyfileError("Failed to open redacted PDF for embedding") from exc

    try:
        if KEYFILE_ATTACHMENT_NAME in doc.embfile_names():
            doc.embfile_del(KEYFILE_ATTACHMENT_NAME)

        doc.embfile_add(
            KEYFILE_ATTACHMENT_NAME,
            payload,
            filename=KEYFILE_ATTACHMENT_NAME,
            ufilename=KEYFILE_ATTACHMENT_NAME,
            desc="",
        )

        doc.save(str(tmp_path), garbage=4, deflate=True, clean=True)
    except KeyfileError:
        raise
    except Exception as exc:
        raise KeyfileError("Failed to embed recovery data") from exc
    finally:
        doc.close()

    tmp_path.rename(dest)
