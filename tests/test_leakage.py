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
]

# French stop words excluded from token-level fragment checks
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

# PII entity types that are regex-detected (hard failures on miss)
_REGEX_ENTITY_TYPES: Final[frozenset[str]] = frozenset({"email", "phone"})


# ---------------------------------------------------------------------------
# Value types
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class GroundTruthEntry:
    text: str
    entity_type: str
    index: int  # position in the ground-truth list, for privacy-safe assertions


@dataclass(frozen=True, slots=True)
class RedactedDoc:
    pdf_path: Path
    gt: list[GroundTruthEntry]
    doc_index: int  # opaque index, never encodes source filename


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
# Session-scoped fixture: run the full pipeline once for all 5 docs
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def _ollama_ready() -> None:
    from incognito.ollama.manager import check_ready

    if not check_ready():
        pytest.skip("Ollama not reachable or gemma4:e4b not loaded")


@pytest.fixture(scope="session")
def redacted_corpus(_ollama_ready: None) -> dict[str, RedactedDoc]:
    from incognito.core.tempfiles import TempFileManager
    from incognito.ollama.manager import generate
    from incognito.pipeline.detector import detect
    from incognito.pipeline.extractor import extract_blocks
    from incognito.pipeline.redactor import redact_pdf
    from incognito.pipeline.validator import validate

    tfm = TempFileManager()
    corpus: dict[str, RedactedDoc] = {}

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

            blocks = extract_blocks(pdf_path)
            raw_dets = detect(blocks, generate)
            validated = validate(raw_dets, blocks)

            # Opaque output filename — never encodes source document name
            output_path = tfm.create_file(f"redacted_{doc_index}.pdf")
            redact_pdf(pdf_path, validated, output_path)

            corpus[pdf_path.name] = RedactedDoc(
                pdf_path=output_path,
                gt=gt_entries,
                doc_index=doc_index,
            )
    except Exception:
        tfm.cleanup()
        raise

    return corpus


# ---------------------------------------------------------------------------
# Parametrize IDs (opaque — no PII in test IDs)
# ---------------------------------------------------------------------------

_DOC_IDS: Final[list[str]] = [f"doc_{i}" for i in range(len(CORPUS_PAIRS))]
_DOC_NAMES: Final[list[str]] = [pdf_path.name for pdf_path, _ in CORPUS_PAIRS]


def _doc_fixture(redacted_corpus: dict[str, RedactedDoc], doc_name: str) -> RedactedDoc:
    return redacted_corpus[doc_name]


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

    decoded_utf8 = _normalize(raw.decode("utf-8", errors="replace"))
    decoded_latin1 = _normalize(raw.decode("latin-1", errors="replace"))

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
