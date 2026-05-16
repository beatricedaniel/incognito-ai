from __future__ import annotations

import logging
import re
from collections import defaultdict
from typing import Final, Protocol

from incognito.core.config import (
    GEMMA_CONFIRM_SYSTEM,
    GLINER_LABELS,
    GLINER_THRESHOLD_ADDRESS,
    GLINER_THRESHOLD_PERSON,
)
from incognito.gliner.loader import load_model
from incognito.models import EntityType, RawDetection, TextBlock

logger: Final = logging.getLogger(__name__)

_CONFIRM_RE: Final[re.Pattern[str]] = re.compile(r"(\d+)\s*[:.\-)\s]\s*([01])")

_THRESHOLDS: Final[dict[str, float]] = {
    "person": GLINER_THRESHOLD_PERSON,
    "address": GLINER_THRESHOLD_ADDRESS,
}

_LABEL_TO_ENTITY: Final[dict[str, EntityType]] = {
    "person": EntityType.PERSON,
    "address": EntityType.ADDRESS,
}

_MAX_CANDIDATES_PER_PROMPT: Final[int] = 10


class GenerateFn(Protocol):
    def __call__(self: GenerateFn, prompt: str, system: str = "") -> str: ...


def detect_gliner(blocks: list[TextBlock]) -> list[RawDetection]:
    model = load_model()
    detections: list[RawDetection] = []
    for block in blocks:
        if not block.text.strip():
            continue
        entities = model.predict_entities(block.text, list(GLINER_LABELS))
        candidates = _filter_and_validate(entities, block)
        survivors = _resolve_same_type_overlaps(candidates)
        detections.extend(survivors)
    return detections


def confirm_candidates(
    blocks: list[TextBlock],
    candidates: list[RawDetection],
    generate_fn: GenerateFn,
) -> list[RawDetection]:
    if not candidates:
        return []

    block_map: dict[tuple[int, int], TextBlock] = {(b.page, b.block_index): b for b in blocks}

    grouped: dict[tuple[int, int], list[RawDetection]] = defaultdict(list)
    for c in candidates:
        grouped[(c.page, c.block_index)].append(c)

    confirmed: list[RawDetection] = []
    for key, group in grouped.items():
        block = block_map.get(key)
        if block is None:
            confirmed.extend(group)
            continue
        confirmed.extend(_confirm_group(block, group, generate_fn))
    return confirmed


def deduplicate(
    regex_dets: list[RawDetection],
    gliner_dets: list[RawDetection],
) -> list[RawDetection]:
    surviving_gliner: list[RawDetection] = []
    for g in gliner_dets:
        if not any(_overlaps(g, r) for r in regex_dets):
            surviving_gliner.append(g)
    return list(regex_dets) + surviving_gliner


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _filter_and_validate(
    entities: list[dict[str, object]],
    block: TextBlock,
) -> list[tuple[RawDetection, float]]:
    results: list[tuple[RawDetection, float]] = []
    for ent in entities:
        label = str(ent.get("label", ""))
        if label not in _THRESHOLDS:
            continue
        raw_score = ent.get("score", 0.0)
        score = float(raw_score) if isinstance(raw_score, int | float) else 0.0
        if score < _THRESHOLDS[label]:
            continue
        raw_start = ent.get("start", 0)
        raw_end = ent.get("end", 0)
        start = int(raw_start) if isinstance(raw_start, int | float) else 0
        end = int(raw_end) if isinstance(raw_end, int | float) else 0
        text = str(ent.get("text", ""))
        end = min(end, len(block.text))
        if start >= end:
            continue
        if block.text[start:end] != text:
            corrected = _try_correct_offsets(block.text, text, start)
            if corrected is None:
                logger.debug("GLiNER offset mismatch, dropping %s at %d:%d", label, start, end)
                continue
            start, end = corrected
        det = RawDetection(
            text=text,
            entity_type=_LABEL_TO_ENTITY[label],
            start=start,
            end=end,
            page=block.page,
            bbox=block.bbox,
            block_index=block.block_index,
        )
        results.append((det, score))
    return results


def _try_correct_offsets(
    block_text: str, target: str, reported_start: int
) -> tuple[int, int] | None:
    search_start = max(0, reported_start - 5)
    search_end = min(len(block_text), reported_start + len(target) + 5)
    idx = block_text.find(target, search_start, search_end)
    if idx == -1:
        return None
    return idx, idx + len(target)


def _resolve_same_type_overlaps(
    candidates: list[tuple[RawDetection, float]],
) -> list[RawDetection]:
    sorted_candidates = sorted(
        candidates, key=lambda x: (-x[1], x[0].start, -(x[0].end - x[0].start))
    )
    kept: list[tuple[RawDetection, float]] = []
    for det, score in sorted_candidates:
        conflict = False
        for existing, _ in kept:
            if existing.entity_type == det.entity_type and _spans_overlap(
                existing.start, existing.end, det.start, det.end
            ):
                conflict = True
                break
        if not conflict:
            kept.append((det, score))
    return [d for d, _ in kept]


def _confirm_group(
    block: TextBlock,
    group: list[RawDetection],
    generate_fn: GenerateFn,
) -> list[RawDetection]:
    confirmed: list[RawDetection] = []
    for batch_start in range(0, len(group), _MAX_CANDIDATES_PER_PROMPT):
        batch = group[batch_start : batch_start + _MAX_CANDIDATES_PER_PROMPT]
        confirmed.extend(_confirm_batch(block, batch, generate_fn))
    return confirmed


def _confirm_batch(
    block: TextBlock,
    batch: list[RawDetection],
    generate_fn: GenerateFn,
) -> list[RawDetection]:
    prompt = _build_confirm_prompt(block.text, batch)
    try:
        response = generate_fn(prompt, system=GEMMA_CONFIRM_SYSTEM)
    except Exception:
        logger.warning(
            "Gemma confirmation failed for block %d:%d, confirming all",
            block.page,
            block.block_index,
        )
        return list(batch)

    verdicts = _parse_confirm_response(response, len(batch))
    return [batch[i] for i in range(len(batch)) if verdicts.get(i + 1, True)]


def _build_confirm_prompt(block_text: str, candidates: list[RawDetection]) -> str:
    lines = ["Text:", '"""', block_text, '"""', "Candidates:"]
    for i, c in enumerate(candidates, 1):
        lines.append(f'{i}. "{c.text}" [{c.entity_type}]')
    lines.append("Answer:")
    return "\n".join(lines)


def _parse_confirm_response(response: str, count: int) -> dict[int, bool]:
    results: dict[int, bool] = {}
    for match in _CONFIRM_RE.finditer(response):
        idx = int(match.group(1))
        if 1 <= idx <= count:
            results[idx] = match.group(2) == "1"
    for i in range(1, count + 1):
        if i not in results:
            results[i] = True
    return results


def _overlaps(a: RawDetection, b: RawDetection) -> bool:
    if a.page != b.page or a.block_index != b.block_index:
        return False
    return _spans_overlap(a.start, a.end, b.start, b.end)


def _spans_overlap(start_a: int, end_a: int, start_b: int, end_b: int) -> bool:
    return max(start_a, start_b) < min(end_a, end_b)
