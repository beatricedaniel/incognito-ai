from __future__ import annotations

import shutil
import subprocess
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Final

import fitz
import pytest

from incognito.core.config import KEYFILE_ATTACHMENT_NAME
from tests.conftest import (
    _DOC_IDS,
    _DOC_NAMES,
    _REGEX_ENTITY_TYPES,
    CORPUS_PAIRS,
    RedactedDoc,
    normalize,
    pii_fragments,
)

if TYPE_CHECKING:
    from tests.conftest import GroundTruthEntry

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TEST_PASSPHRASE: Final[str] = "test-leakage-fixture-passphrase-2026"


# ---------------------------------------------------------------------------
# Value types
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PdfkeyDoc:
    pdfkey_path: Path
    gt: list[GroundTruthEntry]
    doc_index: int


# ---------------------------------------------------------------------------
# Session-scoped fixture: chain off redacted_corpus (no duplicate pipeline)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def pdfkey_corpus(redacted_corpus: dict[str, RedactedDoc]) -> dict[str, PdfkeyDoc]:
    from incognito.pipeline import keyfile

    corpus: dict[str, PdfkeyDoc] = {}

    for doc_name, rdoc in redacted_corpus.items():
        original_path = next(p for p, _ in CORPUS_PAIRS if p.name == doc_name)
        original_bytes = original_path.read_bytes()
        pdfkey_path = keyfile.embed(rdoc.pdf_path, original_bytes, TEST_PASSPHRASE)

        corpus[doc_name] = PdfkeyDoc(
            pdfkey_path=pdfkey_path,
            gt=rdoc.gt,
            doc_index=rdoc.doc_index,
        )

    return corpus


# ---------------------------------------------------------------------------
# Layer 1: pdftotext on .pdfkey
# ---------------------------------------------------------------------------


@pytest.mark.leakage
@pytest.mark.ollama
@pytest.mark.slow
@pytest.mark.parametrize("doc_name", _DOC_NAMES, ids=_DOC_IDS)
def test_keyfile_pdftotext_no_pii(
    pdfkey_corpus: dict[str, PdfkeyDoc],
    doc_name: str,
) -> None:
    if not shutil.which("pdftotext"):
        pytest.skip("pdftotext not in PATH")

    doc = pdfkey_corpus[doc_name]
    result = subprocess.run(
        ["pdftotext", "-enc", "UTF-8", str(doc.pdfkey_path), "-"],
        capture_output=True,
        text=True,
        check=True,
    )
    text_out = normalize(result.stdout)

    hard_failures: list[int] = []
    soft_warnings: list[int] = []

    for entry in doc.gt:
        for fragment in pii_fragments(entry.text):
            if fragment in text_out:
                if entry.entity_type in _REGEX_ENTITY_TYPES:
                    hard_failures.append(entry.index)
                else:
                    soft_warnings.append(entry.index)
                break

    for idx in soft_warnings:
        warnings.warn(
            f"doc={doc.doc_index} gt_index={idx}: person/address fragment "
            "found in .pdfkey pdftotext output (detection miss, not redacted)",
            stacklevel=2,
        )

    assert not hard_failures, (
        f"doc={doc.doc_index}: email/phone PII leaked in .pdfkey pdftotext output "
        f"at gt indices {hard_failures}"
    )


# ---------------------------------------------------------------------------
# Layer 2: fitz metadata on .pdfkey
# ---------------------------------------------------------------------------


@pytest.mark.leakage
@pytest.mark.ollama
@pytest.mark.slow
@pytest.mark.parametrize("doc_name", _DOC_NAMES, ids=_DOC_IDS)
def test_keyfile_metadata_is_empty(
    pdfkey_corpus: dict[str, PdfkeyDoc],
    doc_name: str,
) -> None:
    doc = pdfkey_corpus[doc_name]
    with fitz.open(doc.pdfkey_path) as pdf:
        metadata = pdf.metadata

    non_empty = {k: v for k, v in metadata.items() if v and v.strip()}
    assert (
        not non_empty
    ), f"doc={doc.doc_index}: .pdfkey metadata has non-empty fields: {list(non_empty.keys())}"


# ---------------------------------------------------------------------------
# Layer 3: XMP metadata on .pdfkey
# ---------------------------------------------------------------------------


@pytest.mark.leakage
@pytest.mark.ollama
@pytest.mark.slow
@pytest.mark.parametrize("doc_name", _DOC_NAMES, ids=_DOC_IDS)
def test_keyfile_xmp_metadata_is_empty(
    pdfkey_corpus: dict[str, PdfkeyDoc],
    doc_name: str,
) -> None:
    doc = pdfkey_corpus[doc_name]
    with fitz.open(doc.pdfkey_path) as pdf:
        xmp = pdf.get_xml_metadata()

    assert not xmp, f"doc={doc.doc_index}: .pdfkey contains non-empty XMP metadata"


# ---------------------------------------------------------------------------
# Layer 4: raw bytes (attachment stripped before search)
# ---------------------------------------------------------------------------


