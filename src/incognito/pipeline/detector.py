from __future__ import annotations

import json
import re
from typing import Final

from pydantic import ValidationError

from incognito.core.exceptions import DetectionError
from incognito.models import RawDetection, TextBlock
from incognito.pipeline.detect_ner import GenerateFn

_SYSTEM_PROMPT: Final[str] = (
    "Extract all PII entities (person, address, phone, email) from this French text.\n"
    "Return JSON array of {text, entity_type, start, end} where start/end are "
    "character offsets in the input.\n"
    "If no PII found, return []."
)

_FENCE_RE: Final[re.Pattern[str]] = re.compile(
    r"^\s*```(?:json)?\s*\n(.*?)\n\s*```\s*$",
    re.DOTALL,
)


def detect(blocks: list[TextBlock], generate_fn: GenerateFn) -> list[RawDetection]:
    detections: list[RawDetection] = []
    for block in blocks:
        if not block.text.strip():
            continue
        detections.extend(_detect_block(block, generate_fn))
    return detections


def _detect_block(block: TextBlock, generate_fn: GenerateFn) -> list[RawDetection]:
    try:
        response = generate_fn(block.text, system=_SYSTEM_PROMPT)
    except DetectionError:
        raise
    except Exception as exc:
        raise DetectionError("NER inference failed") from exc

    items = _parse_response(response)
    try:
        return [
            RawDetection.model_validate(
                item | {"page": block.page, "bbox": block.bbox, "block_index": block.block_index}
            )
            for item in items
        ]
    except ValidationError as exc:
        raise DetectionError("Failed to construct detection from response") from exc


def _strip_code_fences(response: str) -> str:
    match = _FENCE_RE.match(response)
    return match.group(1) if match else response


def _parse_response(response: str) -> list[dict[str, object]]:
    stripped = _strip_code_fences(response)
    try:
        data = json.loads(stripped)
    except json.JSONDecodeError as exc:
        raise DetectionError("Gemma returned malformed JSON") from exc

    if not isinstance(data, list):
        raise DetectionError("Gemma response is not a JSON array")

    validated: list[dict[str, object]] = []
    for item in data:
        if not isinstance(item, dict):
            raise DetectionError("Gemma response item is not an object")
        required = {"text", "entity_type", "start", "end"}
        missing = required - item.keys()
        if missing:
            raise DetectionError(f"Detection missing required fields: {missing}")
        validated.append(item)
    return validated
