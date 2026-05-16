from __future__ import annotations

from typing import Final

from incognito.core.exceptions import DetectionError
from incognito.models import RawDetection, TextBlock
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
    # deduplicate returns regex_dets + surviving GLiNER (in that order).
    # Regex detections are auto-confirmed; only GLiNER candidates need Gemma.
    gliner_candidates = deduped[len(regex_dets) :]
    confirmed = confirm_candidates(blocks, gliner_candidates, generate_fn)
    return regex_dets + confirmed
