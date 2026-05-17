from __future__ import annotations

import time

from incognito.core.config import GEMMA_CONFIRM_SYSTEM
from incognito.models import BBox, EntityType, RawDetection, TextBlock
from incognito.pipeline.detect_regex import detect_regex

_BBOX = BBox(x=0.0, y=0.0, width=200.0, height=15.0)


def _block(text: str, page: int = 0, block_index: int = 0) -> TextBlock:
    return TextBlock(text=text, page=page, bbox=_BBOX, block_index=block_index)


def _det(  # noqa: PLR0913
    text: str,
    entity_type: EntityType,
    start: int,
    end: int,
    page: int = 0,
    block_index: int = 0,
) -> RawDetection:
    return RawDetection(
        text=text,
        entity_type=entity_type,
        start=start,
        end=end,
        page=page,
        bbox=_BBOX,
        block_index=block_index,
    )


# ---------------------------------------------------------------------------
# GEMMA_CONFIRM_SYSTEM prompt structure
# ---------------------------------------------------------------------------


def test_system_prompt_has_pii_categories() -> None:
    assert "Real PII (answer 1)" in GEMMA_CONFIRM_SYSTEM
    assert "NOT PII (answer 0)" in GEMMA_CONFIRM_SYSTEM


def test_system_prompt_has_few_shot_examples() -> None:
    assert "Mr. Peter Lawson" in GEMMA_CONFIRM_SYSTEM
    assert "Saint Joseph Medical Center" in GEMMA_CONFIRM_SYSTEM


# ---------------------------------------------------------------------------
# US phone regex — positive cases
# ---------------------------------------------------------------------------


def test_us_phone_parenthesized() -> None:
    text = "Call (612) 555-0184 for details."
    block = _block(text)
    results = detect_regex([block])

    phones = [d for d in results if d.entity_type == EntityType.PHONE]
    assert len(phones) == 1
    det = phones[0]
    assert det.text == "(612) 555-0184"
    assert text[det.start : det.end] == det.text


def test_us_phone_dashed() -> None:
    text = "Contact 513-555-0142 now."
    block = _block(text)
    results = detect_regex([block])

    phones = [d for d in results if d.entity_type == EntityType.PHONE]
    assert len(phones) == 1
    det = phones[0]
    assert det.text == "513-555-0142"
    assert text[det.start : det.end] == det.text


def test_us_phone_dotted() -> None:
    text = "Fax: 513.555.0142."
    block = _block(text)
    results = detect_regex([block])

    phones = [d for d in results if d.entity_type == EntityType.PHONE]
    assert len(phones) == 1
    det = phones[0]
    assert det.text == "513.555.0142"
    assert text[det.start : det.end] == det.text


# ---------------------------------------------------------------------------
# US phone regex — negative cases
# ---------------------------------------------------------------------------


def test_us_phone_no_false_positive_on_short() -> None:
    block = _block("555-012")
    results = detect_regex([block])
    phones = [d for d in results if d.entity_type == EntityType.PHONE]
    assert phones == []


# ---------------------------------------------------------------------------
# confirm_candidates — parallel execution
# ---------------------------------------------------------------------------


def test_confirm_candidates_parallel() -> None:
    from incognito.pipeline.detect_ner import confirm_candidates

    blocks = [_block(f"Person {i}", page=0, block_index=i) for i in range(8)]
    candidates = [
        _det(f"Person {i}", EntityType.PERSON, 0, len(f"Person {i}"), page=0, block_index=i)
        for i in range(8)
    ]

    def generate_fn(prompt: str, system: str = "") -> str:
        time.sleep(0.1)
        return "1: 1"

    start = time.monotonic()
    results = confirm_candidates(blocks, candidates, generate_fn)
    elapsed = time.monotonic() - start

    assert len(results) == 8
    assert elapsed < 0.5, (
        f"confirm_candidates took {elapsed:.2f}s — expected parallel execution under 0.5s "
        f"(sequential minimum would be ~0.8s for 8 blocks)"
    )
