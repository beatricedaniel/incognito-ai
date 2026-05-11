from __future__ import annotations

import pytest

from incognito.core.exceptions import DetectionError
from incognito.models import BBox, Detection, EntityType, RawDetection, TextBlock
from incognito.pipeline.validator import validate

# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------


def _bbox(x: float = 0.0, y: float = 0.0, w: float = 100.0, h: float = 12.0) -> BBox:
    return BBox(x=x, y=y, width=w, height=h)


def _block(
    text: str,
    page: int = 0,
    block_index: int = 0,
    bbox: BBox | None = None,
) -> TextBlock:
    return TextBlock(text=text, page=page, bbox=bbox or _bbox(), block_index=block_index)


def _raw(  # noqa: PLR0913
    text: str,
    start: int,
    end: int,
    page: int = 0,
    block_index: int = 0,
    entity_type: EntityType = EntityType.PERSON,
    bbox: BBox | None = None,
) -> RawDetection:
    return RawDetection(
        text=text,
        entity_type=entity_type,
        start=start,
        end=end,
        page=page,
        bbox=bbox or _bbox(),
        block_index=block_index,
    )


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_happy_path_all_valid() -> None:
    block = _block("Jean Dupont habite Paris.", page=0, block_index=0)
    raws = [
        _raw("Jean Dupont", start=0, end=11, page=0, block_index=0, entity_type=EntityType.PERSON),
        _raw("Paris", start=19, end=24, page=0, block_index=0, entity_type=EntityType.ADDRESS),
    ]
    results = validate(raws, [block])
    assert len(results) == 2
    for d in results:
        assert isinstance(d, Detection)
        assert d.validated is True
        assert d.dismissed is False


# ---------------------------------------------------------------------------
# 10-minus-3 AC: 10 detections, 3 with wrong offsets → exactly 7 returned
# ---------------------------------------------------------------------------


def test_ten_minus_three_wrong_offsets() -> None:
    text = "0123456789"  # 10 chars; each single-char slice is trivially verifiable
    block = _block(text, page=0, block_index=0)

    valid_raws = [
        _raw(text[i : i + 1], start=i, end=i + 1, page=0, block_index=0) for i in range(7)
    ]
    # 3 detections whose text field doesn't match the slice (offset mismatch)
    bad_raws = [
        _raw("X", start=7, end=8, page=0, block_index=0),
        _raw("X", start=8, end=9, page=0, block_index=0),
        _raw("X", start=9, end=10, page=0, block_index=0),
    ]
    results = validate(valid_raws + bad_raws, [block])
    assert len(results) == 7


# ---------------------------------------------------------------------------
# Text mismatch: offset range valid but text field doesn't match slice
# ---------------------------------------------------------------------------


def test_text_mismatch_dropped() -> None:
    block = _block("Bonjour monde", page=0, block_index=0)
    raw = _raw("monde", start=0, end=5, page=0, block_index=0)  # slice is "Bonjo"
    assert validate([raw], [block]) == []


# ---------------------------------------------------------------------------
# Out-of-bounds offsets
# ---------------------------------------------------------------------------


def test_negative_start_dropped() -> None:
    block = _block("Hello", page=0, block_index=0)
    raw = _raw("Hello", start=-1, end=5, page=0, block_index=0)
    assert validate([raw], [block]) == []


def test_end_beyond_text_dropped() -> None:
    block = _block("Hello", page=0, block_index=0)
    raw = _raw("Hello!", start=0, end=6, page=0, block_index=0)
    assert validate([raw], [block]) == []


def test_start_ge_end_dropped() -> None:
    block = _block("Hello", page=0, block_index=0)
    raw = _raw("", start=3, end=3, page=0, block_index=0)
    assert validate([raw], [block]) == []


# ---------------------------------------------------------------------------
# Unknown block_index: detection references (page, block_index) not in blocks
# ---------------------------------------------------------------------------


def test_unknown_block_reference_dropped() -> None:
    block = _block("Valid block", page=0, block_index=0)
    raw = _raw("Valid block", start=0, end=11, page=0, block_index=99)
    assert validate([raw], [block]) == []


def test_unknown_page_reference_dropped() -> None:
    block = _block("Valid block", page=0, block_index=0)
    raw = _raw("Valid block", start=0, end=11, page=5, block_index=0)
    assert validate([raw], [block]) == []


# ---------------------------------------------------------------------------
# Multi-page: detections from different pages validated against correct block
# ---------------------------------------------------------------------------


def test_multi_page_validates_against_correct_block() -> None:
    block_p0 = _block("Alice Martin", page=0, block_index=0)
    block_p1 = _block("rue de la Paix", page=1, block_index=0)

    raws = [
        _raw("Alice Martin", start=0, end=12, page=0, block_index=0, entity_type=EntityType.PERSON),
        _raw(
            "rue de la Paix",
            start=0,
            end=14,
            page=1,
            block_index=0,
            entity_type=EntityType.ADDRESS,
        ),
    ]
    results = validate(raws, [block_p0, block_p1])
    assert len(results) == 2
    pages = {d.page for d in results}
    assert pages == {0, 1}


def test_multi_page_cross_contamination_dropped() -> None:
    """A detection whose text matches page-1 block but is keyed to page-0 must be dropped."""
    block_p0 = _block("Bonjour", page=0, block_index=0)
    block_p1 = _block("rue de la Paix", page=1, block_index=0)

    # Detection claims page=0 but text matches block on page=1
    raw = _raw("rue de la Paix", start=0, end=14, page=0, block_index=0)
    assert validate([raw], [block_p0, block_p1]) == []


# ---------------------------------------------------------------------------
# Duplicate block keys: two blocks with same (page, block_index) → DetectionError
# ---------------------------------------------------------------------------


def test_duplicate_block_key_raises() -> None:
    block_a = _block("First block", page=0, block_index=0)
    block_b = _block("Second block", page=0, block_index=0)
    raw = _raw("First block", start=0, end=11, page=0, block_index=0)

    with pytest.raises(DetectionError):
        validate([raw], [block_a, block_b])


# ---------------------------------------------------------------------------
# Empty inputs
# ---------------------------------------------------------------------------


def test_empty_detections_returns_empty() -> None:
    block = _block("Some text", page=0, block_index=0)
    assert validate([], [block]) == []


def test_empty_blocks_returns_empty() -> None:
    raw = _raw("text", start=0, end=4, page=0, block_index=0)
    assert validate([raw], []) == []


def test_both_empty_returns_empty() -> None:
    assert validate([], []) == []


# ---------------------------------------------------------------------------
# Unique IDs: two valid detections get distinct id values
# ---------------------------------------------------------------------------


def test_unique_ids() -> None:
    block = _block("Jean Dupont habite Paris.", page=0, block_index=0)
    raws = [
        _raw("Jean Dupont", start=0, end=11, page=0, block_index=0, entity_type=EntityType.PERSON),
        _raw("Paris", start=19, end=24, page=0, block_index=0, entity_type=EntityType.ADDRESS),
    ]
    results = validate(raws, [block])
    assert len(results) == 2
    ids = [d.id for d in results]
    assert ids[0] != ids[1]
