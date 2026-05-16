from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from incognito.core.exceptions import DetectionError
from incognito.models import BBox, EntityType, RawDetection, TextBlock
from incognito.pipeline.detector import GenerateFn, detect

_BBOX = BBox(x=10.0, y=20.0, width=200.0, height=15.0)
_PAGE_BBOX = BBox(x=0.0, y=0.0, width=595.0, height=842.0)


def _block(
    text: str,
    page: int = 1,
    block_index: int = 0,
    bbox: BBox = _BBOX,
) -> TextBlock:
    return TextBlock(text=text, page=page, bbox=bbox, block_index=block_index)


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
# Orchestration order and delegation
# ---------------------------------------------------------------------------


def test_detect_calls_all_four_sub_functions_in_order() -> None:
    blocks = [_block("Jean Dupont")]
    regex_result: list[RawDetection] = []
    gliner_result: list[RawDetection] = [_raw_det("Jean Dupont")]
    dedup_result = regex_result + gliner_result
    confirmed: list[RawDetection] = [_raw_det("Jean Dupont")]

    call_order: list[str] = []

    def tracking_regex(b: list[TextBlock]) -> list[RawDetection]:
        call_order.append("regex")
        return regex_result

    def tracking_gliner(b: list[TextBlock]) -> list[RawDetection]:
        call_order.append("gliner")
        return gliner_result

    def tracking_dedup(r: list[RawDetection], g: list[RawDetection]) -> list[RawDetection]:
        call_order.append("dedup")
        return dedup_result

    def tracking_confirm(
        b: list[TextBlock], c: list[RawDetection], g: GenerateFn
    ) -> list[RawDetection]:
        call_order.append("confirm")
        return confirmed

    with (
        patch("incognito.pipeline.detector.detect_regex", tracking_regex),
        patch("incognito.pipeline.detector.detect_gliner", tracking_gliner),
        patch("incognito.pipeline.detector.deduplicate", tracking_dedup),
        patch("incognito.pipeline.detector.confirm_candidates", tracking_confirm),
    ):
        detect(blocks, _noop_generate)

    assert call_order == ["regex", "gliner", "dedup", "confirm"]


# ---------------------------------------------------------------------------
# Regex detections bypass Gemma confirmation
# ---------------------------------------------------------------------------


def test_regex_detections_not_sent_to_confirm() -> None:
    blocks = [_block("jean@example.com")]
    regex_det = _raw_det("jean@example.com", EntityType.EMAIL, end=16)
    dedup_result = [regex_det]  # only regex, no GLiNER survivors

    confirm_mock = MagicMock(return_value=[])

    with (
        patch("incognito.pipeline.detector.detect_regex", return_value=[regex_det]),
        patch("incognito.pipeline.detector.detect_gliner", return_value=[]),
        patch("incognito.pipeline.detector.deduplicate", return_value=dedup_result),
        patch("incognito.pipeline.detector.confirm_candidates", confirm_mock),
    ):
        result = detect(blocks, _noop_generate)

    # confirm_candidates must receive an empty candidate list
    candidates_arg = confirm_mock.call_args[0][1]
    assert candidates_arg == []
    assert regex_det in result


# ---------------------------------------------------------------------------
# GLiNER detections go through confirmation
# ---------------------------------------------------------------------------


def test_gliner_detections_sent_to_confirm() -> None:
    blocks = [_block("Marie Martin habite à Lyon.")]
    gliner_det = _raw_det("Marie Martin", EntityType.PERSON, end=12)
    dedup_result = [gliner_det]  # no regex, one GLiNER survivor
    confirmed = [gliner_det]

    confirm_mock = MagicMock(return_value=confirmed)

    with (
        patch("incognito.pipeline.detector.detect_regex", return_value=[]),
        patch("incognito.pipeline.detector.detect_gliner", return_value=[gliner_det]),
        patch("incognito.pipeline.detector.deduplicate", return_value=dedup_result),
        patch("incognito.pipeline.detector.confirm_candidates", confirm_mock),
    ):
        result = detect(blocks, _noop_generate)

    candidates_arg = confirm_mock.call_args[0][1]
    assert gliner_det in candidates_arg
    assert gliner_det in result


# ---------------------------------------------------------------------------
# Dedup removes GLiNER candidates overlapping with regex
# ---------------------------------------------------------------------------


def test_dedup_called_with_regex_and_gliner_results() -> None:
    blocks = [_block("0612345678")]
    regex_det = _raw_det("0612345678", EntityType.PHONE, end=10)
    gliner_det = _raw_det("0612345678", EntityType.PHONE, end=10)

    dedup_mock = MagicMock(return_value=[regex_det])

    with (
        patch("incognito.pipeline.detector.detect_regex", return_value=[regex_det]),
        patch("incognito.pipeline.detector.detect_gliner", return_value=[gliner_det]),
        patch("incognito.pipeline.detector.deduplicate", dedup_mock),
        patch("incognito.pipeline.detector.confirm_candidates", return_value=[]),
    ):
        detect(blocks, _noop_generate)

    dedup_mock.assert_called_once_with([regex_det], [gliner_det])


