from __future__ import annotations

import ast
import inspect
import logging
import struct
import tempfile
import zlib
from pathlib import Path

import fitz
import pytest

from incognito.api.events import STAGE_UPDATE, sse_event
from incognito.core.exceptions import PdfError
from incognito.models import TextBlock
from incognito.pipeline.extractor import extract_blocks

# ---------------------------------------------------------------------------
# PDF fixture factories — real in-memory PDFs via fitz, no external files
# ---------------------------------------------------------------------------


def _write_pdf_bytes(data: bytes) -> Path:
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(data)
    return Path(tmp.name)


def _single_page_pdf(text: str = "Bonjour le monde") -> Path:
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


def _minimal_png() -> bytes:
    def _chunk(name: bytes, data: bytes) -> bytes:
        c = struct.pack(">I", len(data)) + name + data
        return c + struct.pack(">I", zlib.crc32(name + data) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    raw = b"\x00\xff\xff\xff"
    idat = zlib.compress(raw)
    return (
        b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", ihdr) + _chunk(b"IDAT", idat) + _chunk(b"IEND", b"")
    )


def _image_only_pdf() -> Path:
    doc = fitz.open()
    page = doc.new_page(width=200, height=200)
    page.insert_image(fitz.Rect(10, 10, 190, 190), stream=_minimal_png())
    pdf_bytes = doc.tobytes()
    doc.close()
    return _write_pdf_bytes(pdf_bytes)


def _mixed_content_pdf() -> Path:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Texte visible", fontsize=12)
    page.insert_image(fitz.Rect(200, 200, 400, 400), stream=_minimal_png())
    pdf_bytes = doc.tobytes()
    doc.close()
    return _write_pdf_bytes(pdf_bytes)


def _corrupt_pdf(tmp_path: Path) -> Path:
    p = tmp_path / "corrupt.pdf"
    p.write_bytes(b"this is not a pdf at all \x00\x01\x02")
    return p


# ---------------------------------------------------------------------------
# AC 1 — TextBlock shape
# ---------------------------------------------------------------------------


def test_returns_list_of_text_blocks() -> None:
    path = _single_page_pdf("Jean Dupont habite Paris")
    blocks = extract_blocks(path)
    assert isinstance(blocks, list)
    assert len(blocks) >= 1
    block = blocks[0]
    assert isinstance(block, TextBlock)
    assert isinstance(block.text, str)
    assert isinstance(block.page, int)
    assert isinstance(block.block_index, int)


def test_text_block_has_all_fields() -> None:
    path = _single_page_pdf("Marie Curie")
    blocks = extract_blocks(path)
    block = blocks[0]
    # page is 0-indexed
    assert block.page == 0
    # bbox encodes position and size
    assert block.bbox.x >= 0
    assert block.bbox.y >= 0
    assert block.bbox.width > 0
    assert block.bbox.height > 0
    assert block.block_index >= 0


def test_text_content_preserved() -> None:
    path = _single_page_pdf("Numéro de sécurité sociale 123456789")
    blocks = extract_blocks(path)
    combined = "".join(b.text for b in blocks)
    assert "123456789" in combined


# ---------------------------------------------------------------------------
# AC 2 — Multi-page: all pages returned in page order
# ---------------------------------------------------------------------------


def test_multi_page_returns_blocks_for_all_pages() -> None:
    texts = ["Page un contenu", "Page deux contenu", "Page trois contenu"]
    path = _multi_page_pdf(texts)
    blocks = extract_blocks(path)
    pages_seen = {b.page for b in blocks}
    assert 0 in pages_seen
    assert 1 in pages_seen
    assert 2 in pages_seen


def test_multi_page_blocks_in_page_order() -> None:
    path = _multi_page_pdf(["Alpha", "Beta", "Gamma"])
    blocks = extract_blocks(path)
    page_numbers = [b.page for b in blocks]
    assert page_numbers == sorted(page_numbers), "blocks must be sorted by page number"


def test_multi_page_page_numbers_are_zero_indexed() -> None:
    path = _multi_page_pdf(["first", "second"])
    blocks = extract_blocks(path)
    pages = {b.page for b in blocks}
    assert min(pages) == 0


# ---------------------------------------------------------------------------
# AC 3 — Mixed content: image blocks skipped
# ---------------------------------------------------------------------------


def test_mixed_content_only_text_blocks_returned() -> None:
    path = _mixed_content_pdf()
    blocks = extract_blocks(path)
    assert len(blocks) >= 1
    combined = "".join(b.text for b in blocks)
    assert "Texte visible" in combined


def test_image_blocks_do_not_appear_as_text_blocks() -> None:
    path = _mixed_content_pdf()
    blocks = extract_blocks(path)
    # None of the blocks should have empty text (image blocks stripped)
    for block in blocks:
        assert block.text.strip() != ""


# ---------------------------------------------------------------------------
# AC 4 — SSE stage_update event format
# ---------------------------------------------------------------------------


def test_sse_event_extracting_format() -> None:
    """The expected SSE payload a caller emits before calling extract_blocks."""
    event = sse_event(
        STAGE_UPDATE, {"stage": "extracting", "message": "Extracting text from PDF\u2026"}
    )
    assert event.startswith("event: stage_update\n")
    assert '"stage": "extracting"' in event
    # json.dumps escapes non-ASCII by default; both literal and escaped forms are valid JSON
    assert "Extracting text from PDF\u2026" in event or r"Extracting text from PDF\u2026" in event
    assert event.endswith("\n\n")


def test_sse_event_structure_double_newline_terminator() -> None:
    event = sse_event(STAGE_UPDATE, {"stage": "extracting", "message": "x"})
    lines = event.split("\n")
    # SSE format: event line, data line, blank line, blank line
    assert lines[0].startswith("event:")
    assert lines[1].startswith("data:")
    assert lines[-1] == ""
    assert lines[-2] == ""


# ---------------------------------------------------------------------------
# AC 5 — No HTTP client imports in pipeline/extractor.py
# ---------------------------------------------------------------------------


def test_extractor_has_no_http_client_imports() -> None:
    extractor_path = (
        Path(__file__).parent.parent / "src" / "incognito" / "pipeline" / "extractor.py"
    )
    source = extractor_path.read_text()
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


def test_extractor_function_is_synchronous() -> None:
    assert not inspect.iscoroutinefunction(extract_blocks)


# ---------------------------------------------------------------------------
# Failure mode 6 — Image-only PDF raises PdfError
# ---------------------------------------------------------------------------


def test_image_only_pdf_raises_pdf_error() -> None:
    """Returning [] for an image-only PDF would silently pass the original — catastrophic."""
    path = _image_only_pdf()
    with pytest.raises(PdfError):
        extract_blocks(path)


# ---------------------------------------------------------------------------
# Failure mode 7 — Corrupt file raises PdfError
# ---------------------------------------------------------------------------


def test_corrupt_file_raises_pdf_error(tmp_path: Path) -> None:
    path = _corrupt_pdf(tmp_path)
    with pytest.raises(PdfError):
        extract_blocks(path)


def test_nonexistent_file_raises_pdf_error(tmp_path: Path) -> None:
    path = tmp_path / "does_not_exist.pdf"
    with pytest.raises(PdfError):
        extract_blocks(path)


# ---------------------------------------------------------------------------
# Failure mode 8 — Resource leak: doc closed even on mid-extraction failure
# ---------------------------------------------------------------------------


def test_document_closed_on_exception(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """If extraction raises, fitz.Document.close() must still be called."""
    # Build the fixture path BEFORE patching fitz.open — the fixture factory also uses fitz.open
    path = _single_page_pdf()

    closed: list[bool] = []
    original_fitz_open = fitz.open

    class _TrackingDoc:
        def __init__(self: _TrackingDoc, wrapped: fitz.Document) -> None:
            self._doc = wrapped

        def __len__(self: _TrackingDoc) -> int:
            return len(self._doc)

        def __getitem__(self: _TrackingDoc, idx: int) -> fitz.Page:
            raise RuntimeError("simulated mid-extraction failure")

        def close(self: _TrackingDoc) -> None:
            closed.append(True)
            self._doc.close()

    def patched_open(path: object) -> _TrackingDoc:
        return _TrackingDoc(original_fitz_open(path))  # type: ignore[arg-type]

    monkeypatch.setattr(fitz, "open", patched_open)

    with pytest.raises(RuntimeError, match="simulated"):
        extract_blocks(path)

    assert closed, "fitz document was not closed after extraction failure (resource leak)"


# ---------------------------------------------------------------------------
# Regression: doc.close() before len(doc) in logger produces wrong page count
# ---------------------------------------------------------------------------


def test_logger_page_count_does_not_use_closed_doc(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """After doc.close(), len(doc) returns 0 in PyMuPDF — the log line must fire before close."""
    texts = ["page one", "page two", "page three"]
    path = _multi_page_pdf(texts)
    with caplog.at_level(logging.INFO, logger="incognito.pipeline.extractor"):
        extract_blocks(path)
    log_messages = [r.message for r in caplog.records]
    # Must have logged the correct page count (3), not 0
    assert any(
        "3" in msg for msg in log_messages
    ), f"Expected page count 3 in log output, got: {log_messages}"
