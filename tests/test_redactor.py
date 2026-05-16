from __future__ import annotations

import ast
import logging
import shutil
import subprocess
import tempfile
from pathlib import Path

import fitz
import pytest

from incognito.core.exceptions import RedactionError
from incognito.models import BBox, Detection, EntityType
from incognito.pipeline.redactor import redact_pdf

# ---------------------------------------------------------------------------
# PDF fixture factories
# ---------------------------------------------------------------------------


def _write_pdf_bytes(data: bytes) -> Path:
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(data)
    return Path(tmp.name)


def _output_path() -> Path:
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        pass
    return Path(tmp.name)


def _single_page_pdf(text: str) -> Path:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text, fontsize=12)
    pdf_bytes = doc.tobytes()
    doc.close()
    return _write_pdf_bytes(pdf_bytes)


def _multi_page_pdf(pages: list[str]) -> Path:
    doc = fitz.open()
    for text in pages:
        page = doc.new_page()
        page.insert_text((72, 72), text, fontsize=12)
    pdf_bytes = doc.tobytes()
    doc.close()
    return _write_pdf_bytes(pdf_bytes)


def _detection_for_text(pdf_path: Path, text: str, page_num: int = 0) -> Detection:
    """Build a Detection whose bbox exactly covers the given text on the page."""
    doc = fitz.open(pdf_path)
    rects = doc[page_num].search_for(text)
    doc.close()
    assert rects, f"text '{text}' not found on page {page_num}"
    r = rects[0]
    return Detection(
        text=text,
        entity_type=EntityType.PERSON,
        page=page_num,
        start=0,
        end=len(text),
        bbox=BBox(x=r.x0, y=r.y0, width=r.x1 - r.x0, height=r.y1 - r.y0),
    )


# ---------------------------------------------------------------------------
# AC3 — PyMuPDF get_text() must not contain redacted PII
# ---------------------------------------------------------------------------


def test_redaction_removes_text_from_get_text() -> None:
    pii = "Jean Dupont"
    safe = "Republique Francaise"
    pdf_path = _single_page_pdf(f"{pii} - {safe}")
    det = _detection_for_text(pdf_path, pii)
    out = _output_path()

    redact_pdf(pdf_path, [det], out)

    doc = fitz.open(out)
    full_text = "".join(doc[i].get_text() for i in range(len(doc)))
    doc.close()

    assert pii not in full_text
    assert safe in full_text


# ---------------------------------------------------------------------------
# AC2 — pdftotext must not contain redacted PII
# ---------------------------------------------------------------------------