@pytest.mark.leakage
@pytest.mark.ollama
@pytest.mark.slow
@pytest.mark.parametrize("doc_name", _DOC_NAMES, ids=_DOC_IDS)
def test_keyfile_raw_bytes_no_pii(
    pdfkey_corpus: dict[str, PdfkeyDoc],
    doc_name: str,
) -> None:
    doc = pdfkey_corpus[doc_name]

    with fitz.open(doc.pdfkey_path) as pdf:
        if KEYFILE_ATTACHMENT_NAME in pdf.embfile_names():
            pdf.embfile_del(KEYFILE_ATTACHMENT_NAME)
        stripped = pdf.tobytes(garbage=4, deflate=True, clean=True)

    decoded_utf8 = normalize(stripped.decode("utf-8", errors="replace"))
    decoded_latin1 = normalize(stripped.decode("latin-1", errors="replace"))

    hard_failures: list[int] = []
    soft_warnings: list[int] = []

    for entry in doc.gt:
        for fragment in pii_fragments(entry.text):
            if fragment in decoded_utf8 or fragment in decoded_latin1:
                if entry.entity_type in _REGEX_ENTITY_TYPES:
                    hard_failures.append(entry.index)
                else:
                    soft_warnings.append(entry.index)
                break

    for idx in soft_warnings:
        warnings.warn(
            f"doc={doc.doc_index} gt_index={idx}: person/address fragment "
            "found in .pdfkey stripped raw bytes (detection miss, not redacted)",
            stacklevel=2,
        )

    assert not hard_failures, (
        f"doc={doc.doc_index}: email/phone PII leaked in .pdfkey raw bytes "
        f"(after attachment strip) at gt indices {hard_failures}"
    )


# ---------------------------------------------------------------------------
# Layer 5: strip recovery.bin → residual is a valid PDF passing all checks
# ---------------------------------------------------------------------------


@pytest.mark.leakage
@pytest.mark.ollama
@pytest.mark.slow
@pytest.mark.parametrize("doc_name", _DOC_NAMES, ids=_DOC_IDS)
def test_keyfile_stripped_is_valid_pdf(
    pdfkey_corpus: dict[str, PdfkeyDoc],
    doc_name: str,
) -> None:
    doc = pdfkey_corpus[doc_name]

    with fitz.open(doc.pdfkey_path) as pdf:
        if KEYFILE_ATTACHMENT_NAME in pdf.embfile_names():
            pdf.embfile_del(KEYFILE_ATTACHMENT_NAME)
        stripped_bytes = pdf.tobytes(garbage=4, deflate=True, clean=True)

    with fitz.open(stream=stripped_bytes, filetype="pdf") as residual:
        assert residual.page_count > 0, f"doc={doc.doc_index}: stripped .pdfkey has no pages"
        metadata = residual.metadata
        xmp = residual.get_xml_metadata()

    non_empty_meta = {k: v for k, v in metadata.items() if v and v.strip()}
    assert not non_empty_meta, (
        f"doc={doc.doc_index}: stripped .pdfkey metadata has non-empty fields: "
        f"{list(non_empty_meta.keys())}"
    )
    assert not xmp, f"doc={doc.doc_index}: stripped .pdfkey contains non-empty XMP metadata"

    if not shutil.which("pdftotext"):
        return

    from incognito.core.tempfiles import TempFileManager

    tfm = TempFileManager()
    try:
        tmp_path = tfm.create_file("stripped.pdf")
        tmp_path.write_bytes(stripped_bytes)

        result = subprocess.run(
            ["pdftotext", "-enc", "UTF-8", str(tmp_path), "-"],
            capture_output=True,
            text=True,
            check=True,
        )
        text_out = normalize(result.stdout)
    finally:
        tfm.cleanup()

    hard_failures: list[int] = []
    soft_warnings: list[int] = []

    for entry in doc.gt:
        for fragment in pii_fragments(entry.text):
            if fragment in text_out:
                if entry.entity_type in _REGEX_ENTITY_TYPES:
                    hard_failures.append(entry.index)
                else:
                    soft_warnings.append(entry.index)
                break

    for idx in soft_warnings:
        warnings.warn(
            f"doc={doc.doc_index} gt_index={idx}: person/address fragment "
            "found in stripped .pdfkey pdftotext output",
            stacklevel=2,
        )

    assert not hard_failures, (
        f"doc={doc.doc_index}: email/phone PII leaked in stripped .pdfkey pdftotext output "
        f"at gt indices {hard_failures}"
    )


# ---------------------------------------------------------------------------
# Layer 6: single %%EOF (non-incremental save)
# ---------------------------------------------------------------------------


@pytest.mark.leakage
@pytest.mark.ollama
@pytest.mark.slow
@pytest.mark.parametrize("doc_name", _DOC_NAMES, ids=_DOC_IDS)
def test_keyfile_single_eof(
    pdfkey_corpus: dict[str, PdfkeyDoc],
    doc_name: str,
) -> None:
    doc = pdfkey_corpus[doc_name]
    raw = doc.pdfkey_path.read_bytes()
    eof_count = raw.count(b"%%EOF")
    assert eof_count == 1, (
        f"doc={doc.doc_index}: expected exactly 1 %%EOF marker in .pdfkey "
        f"(non-incremental save), found {eof_count}"
    )
