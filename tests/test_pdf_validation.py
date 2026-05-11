from __future__ import annotations

import struct
import tempfile
import zlib
from pathlib import Path
from unittest.mock import patch

import fitz
import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from incognito.core.config import TEMP_PREFIX

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_pdf() -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Sample text for validation.")
    b = doc.tobytes()
    doc.close()
    return b


def _make_encrypted_pdf() -> bytes:
    doc = fitz.open()
    doc.new_page()
    b = doc.tobytes(encryption=fitz.PDF_ENCRYPT_AES_256, user_pw="secret")
    doc.close()
    return b


def _make_image_only_pdf() -> bytes:
    # Build a minimal 1x1 red pixel PNG in memory.
    def _png_chunk(tag: bytes, data: bytes) -> bytes:
        length = struct.pack(">I", len(data))
        crc = struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        return length + tag + data + crc

    signature = b"\x89PNG\r\n\x1a\n"
    ihdr = _png_chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
    raw_pixel = b"\x00\xff\x00\x00"  # filter byte + R G B
    compressed = zlib.compress(raw_pixel)
    idat = _png_chunk(b"IDAT", compressed)
    iend = _png_chunk(b"IEND", b"")
    png_bytes = signature + ihdr + idat + iend

    doc = fitz.open()
    page = doc.new_page(width=100, height=100)
    page.insert_image(fitz.Rect(0, 0, 100, 100), stream=png_bytes)
    b = doc.tobytes()
    doc.close()
    return b


def _make_app(tmp_path: Path) -> FastAPI:
    static_dir = tmp_path / "static"
    static_dir.mkdir()
    (static_dir / "index.html").write_text("<html></html>")
    with (
        patch("incognito.app.STATIC_DIR", static_dir),
        patch("incognito.app.cleanup_orphaned_temp_dirs"),
    ):
        from incognito.app import create_app

        return create_app()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def app(tmp_path: Path) -> FastAPI:
    return _make_app(tmp_path)


@pytest_asyncio.fixture()
async def client(app: FastAPI) -> AsyncClient:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


# ---------------------------------------------------------------------------
# AC1 — non-PDF file type → 400 with exact error body
# ---------------------------------------------------------------------------


async def test_non_pdf_returns_400_with_correct_body(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/upload",
        files={"file": ("note.txt", b"hello world", "text/plain")},
    )

    assert resp.status_code == 400
    body = resp.json()
    assert body["error"] == "Invalid file type"
    assert body["detail"] == "Only PDF files are supported"


async def test_docx_returns_400(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/upload",
        files={
            "file": (
                "report.docx",
                b"PK\x03\x04fake-docx-content",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )

    assert resp.status_code == 400
    assert resp.json()["error"] == "Invalid file type"


async def test_png_returns_400(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/upload",
        files={"file": ("scan.png", b"\x89PNG\r\n\x1a\n", "image/png")},
    )

    assert resp.status_code == 400
    assert resp.json()["error"] == "Invalid file type"


# ---------------------------------------------------------------------------
# AC2 — encrypted PDF → 400 with exact error body
# ---------------------------------------------------------------------------


async def test_encrypted_pdf_returns_400(client: AsyncClient) -> None:
    encrypted = _make_encrypted_pdf()
    resp = await client.post(
        "/api/upload",
        files={"file": ("protected.pdf", encrypted, "application/pdf")},
    )

    assert resp.status_code == 400
    body = resp.json()
    assert body["error"] == "Unsupported PDF"
    assert body["detail"] == "Encrypted PDFs are not supported"


# ---------------------------------------------------------------------------
# AC3 — image-only PDF → 400 with exact error body
# ---------------------------------------------------------------------------


async def test_image_only_pdf_returns_400(client: AsyncClient) -> None:
    image_pdf = _make_image_only_pdf()
    resp = await client.post(
        "/api/upload",
        files={"file": ("scanned.pdf", image_pdf, "application/pdf")},
    )

    assert resp.status_code == 400
    body = resp.json()
    assert body["error"] == "Unsupported PDF"
    assert body["detail"] == "This PDF contains no extractable text (scanned/image-only)"


# ---------------------------------------------------------------------------
# Corrupted bytes with application/pdf content type → 400
# ---------------------------------------------------------------------------


async def test_corrupted_file_with_pdf_content_type_returns_400(client: AsyncClient) -> None:
    garbage = b"\x00\x01\x02\x03this is not a pdf at all"
    resp = await client.post(
        "/api/upload",
        files={"file": ("corrupt.pdf", garbage, "application/pdf")},
    )

    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# AC4 — validation failure cleans up temp files immediately
# ---------------------------------------------------------------------------


async def test_validation_failure_cleans_temp_files(client: AsyncClient) -> None:
    encrypted = _make_encrypted_pdf()

    tmp_root = Path(tempfile.gettempdir())
    before = {p for p in tmp_root.iterdir() if p.is_dir() and p.name.startswith(TEMP_PREFIX)}

    resp = await client.post(
        "/api/upload",
        files={"file": ("protected.pdf", encrypted, "application/pdf")},
    )

    assert resp.status_code == 400

    after = {p for p in tmp_root.iterdir() if p.is_dir() and p.name.startswith(TEMP_PREFIX)}
    leaked = after - before
    assert not leaked, f"Temp dirs leaked after validation failure: {leaked}"


# ---------------------------------------------------------------------------
# application/octet-stream — valid PDF accepted, non-PDF rejected
# ---------------------------------------------------------------------------


async def test_octet_stream_with_valid_pdf_accepted(client: AsyncClient) -> None:
    pdf_bytes = _make_pdf()
    resp = await client.post(
        "/api/upload",
        files={"file": ("upload.pdf", pdf_bytes, "application/octet-stream")},
    )

    # Must not reject valid PDF just because content-type is octet-stream.
    assert resp.status_code == 201


async def test_octet_stream_with_non_pdf_rejected(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/upload",
        files={"file": ("upload.bin", b"clearly not pdf bytes", "application/octet-stream")},
    )

    assert resp.status_code == 400
