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

    for det in detections:
        if det.dismissed:
            continue
        page = doc[det.page]
        rect = fitz.Rect(
            det.bbox.x,
            det.bbox.y,
            det.bbox.x + det.bbox.width,
            det.bbox.y + det.bbox.height,
        )
        page.add_redact_annot(rect)

    for page_num in range(len(doc)):
        doc[page_num].apply_redactions()

    doc.set_metadata({})
    doc.del_xml_metadata()
    doc.save(output_path, garbage=4, deflate=True, clean=True)
    doc.close()

    logger.info("Redacted PDF saved, %d detections applied", len(detections))
    return output_path
