from __future__ import annotations

import logging
from pathlib import Path
from typing import Final

import fitz

from incognito.core.exceptions import RedactionError
from incognito.models import Detection

logger: Final = logging.getLogger(__name__)


def redact_pdf(
    pdf_path: Path,
    detections: list[Detection],
    output_path: Path,
) -> Path:
    try:
        doc = fitz.open(pdf_path)
    except Exception as exc:
        raise RedactionError("Failed to open PDF for redaction") from exc

    try:
        applied = 0
        redacted_pages: set[int] = set()
        for det in detections:
            if det.dismissed:
                continue
            try:
                page = doc[det.page]
            except IndexError:
                raise RedactionError(
                    f"Page index {det.page} out of range for {len(doc)}-page document"
                ) from None
            rect = fitz.Rect(
                det.bbox.x,
                det.bbox.y,
                det.bbox.x + det.bbox.width,
                det.bbox.y + det.bbox.height,
            )
            page.add_redact_annot(rect, fill=(0, 0, 0))
            redacted_pages.add(det.page)
            applied += 1

        for page_num in redacted_pages:
            doc[page_num].apply_redactions()

        doc.set_metadata({})
        doc.del_xml_metadata()
        doc.save(output_path, garbage=4, deflate=True, clean=True)
    finally:
        doc.close()

    logger.info("Redacted PDF saved, %d detections applied", applied)
    return output_path
