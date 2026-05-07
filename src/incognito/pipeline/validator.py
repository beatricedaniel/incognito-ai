from __future__ import annotations

import logging
from typing import Final

from incognito.models import BBox, Detection, RawDetection, TextBlock

logger: Final = logging.getLogger(__name__)


def validate_detections(
    block: TextBlock,
    raw_detections: list[RawDetection],
) -> list[Detection]:
    valid: list[Detection] = []
    for raw in raw_detections:
        if raw.start < 0 or raw.end > len(block.text) or raw.start >= raw.end:
            continue
        if block.text[raw.start : raw.end] != raw.text:
            continue
        valid.append(
            Detection(
                text=raw.text,
                entity_type=raw.entity_type,
                page=block.page,
                start=raw.start,
                end=raw.end,
                bbox=BBox(
                    x=block.bbox.x,
                    y=block.bbox.y,
                    width=block.bbox.width,
                    height=block.bbox.height,
                ),
            )
        )
    logger.info(
        "Validated %d/%d detections for block %d on page %d",
        len(valid),
        len(raw_detections),
        block.block_index,
        block.page,
    )
    return valid
