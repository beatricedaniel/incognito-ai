from __future__ import annotations

import json
import shutil
import subprocess
import unicodedata
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import fitz
import pytest

from incognito.core.config import KEYFILE_ATTACHMENT_NAME

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CORPUS_DIR: Final[Path] = Path(__file__).parent / "evaluation" / "corpus"

CORPUS_PAIRS: Final[list[tuple[Path, Path]]] = [
    (
        CORPUS_DIR / "770003408_EHPAD LES ACACIAS.pdf",
        CORPUS_DIR / "770003408_EHPAD_LES_ACACIAS_pii.json",
    ),
    (
        CORPUS_DIR / "780823878_EHPAD LA ROSE DES VENTS.pdf",
        CORPUS_DIR / "780823878_EHPAD_LA_ROSE_DES_VENTS_pii.json",
    ),
    (
        CORPUS_DIR / "930816723_EHPAD RESIDENCE LES BEAUX MONTS.pdf",
        CORPUS_DIR / "930816723_EHPAD_RESIDENCE_LES_BEAUX_MONTS_pii.json",
    ),
    (
        CORPUS_DIR / "950805978_EHPAD RESIDENCE RACHEL.pdf",
        CORPUS_DIR / "950805978_EHPAD_RESIDENCE_RACHEL_pii.json",
    ),
    (
        CORPUS_DIR / "950807826_EHPAD LE PAVILLON DES ARTS.pdf",
        CORPUS_DIR / "950807826_EHPAD_LE_PAVILLON_DES_ARTS_pii.json",
    ),
    (
        CORPUS_DIR / "test-small.pdf",
        CORPUS_DIR / "test-small_pii.json",
    ),
]

TEST_PASSPHRASE: Final[str] = "test-leakage-fixture-passphrase-2026"

_FRENCH_STOP_WORDS: Final[frozenset[str]] = frozenset(
    {
        "de",
        "du",
        "des",
        "le",
        "la",
        "les",
        "un",
        "une",
        "et",
        "en",
        "au",
        "aux",
        "sur",
        "par",
        "pour",
        "dans",
        "avec",
        "que",
        "qui",
        "est",
        "son",
        "sa",
        "ses",
        "mon",
        "ma",
        "mes",
        "ton",
        "ta",
        "tes",
        "rue",
        "avenue",
        "boulevard",
        "place",
        "impasse",
        "chemin",
    }
)

_REGEX_ENTITY_TYPES: Final[frozenset[str]] = frozenset({"email", "phone"})

_DOC_IDS: Final[list[str]] = [f"doc_{i}" for i in range(len(CORPUS_PAIRS))]
_DOC_NAMES: Final[list[str]] = [pdf_path.name for pdf_path, _ in CORPUS_PAIRS]


# ---------------------------------------------------------------------------
# Value types
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class GroundTruthEntry:
    text: str
    entity_type: str
    index: int


@dataclass(frozen=True, slots=True)
class PdfkeyDoc:
    pdfkey_path: Path
    gt: list[GroundTruthEntry]
    doc_index: int


# ---------------------------------------------------------------------------
# Normalization helpers
# ---------------------------------------------------------------------------


def _normalize(text: str) -> str:
    nfc = unicodedata.normalize("NFC", text)
    return " ".join(nfc.split()).lower()


def _pii_fragments(pii_text: str) -> list[str]:
    normalized = _normalize(pii_text)
    tokens = [t for t in normalized.split() if len(t) >= 4 and t not in _FRENCH_STOP_WORDS]
    return [normalized, *tokens]


# ---------------------------------------------------------------------------
# Session-scoped fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def _ollama_ready() -> None:
    from incognito.ollama.manager import check_ready

    if not check_ready():
        pytest.skip("Ollama not reachable or gemma4:e4b not loaded")


@pytest.fixture(scope="session")
def pdfkey_corpus(_ollama_ready: None) -> dict[str, PdfkeyDoc]:
    from incognito.core.tempfiles import TempFileManager
    from incognito.ollama.manager import generate
    from incognito.pipeline import keyfile
    from incognito.pipeline.detector import detect
    from incognito.pipeline.extractor import extract_blocks
    from incognito.pipeline.redactor import redact_pdf
    from incognito.pipeline.validator import validate

    tfm = TempFileManager()
    corpus: dict[str, PdfkeyDoc] = {}

    try:
        for doc_index, (pdf_path, gt_path) in enumerate(CORPUS_PAIRS):
            raw_gt: list[dict[str, object]] = json.loads(gt_path.read_text())
            gt_entries = [
                GroundTruthEntry(
                    text=str(entry["text"]),
                    entity_type=str(entry["entity_type"]),
                    index=i,
                )
                for i, entry in enumerate(raw_gt)
            ]

            original_pdf_bytes = pdf_path.read_bytes()
            blocks = extract_blocks(pdf_path)
            raw_dets = detect(blocks, generate)
            validated = validate(raw_dets, blocks)

            redacted_path = tfm.create_file(f"redacted_{doc_index}.pdf")
            redact_pdf(pdf_path, validated, redacted_path)

            pdfkey_path = keyfile.embed(redacted_path, original_pdf_bytes, TEST_PASSPHRASE)

            corpus[pdf_path.name] = PdfkeyDoc(
                pdfkey_path=pdfkey_path,
                gt=gt_entries,
                doc_index=doc_index,
            )
    except Exception:
        tfm.cleanup()
        raise

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
    text_out = _normalize(result.stdout)

    hard_failures: list[int] = []
    soft_warnings: list[int] = []

    for entry in doc.gt:
        for fragment in _pii_fragments(entry.text):
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

    decoded_utf8 = _normalize(stripped.decode("utf-8", errors="replace"))
    decoded_latin1 = _normalize(stripped.decode("latin-1", errors="replace"))

    hard_failures: list[int] = []
    soft_warnings: list[int] = []

    for entry in doc.gt:
        for fragment in _pii_fragments(entry.text):
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
        text_out = _normalize(result.stdout)
    finally:
        tfm.cleanup()

    hard_failures: list[int] = []
    soft_warnings: list[int] = []

    for entry in doc.gt:
        for fragment in _pii_fragments(entry.text):
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
