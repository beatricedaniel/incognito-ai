from __future__ import annotations

import shutil
import subprocess
import warnings

import fitz
import pytest

from tests.conftest import (
    _DOC_IDS,
    _DOC_NAMES,
    _REGEX_ENTITY_TYPES,
    RedactedDoc,
    normalize,
    pii_fragments,
)

# ---------------------------------------------------------------------------
# Layer 1: pdftotext
# ---------------------------------------------------------------------------


@pytest.mark.leakage
@pytest.mark.ollama
@pytest.mark.slow
@pytest.mark.parametrize("doc_name", _DOC_NAMES, ids=_DOC_IDS)
def test_pdftotext_no_pii_leakage(
    redacted_corpus: dict[str, RedactedDoc],
    doc_name: str,
) -> None:
    if not shutil.which("pdftotext"):
        pytest.skip("pdftotext not in PATH")

    doc = redacted_corpus[doc_name]
    result = subprocess.run(
        ["pdftotext", "-enc", "UTF-8", str(doc.pdf_path), "-"],
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
            "found in pdftotext output (detection miss, not redacted)",
            stacklevel=2,
        )

    assert not hard_failures, (
        f"doc={doc.doc_index}: email/phone PII leaked in pdftotext output "
        f"at gt indices {hard_failures}"
    )


# ---------------------------------------------------------------------------
# Layer 2: metadata
# ---------------------------------------------------------------------------


@pytest.mark.leakage
@pytest.mark.ollama
@pytest.mark.slow
@pytest.mark.parametrize("doc_name", _DOC_NAMES, ids=_DOC_IDS)
def test_metadata_is_empty(
    redacted_corpus: dict[str, RedactedDoc],
    doc_name: str,
) -> None:
    doc = redacted_corpus[doc_name]
    with fitz.open(doc.pdf_path) as pdf:
        metadata = pdf.metadata

    non_empty = {k: v for k, v in metadata.items() if v and v.strip()}
    assert (
        not non_empty
    ), f"doc={doc.doc_index}: redacted PDF metadata has non-empty fields: {list(non_empty.keys())}"


# ---------------------------------------------------------------------------
# Layer 3: XMP metadata
# ---------------------------------------------------------------------------


@pytest.mark.leakage
@pytest.mark.ollama
@pytest.mark.slow
@pytest.mark.parametrize("doc_name", _DOC_NAMES, ids=_DOC_IDS)
def test_xmp_metadata_is_empty(
    redacted_corpus: dict[str, RedactedDoc],
    doc_name: str,
) -> None:
    doc = redacted_corpus[doc_name]
    with fitz.open(doc.pdf_path) as pdf:
        xmp = pdf.get_xml_metadata()

    assert not xmp, f"doc={doc.doc_index}: redacted PDF contains non-empty XMP metadata"


# ---------------------------------------------------------------------------
# Layer 4: raw bytes
# ---------------------------------------------------------------------------


@pytest.mark.leakage
@pytest.mark.ollama
@pytest.mark.slow
@pytest.mark.parametrize("doc_name", _DOC_NAMES, ids=_DOC_IDS)
def test_raw_bytes_no_pii_leakage(
    redacted_corpus: dict[str, RedactedDoc],
    doc_name: str,
) -> None:
    doc = redacted_corpus[doc_name]
    raw = doc.pdf_path.read_bytes()

    decoded_utf8 = normalize(raw.decode("utf-8", errors="replace"))
    decoded_latin1 = normalize(raw.decode("latin-1", errors="replace"))

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
            "found in raw PDF bytes (detection miss, not redacted)",
            stacklevel=2,
        )

    assert not hard_failures, (
        f"doc={doc.doc_index}: email/phone PII leaked in raw PDF bytes "
        f"at gt indices {hard_failures}"
    )


@pytest.mark.leakage
@pytest.mark.ollama
@pytest.mark.slow
@pytest.mark.parametrize("doc_name", _DOC_NAMES, ids=_DOC_IDS)
def test_raw_bytes_single_eof(
    redacted_corpus: dict[str, RedactedDoc],
    doc_name: str,
) -> None:
    doc = redacted_corpus[doc_name]
    raw = doc.pdf_path.read_bytes()
    eof_count = raw.count(b"%%EOF")
    assert eof_count == 1, (
        f"doc={doc.doc_index}: expected exactly 1 %%EOF marker (non-incremental save), "
        f"found {eof_count}"
    )
