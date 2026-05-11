from __future__ import annotations

import tempfile
import time
from pathlib import Path

import fitz
import pytest

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


def _single_page_pdf(text: str, *, metadata: dict[str, str] | None = None) -> Path:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text, fontsize=12)
    if metadata:
        doc.set_metadata(metadata)
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
# FR20 — Info dictionary stripped after redaction
# ---------------------------------------------------------------------------


def test_metadata_stripped_after_redaction() -> None:
    pdf_path = _single_page_pdf(
        "Jean Dupont",
        metadata={
            "author": "Dr. Secret",
            "title": "Confidentiel",
            "subject": "Medical",
            "creator": "Scanner",
            "producer": "LibreOffice",
        },
    )
    det = _detection_for_text(pdf_path, "Jean Dupont")
    out = _output_path()

    redact_pdf(pdf_path, [det], out)

    doc = fitz.open(out)
    meta = doc.metadata
    doc.close()

    info_fields = (
        "author",
        "title",
        "subject",
        "keywords",
        "creator",
        "producer",
        "creationDate",
        "modDate",
    )
    for field in info_fields:
        value = meta.get(field)
        assert (
            not value
        ), f"metadata field '{field}' should be empty after sanitization, got: {value!r}"


# ---------------------------------------------------------------------------
# FR21 — XMP metadata removed after redaction
# ---------------------------------------------------------------------------


def test_xmp_metadata_removed_after_redaction() -> None:
    # Build a base PDF then inject XMP into its bytes before handing to redact_pdf
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Marie Curie", fontsize=12)
    xmp_packet = (
        '<?xpacket begin="\xef\xbb\xbf" id="W5M0MpCehiHzreSzNTczkc9d"?>'
        '<x:xmpmeta xmlns:x="adobe:ns:meta/">'
        '<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
        '<rdf:Description rdf:about="" xmlns:dc="http://purl.org/dc/elements/1.1/">'
        "<dc:creator><rdf:Seq><rdf:li>Dr. Secret</rdf:li></rdf:Seq></dc:creator>"
        "</rdf:Description>"
        "</rdf:RDF>"
        "</x:xmpmeta>"
        '<?xpacket end="w"?>'
    )
    doc.set_xml_metadata(xmp_packet)
    pdf_bytes = doc.tobytes()
    doc.close()

    pdf_path = _write_pdf_bytes(pdf_bytes)
    det = _detection_for_text(pdf_path, "Marie Curie")
    out = _output_path()

    redact_pdf(pdf_path, [det], out)

    result_doc = fitz.open(out)
    xmp = result_doc.get_xml_metadata()
    result_doc.close()

    assert not xmp, f"XMP metadata should be empty after sanitization, got: {xmp!r}"


# ---------------------------------------------------------------------------
# Edge case — sanitization runs even with zero detections
# ---------------------------------------------------------------------------


def test_metadata_stripped_without_detections() -> None:
    pdf_path = _single_page_pdf(
        "Aucun PII ici",
        metadata={
            "author": "Auteur Confidentiel",
            "title": "Document Prive",
            "subject": "RH",
            "creator": "Word",
            "producer": "Acrobat",
        },
    )
    out = _output_path()

    redact_pdf(pdf_path, [], out)

    doc = fitz.open(out)
    meta = doc.metadata
    xmp = doc.get_xml_metadata()
    doc.close()

    info_fields = (
        "author",
        "title",
        "subject",
        "keywords",
        "creator",
        "producer",
        "creationDate",
        "modDate",
    )
    for field in info_fields:
        value = meta.get(field)
        assert (
            not value
        ), f"metadata field '{field}' should be empty with zero detections, got: {value!r}"

    assert not xmp, f"XMP metadata should be empty with zero detections, got: {xmp!r}"


# ---------------------------------------------------------------------------
# FR22/FR23 — Non-incremental save: no leaked content, single %%EOF
# ---------------------------------------------------------------------------


def test_non_incremental_save_no_leaked_content() -> None:
    pii = "UNIQUE_MARKER_STRING"
    pdf_path = _single_page_pdf(pii)
    det = _detection_for_text(pdf_path, pii)
    out = _output_path()

    redact_pdf(pdf_path, [det], out)

    raw = out.read_bytes()

    assert pii.encode() not in raw, (
        "Redacted PII found in raw output bytes — " "non-incremental save leaked content"
    )

    # Non-incremental save produces exactly one %%EOF marker
    eof_count = raw.count(b"%%EOF")
    assert eof_count == 1, (
        f"Expected exactly 1 %%EOF marker (non-incremental save), found {eof_count}. "
        "garbage=4 + non-incremental mode should collapse to a single revision."
    )


# ---------------------------------------------------------------------------
# NFR5 — 10-page redaction+sanitization completes under 5 seconds
# ---------------------------------------------------------------------------


@pytest.mark.slow
def test_ten_page_redaction_under_five_seconds() -> None:
    pages = [f"Patient{i} Nom{i}" for i in range(10)]
    pdf_path = _multi_page_pdf(pages)

    detections: list[Detection] = []
    for i, text in enumerate(pages):
        detections.append(_detection_for_text(pdf_path, text, page_num=i))

    out = _output_path()

    start = time.monotonic()
    redact_pdf(pdf_path, detections, out)
    elapsed = time.monotonic() - start

    assert (
        elapsed < 5.0
    ), f"10-page redaction+sanitization took {elapsed:.2f}s, exceeds 5s NFR5 budget"