# ---------------------------------------------------------------------------
# Empty blocks → empty list, no crash
# ---------------------------------------------------------------------------


def test_empty_blocks_returns_empty_list() -> None:
    with (
        patch("incognito.pipeline.detector.detect_regex", return_value=[]),
        patch("incognito.pipeline.detector.detect_gliner", return_value=[]),
        patch("incognito.pipeline.detector.deduplicate", return_value=[]),
        patch("incognito.pipeline.detector.confirm_candidates", return_value=[]),
    ):
        result = detect([], _noop_generate)

    assert result == []


# ---------------------------------------------------------------------------
# GLiNER failure → raises DetectionError (not swallowed)
# ---------------------------------------------------------------------------


def test_gliner_failure_raises_detection_error() -> None:
    blocks = [_block("Jean Dupont")]

    def exploding_gliner(b: list[TextBlock]) -> list[RawDetection]:
        raise DetectionError("GLiNER model crashed")

    with (
        patch("incognito.pipeline.detector.detect_regex", return_value=[]),
        patch("incognito.pipeline.detector.detect_gliner", exploding_gliner),
        pytest.raises(DetectionError),
    ):
        detect(blocks, _noop_generate)


# ---------------------------------------------------------------------------
# generate_fn not called when no GLiNER candidates survive dedup
# ---------------------------------------------------------------------------


def test_generate_fn_not_called_when_no_gliner_candidates() -> None:
    blocks = [_block("jean@example.com")]
    regex_det = _raw_det("jean@example.com", EntityType.EMAIL, end=16)
    generate_mock = MagicMock(return_value="")

    with (
        patch("incognito.pipeline.detector.detect_regex", return_value=[regex_det]),
        patch("incognito.pipeline.detector.detect_gliner", return_value=[]),
        patch("incognito.pipeline.detector.deduplicate", return_value=[regex_det]),
        patch("incognito.pipeline.detector.confirm_candidates", return_value=[]) as confirm_mock,
    ):
        detect(blocks, generate_mock)

    # confirm_candidates is called with empty candidates, so generate_fn must not be
    # invoked. Verify by checking the candidates arg is empty.
    candidates_arg = confirm_mock.call_args[0][1]
    assert candidates_arg == []
    generate_mock.assert_not_called()


# ---------------------------------------------------------------------------
# Return value is regex_dets + confirmed (not deduped list directly)
# ---------------------------------------------------------------------------


def test_return_value_is_regex_plus_confirmed() -> None:
    blocks = [_block("Marie Martin, jean@example.com")]
    regex_det = _raw_det("jean@example.com", EntityType.EMAIL, start=14, end=30)
    gliner_det = _raw_det("Marie Martin", EntityType.PERSON, start=0, end=12)
    confirmed_det = _raw_det("Marie Martin", EntityType.PERSON, start=0, end=12)

    with (
        patch("incognito.pipeline.detector.detect_regex", return_value=[regex_det]),
        patch("incognito.pipeline.detector.detect_gliner", return_value=[gliner_det]),
        patch(
            "incognito.pipeline.detector.deduplicate",
            return_value=[regex_det, gliner_det],
        ),
        patch(
            "incognito.pipeline.detector.confirm_candidates",
            return_value=[confirmed_det],
        ),
    ):
        result = detect(blocks, _noop_generate)

    assert regex_det in result
    assert confirmed_det in result
    assert len(result) == 2


# ---------------------------------------------------------------------------
# Purity: no httpx import in detector.py
# ---------------------------------------------------------------------------


def test_no_httpx_import_in_detector() -> None:
    source = (
        Path(__file__).parent.parent / "src" / "incognito" / "pipeline" / "detector.py"
    ).read_text()
    assert "httpx" not in source


# ---------------------------------------------------------------------------
# Old internals deleted
# ---------------------------------------------------------------------------


def test_old_internals_not_present_in_detector_module() -> None:
    import incognito.pipeline.detector as detector_module

    deleted = [
        "_SYSTEM_PROMPT",
        "_FENCE_RE",
        "_parse_response",
        "_strip_code_fences",
        "_detect_block",
    ]
    for name in deleted:
        assert not hasattr(detector_module, name), f"{name!r} still exists in detector.py"


# ---------------------------------------------------------------------------
# GenerateFn re-exported from detector
# ---------------------------------------------------------------------------


def test_generate_fn_importable_from_detector() -> None:
    from incognito.pipeline.detector import GenerateFn as DetectorGenerateFn

    assert DetectorGenerateFn is not None
