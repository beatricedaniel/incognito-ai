from __future__ import annotations

from typing import Final

from incognito.core.exceptions import DetectionError
from incognito.models import EntityType, RawDetection, TextBlock
from incognito.pipeline.detect_ner import (
    GenerateFn,
    confirm_candidates,
    deduplicate,
    detect_gliner,
)
from incognito.pipeline.detect_regex import detect_regex

__all__: Final[list[str]] = ["GenerateFn", "detect"]


def detect(blocks: list[TextBlock], generate_fn: GenerateFn) -> list[RawDetection]:
    """Three-stage pipeline: regex → GLiNER → dedup → Gemma confirm."""
    try:
        regex_dets = detect_regex(blocks)
        gliner_dets = detect_gliner(blocks)
    except DetectionError:
        raise
    except Exception as exc:
        raise DetectionError("Detection stage failed") from exc

    deduped = deduplicate(regex_dets, gliner_dets)
    gliner_candidates = deduped[len(regex_dets) :]
    address_candidates = [c for c in gliner_candidates if c.entity_type == EntityType.ADDRESS]
    non_address_candidates = [c for c in gliner_candidates if c.entity_type != EntityType.ADDRESS]
    confirmed = confirm_candidates(blocks, non_address_candidates, generate_fn)
    return regex_dets + address_candidates + confirmed
