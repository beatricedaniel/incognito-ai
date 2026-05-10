from __future__ import annotations

import json
import logging
from typing import Final

from incognito.core.exceptions import DetectionError
from incognito.models import RawDetection, TextBlock
from incognito.ollama.manager import generate

logger: Final = logging.getLogger(__name__)

_SYSTEM_PROMPT: Final[str] = (
    "Extract all PII entities (person, address, phone, email) from this French text.\n"
    "Return JSON array of {text, entity_type, start, end} where start/end are "
    "character offsets in the input.\n"
    "If no PII found, return []."
)


def detect_entities(block: TextBlock) -> list[RawDetection]:
    if not block.text.strip():
        return []

    prompt = block.text
    try:
        response = generate(prompt, system=_SYSTEM_PROMPT)
    except Exception as exc:
        raise DetectionError("NER inference failed") from exc

    return _parse_response(response)


def _parse_response(response: str) -> list[RawDetection]:
    try:
        data = json.loads(response)
    except json.JSONDecodeError:
        logger.warning("Failed to parse NER response as JSON")
        return []

    if not isinstance(data, list):
        return []

    detections: list[RawDetection] = []
    for item in data:
        try:
            detections.append(RawDetection(**item))
        except (TypeError, ValueError):
            continue
    return detections
