from __future__ import annotations

import logging
from typing import Final

from incognito.core.exceptions import DetectionError
from incognito.models import Detection, RawDetection, TextBlock

logger: Final = logging.getLogger(__name__)


def validate(
    raw_detections: list[RawDetection],
    blocks: list[TextBlock],
) -> list[Detection]:
    block_map = _build_block_map(blocks)
    valid: list[Detection] = []
    for raw in raw_detections:
        key = (raw.page, raw.block_index)
        block = block_map.get(key)
        if block is None:
            continue
        if raw.start < 0 or raw.end > len(block.text) or raw.start >= raw.end:
            continue
        if block.text[raw.start : raw.end] != raw.text:
            continue
        valid.append(
            Detection(
                text=raw.text,
                entity_type=raw.entity_type,
                page=raw.page,
                start=raw.start,
                end=raw.end,
                bbox=raw.bbox,
            )
        )
    logger.info("Validated %d/%d detections", len(valid), len(raw_detections))
    return valid


def _build_block_map(blocks: list[TextBlock]) -> dict[tuple[int, int], TextBlock]:
    block_map: dict[tuple[int, int], TextBlock] = {}
    for block in blocks:
        key = (block.page, block.block_index)
        if key in block_map:
            msg = f"Duplicate block key (page={block.page}, block_index={block.block_index})"
            raise DetectionError(msg)
        block_map[key] = block
    return block_map
