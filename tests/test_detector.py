from __future__ import annotations

import json
import textwrap
from collections.abc import Callable
from pathlib import Path

import pytest

from incognito.core.exceptions import DetectionError
from incognito.models import BBox, EntityType, TextBlock
from incognito.pipeline.detector import detect

GenerateFn = Callable[[str, str], str]

_BBOX = BBox(x=10.0, y=20.0, width=200.0, height=15.0)


def _block(
    text: str,
    page: int = 1,
    block_index: int = 0,
    bbox: BBox = _BBOX,
) -> TextBlock:
    return TextBlock(text=text, page=page, bbox=bbox, block_index=block_index)


def _generate_returning(payload: str) -> GenerateFn:
    def generate_fn(prompt: str, system: str) -> str:
        return payload

    return generate_fn


def test_happy_path_single_block() -> None:
    block = _block("Jean Dupont habite à Paris.")
    response = json.dumps([{"text": "Jean Dupont", "entity_type": "person", "start": 0, "end": 11}])
    result = detect([block], _generate_returning(response))

    assert len(result) == 1
    det = result[0]
    assert det.text == "Jean Dupont"
    assert det.entity_type == EntityType.PERSON
    assert det.start == 0
    assert det.end == 11
    assert det.page == block.page
    assert det.bbox == block.bbox
    assert det.block_index == block.block_index


def test_multiple_blocks_inherit_correct_metadata() -> None:
    bbox_a = BBox(x=0.0, y=0.0, width=100.0, height=10.0)
    bbox_b = BBox(x=5.0, y=50.0, width=150.0, height=12.0)
    block_a = _block("Marie Martin.", page=1, block_index=0, bbox=bbox_a)
    block_b = _block("0612345678", page=2, block_index=3, bbox=bbox_b)

    responses = [
        json.dumps([{"text": "Marie Martin", "entity_type": "person", "start": 0, "end": 12}]),
        json.dumps([{"text": "0612345678", "entity_type": "phone", "start": 0, "end": 10}]),
    ]
    call_count = 0

    def generate_fn(prompt: str, system: str) -> str:
        nonlocal call_count
        r = responses[call_count]
        call_count += 1
        return r

    result = detect([block_a, block_b], generate_fn)

    assert len(result) == 2
    assert result[0].page == 1
    assert result[0].bbox == bbox_a
    assert result[0].block_index == 0
    assert result[1].page == 2
    assert result[1].bbox == bbox_b
    assert result[1].block_index == 3


def test_whitespace_only_block_skipped_no_generate_call() -> None:
    called = False

    def generate_fn(prompt: str, system: str) -> str:
        nonlocal called
        called = True
        return "[]"

    result = detect([_block("   \n\t  ")], generate_fn)

    assert result == []
    assert not called


def test_no_pii_found_returns_empty_list() -> None:
    result = detect([_block("Texte sans PII.")], _generate_returning("[]"))
    assert result == []


def test_malformed_json_raises_detection_error() -> None:
    with pytest.raises(DetectionError):
        detect([_block("Jean Dupont")], _generate_returning("not json at all"))


def test_non_list_json_raises_detection_error() -> None:
    payload = json.dumps({"text": "foo", "entity_type": "person", "start": 0, "end": 3})
    with pytest.raises(DetectionError):
        detect([_block("foo bar")], _generate_returning(payload))


def test_missing_required_field_raises_detection_error() -> None:
    payload = json.dumps([{"text": "Jean", "entity_type": "person"}])
    with pytest.raises(DetectionError):
        detect([_block("Jean Dupont")], _generate_returning(payload))


def test_no_httpx_import_in_detector() -> None:
    detector_path = Path(__file__).parent.parent / "src" / "incognito" / "pipeline" / "detector.py"
    source = detector_path.read_text()
    assert "httpx" not in source


def test_bbox_inherited_exactly() -> None:
    exact_bbox = BBox(x=3.14, y=2.72, width=99.9, height=14.1)
    block = _block("jean@example.com", page=3, block_index=7, bbox=exact_bbox)
    response = json.dumps(
        [
            {
                "text": "jean@example.com",
                "entity_type": "email",
                "start": 0,
                "end": 16,
            }
        ]
    )
    result = detect([block], _generate_returning(response))

    assert len(result) == 1
    assert result[0].bbox == exact_bbox


def test_code_fenced_json_parsed_correctly() -> None:
    block = _block("Jean Dupont")
    payload = textwrap.dedent(
        """\
        ```json
        [{"text": "Jean Dupont", "entity_type": "person", "start": 0, "end": 11}]
        ```"""
    )
    result = detect([block], _generate_returning(payload))

    assert len(result) == 1
    assert result[0].text == "Jean Dupont"


def test_generate_fn_exception_wrapped_as_detection_error() -> None:
    def exploding_generate(prompt: str, system: str) -> str:
        raise RuntimeError("model crashed")

    with pytest.raises(DetectionError):
        detect([_block("Jean Dupont")], exploding_generate)
