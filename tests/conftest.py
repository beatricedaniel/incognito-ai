from __future__ import annotations

import json
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Final

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
    (
        CORPUS_DIR / "test-small.pdf",
        CORPUS_DIR / "test-small_pii.json",
    ),
]

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
class RedactedDoc:
    pdf_path: Path
    gt: list[GroundTruthEntry]
    doc_index: int


# ---------------------------------------------------------------------------
# Normalization helpers
# ---------------------------------------------------------------------------


def normalize(text: str) -> str:
    nfc = unicodedata.normalize("NFC", text)
    return " ".join(nfc.split()).lower()


def pii_fragments(pii_text: str) -> list[str]:
    normalized = normalize(pii_text)
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
