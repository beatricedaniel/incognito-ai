from __future__ import annotations

import logging
from pathlib import Path
from typing import Final

import fitz

from incognito.core.exceptions import PdfError
from incognito.models import BBox, TextBlock

logger: Final = logging.getLogger(__name__)

_ENCRYPTED_KEYWORDS: Final = ("encrypt", "password")


def validate_pdf(pdf_path: Path) -> None:
    try:
        doc = fitz.open(pdf_path)
    except Exception as exc:
        msg = str(exc).lower()
        if any(kw in msg for kw in _ENCRYPTED_KEYWORDS):
            raise PdfError("Encrypted PDFs are not supported", error="Unsupported PDF") from exc
        raise PdfError(
            "The file could not be read as a valid PDF", error="Unsupported PDF"
        ) from exc

    try:
        if doc.needs_pass:
            raise PdfError("Encrypted PDFs are not supported", error="Unsupported PDF")

        for page_num in range(len(doc)):
            page = doc[page_num]
            page_dict = page.get_text("dict")
            for block in page_dict.get("blocks", []):
                if block.get("type") != 0:
                    continue
                lines = block.get("lines", [])
                text = "".join(span["text"] for line in lines for span in line.get("spans", []))
                if text.strip():
                    return
        raise PdfError(
            "This PDF contains no extractable text (scanned/image-only)",
            error="Unsupported PDF",
        )
    finally:
        doc.close()


def extract_blocks(pdf_path: Path) -> list[TextBlock]:
    try:
        doc = fitz.open(pdf_path)
    except Exception as exc:
        raise PdfError("Failed to open PDF") from exc

    blocks: list[TextBlock] = []
    for page_num in range(len(doc)):
        page = doc[page_num]
        page_dict = page.get_text("dict")
        for idx, block in enumerate(page_dict.get("blocks", [])):
            if block.get("type") != 0:
                continue
            lines = block.get("lines", [])
            text = "".join(span["text"] for line in lines for span in line.get("spans", []))
            if not text.strip():
                continue
            x0, y0, x1, y1 = block["bbox"]
            blocks.append(
                TextBlock(
                    text=text,
                    page=page_num,
                    bbox=BBox(x=x0, y=y0, width=x1 - x0, height=y1 - y0),
                    block_index=idx,
                )
            )
    doc.close()
    logger.info("Extracted %d text blocks from %d pages", len(blocks), len(doc))
    return blocks
