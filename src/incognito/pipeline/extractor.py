from __future__ import annotations

import logging
from pathlib import Path
from typing import Final

import fitz

from incognito.core.exceptions import PdfError
from incognito.models import BBox, TextBlock

logger: Final = logging.getLogger(__name__)


def extract_blocks(pdf_path: Path) -> list[TextBlock]:
    try:
        doc = fitz.open(pdf_path)
    except Exception as exc:
        raise PdfError("Failed to open PDF") from exc

    blocks: list[TextBlock] = []
    page_count = len(doc)
    try:
        for page_num in range(page_count):
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
    finally:
        doc.close()

    if not blocks:
        raise PdfError("No extractable text found in PDF")

    logger.info("Extracted %d text blocks from %d pages", len(blocks), page_count)
    return blocks
