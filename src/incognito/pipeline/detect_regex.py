from __future__ import annotations

import re
from typing import Final

from incognito.models import EntityType, RawDetection, TextBlock

_SEP: Final[str] = r"[\s.\-\u00AD\u200B]"

_PHONE_RE: Final[re.Pattern[str]] = re.compile(rf"(?:\+33\s?|0)[1-9](?:{_SEP}?\d{{2}}){{4}}")

_PHONE_US_RE: Final[re.Pattern[str]] = re.compile(
    r"\(\d{3}\)"
    rf"{_SEP}?\d{{3}}"
    rf"{_SEP}?\d{{4}}"
    r"|"
    r"\b\d{3}"
    rf"[\-\.]{_SEP}?\d{{3}}"
    rf"[\-\.]{_SEP}?\d{{4}}"
)

_EMAIL_RE: Final[re.Pattern[str]] = re.compile(
    r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9\-]+(?:\.[a-zA-Z0-9\-]+)*\.[a-zA-Z]{2,}"
)

_PATTERNS: Final[list[tuple[re.Pattern[str], EntityType]]] = [
    (_PHONE_RE, EntityType.PHONE),
    (_PHONE_US_RE, EntityType.PHONE),
    (_EMAIL_RE, EntityType.EMAIL),
]


def detect_regex(blocks: list[TextBlock]) -> list[RawDetection]:
    detections: list[RawDetection] = []
    for block in blocks:
        if not block.text.strip():
            continue
        for pattern, entity_type in _PATTERNS:
            for match in pattern.finditer(block.text):
                detections.append(
                    RawDetection(
                        text=match.group(),
                        entity_type=entity_type,
                        start=match.start(),
                        end=match.end(),
                        page=block.page,
                        bbox=block.bbox,
                        block_index=block.block_index,
                    )
                )
    return detections