@pytest.mark.skipif(shutil.which("pdftotext") is None, reason="pdftotext not installed")
def test_redaction_removes_text_from_pdftotext() -> None:
    pii = "Marie Curie"
    safe = "Acte de naissance"
    pdf_path = _single_page_pdf(f"{pii} {safe}")
    det = _detection_for_text(pdf_path, pii)
    out = _output_path()

    redact_pdf(pdf_path, [det], out)

    result = subprocess.run(
        ["pdftotext", str(out), "-"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert pii not in result.stdout
    assert safe in result.stdout


# ---------------------------------------------------------------------------
# AC4 — Black bar drawn over redacted area (SHOULD FAIL: fill=None by default)
# ---------------------------------------------------------------------------


def test_black_bar_drawn_over_redacted_area() -> None:
    pii = "12 rue de la Paix"
    pdf_path = _single_page_pdf(pii)
    det = _detection_for_text(pdf_path, pii)
    out = _output_path()

    redact_pdf(pdf_path, [det], out)

    doc = fitz.open(out)
    page = doc[0]
    # Sample the centre of the redacted rect
    cx = det.bbox.x + det.bbox.width / 2
    cy = det.bbox.y + det.bbox.height / 2
    clip = fitz.Rect(cx - 1, cy - 1, cx + 1, cy + 1)
    pix = page.get_pixmap(clip=clip, colorspace=fitz.csRGB)
    doc.close()

    # Every sampled pixel must be black (R=0, G=0, B=0)
    samples = list(pix.samples)
    for i in range(0, len(samples), 3):
        r, g, b = samples[i], samples[i + 1], samples[i + 2]
        assert (r, g, b) == (0, 0, 0), (
            f"Expected black pixel at redacted area, got ({r}, {g}, {b}). "
            "add_redact_annot() must be called with fill=(0,0,0)."
        )


# ---------------------------------------------------------------------------
# AC4 — Rest of document intact after redaction
# ---------------------------------------------------------------------------


def test_non_pii_text_preserved() -> None:
    pii = "Pierre Martin"
    safe = "75002 Paris"
    pdf_path = _single_page_pdf(f"{pii} {safe}")
    det = _detection_for_text(pdf_path, pii)
    out = _output_path()

    redact_pdf(pdf_path, [det], out)

    doc = fitz.open(out)
    full_text = "".join(doc[i].get_text() for i in range(len(doc)))
    doc.close()

    assert safe in full_text


# ---------------------------------------------------------------------------
# Edge case — empty detection list preserves document
# ---------------------------------------------------------------------------


def test_empty_detections_preserves_document() -> None:
    text = "Aucun PII ici"
    pdf_path = _single_page_pdf(text)
    out = _output_path()

    redact_pdf(pdf_path, [], out)

    doc = fitz.open(out)
    full_text = "".join(doc[i].get_text() for i in range(len(doc)))
    doc.close()

    assert text in full_text


# ---------------------------------------------------------------------------
# Edge case — all detections dismissed: document unchanged
# ---------------------------------------------------------------------------


def test_all_dismissed_preserves_document() -> None:
    pii = "Sophie Bernard"
    pdf_path = _single_page_pdf(pii)
    det = _detection_for_text(pdf_path, pii)
    dismissed = det.model_copy(update={"dismissed": True})
    out = _output_path()

    redact_pdf(pdf_path, [dismissed], out)

    doc = fitz.open(out)
    full_text = "".join(doc[i].get_text() for i in range(len(doc)))
    doc.close()

    assert pii in full_text


# ---------------------------------------------------------------------------
# AC1+3 — Multi-page: each detection on its own page is redacted
# ---------------------------------------------------------------------------


def test_multi_page_redaction() -> None:
    pii_p0 = "Luc Moreau"
    pii_p1 = "Anne Leblanc"
    safe_p0 = "Dossier medical"
    safe_p1 = "Centre hospitalier"

    pdf_path = _multi_page_pdf([f"{pii_p0} {safe_p0}", f"{pii_p1} {safe_p1}"])
    det0 = _detection_for_text(pdf_path, pii_p0, page_num=0)
    det1 = _detection_for_text(pdf_path, pii_p1, page_num=1)
    out = _output_path()

    redact_pdf(pdf_path, [det0, det1], out)

    doc = fitz.open(out)
    text_p0 = doc[0].get_text()
    text_p1 = doc[1].get_text()
    doc.close()

    assert pii_p0 not in text_p0
    assert safe_p0 in text_p0
    assert pii_p1 not in text_p1
    assert safe_p1 in text_p1


# ---------------------------------------------------------------------------
# Bug — invalid page raises IndexError, not RedactionError (SHOULD FAIL)
# ---------------------------------------------------------------------------


def test_page_out_of_range_raises_redaction_error() -> None:
    pdf_path = _single_page_pdf("Contenu quelconque")
    det = Detection(
        text="fantome",
        entity_type=EntityType.PERSON,
        page=99,  # page does not exist
        start=0,
        end=7,
        bbox=BBox(x=0, y=0, width=100, height=20),
    )
    out = _output_path()

    with pytest.raises(RedactionError):
        redact_pdf(pdf_path, [det], out)


# ---------------------------------------------------------------------------
# Bug — no try/finally: doc not closed on mid-redaction exception (SHOULD FAIL)
# ---------------------------------------------------------------------------


def test_document_closed_on_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    """If an error occurs after doc.open(), doc.close() must still be called."""
    pdf_path = _single_page_pdf("Texte quelconque")

    closed: list[bool] = []
    original_fitz_open = fitz.open

    class _TrackingDoc:
        def __init__(self: _TrackingDoc, wrapped: fitz.Document) -> None:
            self._doc = wrapped

        def __len__(self: _TrackingDoc) -> int:
            return len(self._doc)

        def __getitem__(self: _TrackingDoc, idx: int) -> fitz.Page:
            raise RuntimeError("simulated mid-redaction failure")

        def set_metadata(self: _TrackingDoc, _meta: dict[str, str]) -> None:
            pass

        def del_xml_metadata(self: _TrackingDoc) -> None:
            pass

        def save(self: _TrackingDoc, *args: object, **kwargs: object) -> None:
            pass

        def close(self: _TrackingDoc) -> None:
            closed.append(True)
            self._doc.close()

    def patched_open(path: object) -> _TrackingDoc:
        return _TrackingDoc(original_fitz_open(path))

    monkeypatch.setattr(fitz, "open", patched_open)

    det = Detection(
        text="Texte quelconque",
        entity_type=EntityType.PERSON,
        page=0,
        start=0,
        end=16,
        bbox=BBox(x=72, y=60, width=120, height=20),
    )
    out = _output_path()

    with pytest.raises(RuntimeError, match="simulated"):
        redact_pdf(pdf_path, [det], out)

    assert closed, "fitz document was not closed after redaction failure (resource leak)"


# ---------------------------------------------------------------------------
# Bug — log counts dismissed detections (SHOULD FAIL)
# ---------------------------------------------------------------------------


def test_log_counts_only_applied(caplog: pytest.LogCaptureFixture) -> None:
    pii = "Claude Monet"
    pdf_path = _single_page_pdf(pii)

    applied = _detection_for_text(pdf_path, pii)
    dismissed = Detection(
        text="fantome",
        entity_type=EntityType.EMAIL,
        page=0,
        start=0,
        end=7,
        bbox=BBox(x=300, y=300, width=80, height=20),
        dismissed=True,
    )
    out = _output_path()

    with caplog.at_level(logging.INFO, logger="incognito.pipeline.redactor"):
        redact_pdf(pdf_path, [applied, dismissed], out)

    log_messages = [r.message for r in caplog.records]
    # Only 1 detection was actually applied; log must NOT say "2 detections applied"
    assert any(
        "1" in msg for msg in log_messages
    ), f"Expected applied count 1 in log output, got: {log_messages}"
    assert not any(
        "2 detections applied" in msg for msg in log_messages
    ), "Log incorrectly counts dismissed detection in applied total"


# ---------------------------------------------------------------------------
# Import guard — no HTTP client imports in pipeline/redactor.py
# ---------------------------------------------------------------------------


def test_no_http_client_imports() -> None:
    redactor_path = Path(__file__).parent.parent / "src" / "incognito" / "pipeline" / "redactor.py"
    source = redactor_path.read_text()
    tree = ast.parse(source)
    forbidden = {"httpx", "urllib", "urllib3", "requests", "aiohttp", "http.client"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name not in forbidden, f"forbidden import: {alias.name}"
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for pkg in forbidden:
                assert not module.startswith(pkg), f"forbidden import from: {module}"
