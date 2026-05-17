from __future__ import annotations

from unittest.mock import MagicMock, patch

from incognito.core import config
from incognito.models import BBox, EntityType, RawDetection, TextBlock
from incognito.pipeline.detector import detect

_BBOX = BBox(x=10.0, y=20.0, width=200.0, height=15.0)


def _block(text: str, page: int = 1, block_index: int = 0) -> TextBlock:
    return TextBlock(text=text, page=page, bbox=_BBOX, block_index=block_index)


def _raw_det(  # noqa: PLR0913
    text: str,
    entity_type: EntityType = EntityType.PERSON,
    start: int = 0,
    end: int | None = None,
    page: int = 1,
    block_index: int = 0,
) -> RawDetection:
    return RawDetection(
        text=text,
        entity_type=entity_type,
        start=start,
        end=end if end is not None else len(text),
        page=page,
        bbox=_BBOX,
        block_index=block_index,
    )


def _noop_generate(prompt: str, system: str = "") -> str:
    return ""


# ---------------------------------------------------------------------------
# Config constant
# ---------------------------------------------------------------------------


def test_gliner_model_is_pii_large_v1() -> None:
    assert config.GLINER_MODEL == "knowledgator/gliner-pii-large-v1.0"


# ---------------------------------------------------------------------------
# ADDRESS detections bypass confirm_candidates
# ---------------------------------------------------------------------------


def test_address_detection_bypasses_confirm_candidates() -> None:
    blocks = [_block("12 rue de la Paix, 75001 Paris")]
    address_det = _raw_det(
        "12 rue de la Paix, 75001 Paris",
        EntityType.ADDRESS,
        end=30,
    )
    dedup_result = [address_det]
    confirm_mock = MagicMock(return_value=[])

    with (
        patch("incognito.pipeline.detector.detect_regex", return_value=[]),
        patch("incognito.pipeline.detector.detect_gliner", return_value=[address_det]),
        patch("incognito.pipeline.detector.deduplicate", return_value=dedup_result),
        patch("incognito.pipeline.detector.confirm_candidates", confirm_mock),
    ):
        result = detect(blocks, _noop_generate)

    candidates_arg = confirm_mock.call_args[0][1]
    assert address_det not in candidates_arg
    assert address_det in result


def test_address_detection_does_not_call_generate_fn() -> None:
    blocks = [_block("12 rue de la Paix, 75001 Paris")]
    address_det = _raw_det(
        "12 rue de la Paix, 75001 Paris",
        EntityType.ADDRESS,
        end=30,
    )
    dedup_result = [address_det]
    generate_mock = MagicMock(return_value="")

    with (
        patch("incognito.pipeline.detector.detect_regex", return_value=[]),
        patch("incognito.pipeline.detector.detect_gliner", return_value=[address_det]),
        patch("incognito.pipeline.detector.deduplicate", return_value=dedup_result),
        patch(
            "incognito.pipeline.detector.confirm_candidates",
            return_value=[],
        ) as confirm_mock,
    ):
        detect(blocks, generate_mock)

    candidates_arg = confirm_mock.call_args[0][1]
    assert candidates_arg == []
    generate_mock.assert_not_called()


# ---------------------------------------------------------------------------
# PERSON detections still go through confirm_candidates
# ---------------------------------------------------------------------------


def test_person_detection_sent_to_confirm_candidates() -> None:
    blocks = [_block("Marie Curie")]
    person_det = _raw_det("Marie Curie", EntityType.PERSON, end=11)
    dedup_result = [person_det]
    confirmed = [person_det]
    confirm_mock = MagicMock(return_value=confirmed)

    with (
        patch("incognito.pipeline.detector.detect_regex", return_value=[]),
        patch("incognito.pipeline.detector.detect_gliner", return_value=[person_det]),
        patch("incognito.pipeline.detector.deduplicate", return_value=dedup_result),
        patch("incognito.pipeline.detector.confirm_candidates", confirm_mock),
    ):
        result = detect(blocks, _noop_generate)

    candidates_arg = confirm_mock.call_args[0][1]
    assert person_det in candidates_arg
    assert person_det in result


# ---------------------------------------------------------------------------
# Mixed: ADDRESS auto-confirmed, PERSON goes to confirm_candidates
# ---------------------------------------------------------------------------


def test_address_auto_confirmed_person_still_confirmed() -> None:
    blocks = [_block("Marie Curie, 12 rue de la Paix, 75001 Paris")]
    person_det = _raw_det("Marie Curie", EntityType.PERSON, end=11)
    address_det = _raw_det(
        "12 rue de la Paix, 75001 Paris",
        EntityType.ADDRESS,
        start=13,
        end=43,
    )
    dedup_result = [person_det, address_det]
    confirm_mock = MagicMock(return_value=[person_det])

    with (
        patch("incognito.pipeline.detector.detect_regex", return_value=[]),
        patch(
            "incognito.pipeline.detector.detect_gliner",
            return_value=[person_det, address_det],
        ),
        patch("incognito.pipeline.detector.deduplicate", return_value=dedup_result),
        patch("incognito.pipeline.detector.confirm_candidates", confirm_mock),
    ):
        result = detect(blocks, _noop_generate)

    candidates_arg = confirm_mock.call_args[0][1]
    assert person_det in candidates_arg
    assert address_det not in candidates_arg
    assert address_det in result
    assert person_det in result
