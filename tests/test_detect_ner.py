from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

from incognito.models import BBox, EntityType, RawDetection, TextBlock

if TYPE_CHECKING:
    pass

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


def _gliner_available() -> bool:
    try:
        from incognito.gliner.loader import load_model

        load_model()
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# detect_gliner — basic shape
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _gliner_available(), reason="GLiNER model not loaded")
def test_detect_gliner_returns_list() -> None:
    from incognito.pipeline.detect_ner import detect_gliner

    result = detect_gliner([_block("Bonjour")])
    assert isinstance(result, list)


@pytest.mark.skipif(not _gliner_available(), reason="GLiNER model not loaded")
def test_detect_gliner_empty_blocks_returns_empty() -> None:
    from incognito.pipeline.detect_ner import detect_gliner

    assert detect_gliner([]) == []


@pytest.mark.skipif(not _gliner_available(), reason="GLiNER model not loaded")
def test_detect_gliner_results_are_raw_detections() -> None:
    from incognito.pipeline.detect_ner import detect_gliner

    results = detect_gliner([_block("Jean Dupont habite à Paris.")])
    for det in results:
        assert isinstance(det, RawDetection)


@pytest.mark.skipif(not _gliner_available(), reason="GLiNER model not loaded")
def test_detect_gliner_offsets_match_block_text() -> None:
    from incognito.pipeline.detect_ner import detect_gliner

    block = _block("Jean Dupont habite à Paris.")
    results = detect_gliner([block])
    for det in results:
        assert block.text[det.start : det.end] == det.text


@pytest.mark.skipif(not _gliner_available(), reason="GLiNER model not loaded")
def test_detect_gliner_entity_type_is_person_or_address() -> None:
    from incognito.pipeline.detect_ner import detect_gliner

    results = detect_gliner([_block("Jean Dupont, 12 rue de la Paix, Paris.")])
    for det in results:
        assert det.entity_type in (EntityType.PERSON, EntityType.ADDRESS)


@pytest.mark.skipif(not _gliner_available(), reason="GLiNER model not loaded")
def test_detect_gliner_page_and_block_index_propagated() -> None:
    from incognito.pipeline.detect_ner import detect_gliner

    block = _block("Jean Dupont", page=3, block_index=7)
    results = detect_gliner([block])
    for det in results:
        assert det.page == 3
        assert det.block_index == 7


# ---------------------------------------------------------------------------
# detect_gliner — threshold filtering (mocked GLiNER)
# ---------------------------------------------------------------------------


def _mock_gliner_model(entities: list[dict]) -> MagicMock:
    model = MagicMock()
    model.predict_entities.return_value = entities
    return model


def test_person_below_threshold_excluded() -> None:
    from incognito.pipeline.detect_ner import detect_gliner

    block = _block("Jean Dupont")
    fake_entities = [
        {"text": "Jean Dupont", "label": "person", "start": 0, "end": 11, "score": 0.49}
    ]

    with patch(
        "incognito.pipeline.detect_ner.load_model", return_value=_mock_gliner_model(fake_entities)
    ):
        results = detect_gliner([block])

    persons = [d for d in results if d.entity_type == EntityType.PERSON]
    assert persons == []


def test_person_at_threshold_included() -> None:
    from incognito.pipeline.detect_ner import detect_gliner

    block = _block("Jean Dupont")
    fake_entities = [
        {"text": "Jean Dupont", "label": "person", "start": 0, "end": 11, "score": 0.5}
    ]

    with patch(
        "incognito.pipeline.detect_ner.load_model", return_value=_mock_gliner_model(fake_entities)
    ):
        results = detect_gliner([block])

    persons = [d for d in results if d.entity_type == EntityType.PERSON]
    assert len(persons) == 1


def test_address_below_threshold_excluded() -> None:
    from incognito.pipeline.detect_ner import detect_gliner

    block = _block("12 rue de la Paix")
    fake_entities = [
        {"text": "12 rue de la Paix", "label": "address", "start": 0, "end": 18, "score": 0.29}
    ]

    with patch(
        "incognito.pipeline.detect_ner.load_model", return_value=_mock_gliner_model(fake_entities)
    ):
        results = detect_gliner([block])

    addresses = [d for d in results if d.entity_type == EntityType.ADDRESS]
    assert addresses == []


def test_address_at_threshold_included() -> None:
    from incognito.pipeline.detect_ner import detect_gliner

    block = _block("12 rue de la Paix")
    fake_entities = [
        {"text": "12 rue de la Paix", "label": "address", "start": 0, "end": 18, "score": 0.3}
    ]

    with patch(
        "incognito.pipeline.detect_ner.load_model", return_value=_mock_gliner_model(fake_entities)
    ):
        results = detect_gliner([block])

    addresses = [d for d in results if d.entity_type == EntityType.ADDRESS]
    assert len(addresses) == 1


def test_person_above_threshold_included() -> None:
    from incognito.pipeline.detect_ner import detect_gliner

    block = _block("Marie Curie")
    fake_entities = [
        {"text": "Marie Curie", "label": "person", "start": 0, "end": 11, "score": 0.95}
    ]

    with patch(
        "incognito.pipeline.detect_ner.load_model", return_value=_mock_gliner_model(fake_entities)
    ):
        results = detect_gliner([block])

    assert len(results) == 1
    assert results[0].entity_type == EntityType.PERSON


def test_gliner_offsets_from_predict_entities_are_preserved() -> None:
    from incognito.pipeline.detect_ner import detect_gliner

    block = _block("Nom: Jean Dupont.")
    fake_entities = [
        {"text": "Jean Dupont", "label": "person", "start": 5, "end": 16, "score": 0.9}
    ]

    with patch(
        "incognito.pipeline.detect_ner.load_model", return_value=_mock_gliner_model(fake_entities)
    ):
        results = detect_gliner([block])

    assert len(results) == 1
    assert results[0].start == 5
    assert results[0].end == 16
    assert results[0].text == "Jean Dupont"


# ---------------------------------------------------------------------------
# detect_gliner — intra-GLiNER deduplication (same-type overlap, higher score wins)
# ---------------------------------------------------------------------------


def test_intra_gliner_dedup_higher_score_wins_on_overlap() -> None:
    from incognito.pipeline.detect_ner import detect_gliner

    block = _block("Jean Dupont Martin")
    # Two overlapping person spans — first has higher score
    fake_entities = [
        {"text": "Jean Dupont Martin", "label": "person", "start": 0, "end": 18, "score": 0.9},
        {"text": "Dupont Martin", "label": "person", "start": 5, "end": 18, "score": 0.7},
    ]

    with patch(
        "incognito.pipeline.detect_ner.load_model", return_value=_mock_gliner_model(fake_entities)
    ):
        results = detect_gliner([block])

    persons = [d for d in results if d.entity_type == EntityType.PERSON]
    assert len(persons) == 1
    assert persons[0].text == "Jean Dupont Martin"


def test_intra_gliner_dedup_lower_score_span_removed() -> None:
    from incognito.pipeline.detect_ner import detect_gliner

    block = _block("Jean Dupont")
    fake_entities = [
        {"text": "Jean", "label": "person", "start": 0, "end": 4, "score": 0.6},
        {"text": "Jean Dupont", "label": "person", "start": 0, "end": 11, "score": 0.85},
    ]

    with patch(
        "incognito.pipeline.detect_ner.load_model", return_value=_mock_gliner_model(fake_entities)
    ):
        results = detect_gliner([block])

    persons = [d for d in results if d.entity_type == EntityType.PERSON]
    assert len(persons) == 1
    assert persons[0].text == "Jean Dupont"


# ---------------------------------------------------------------------------
# confirm_candidates — normal confirmation
# ---------------------------------------------------------------------------


def test_confirm_candidates_confirms_and_rejects_per_response() -> None:
    from incognito.pipeline.detect_ner import confirm_candidates

    block = _block("Jean Dupont, 12 rue de la Paix, Paris.")
    candidates = [
        _det("Jean Dupont", EntityType.PERSON, 0, 11),
        _det("12 rue de la Paix", EntityType.ADDRESS, 13, 31),
        _det("Paris", EntityType.ADDRESS, 33, 38),
    ]

    def generate_fn(prompt: str, system: str = "") -> str:
        return "1: 1\n2: 0\n3: 1"

    results = confirm_candidates([block], candidates, generate_fn)
    texts = [d.text for d in results]
    assert "Jean Dupont" in texts
    assert "Paris" in texts
    assert "12 rue de la Paix" not in texts


def test_confirm_candidates_rejected_candidate_excluded() -> None:
    from incognito.pipeline.detect_ner import confirm_candidates

    block = _block("Jean Dupont")
    candidates = [_det("Jean Dupont", EntityType.PERSON, 0, 11)]

    def generate_fn(prompt: str, system: str = "") -> str:
        return "1: 0"

    results = confirm_candidates([block], candidates, generate_fn)
    assert results == []


def test_confirm_candidates_all_confirmed_when_all_ones() -> None:
    from incognito.pipeline.detect_ner import confirm_candidates

    block = _block("Jean Dupont habite à Paris.")
    candidates = [
        _det("Jean Dupont", EntityType.PERSON, 0, 11),
        _det("Paris", EntityType.ADDRESS, 21, 26),
    ]

    def generate_fn(prompt: str, system: str = "") -> str:
        return "1: 1\n2: 1"

    results = confirm_candidates([block], candidates, generate_fn)
    assert len(results) == 2


# ---------------------------------------------------------------------------
# confirm_candidates — fail-safe behaviours
# ---------------------------------------------------------------------------


def test_confirm_candidates_missing_id_confirms_candidate() -> None:
    from incognito.pipeline.detect_ner import confirm_candidates

    block = _block("Jean Dupont et Marie Curie.")
    candidates = [
        _det("Jean Dupont", EntityType.PERSON, 0, 11),
        _det("Marie Curie", EntityType.PERSON, 15, 26),
    ]

    # Response only has ID 1, omits ID 2 — ID 2 must be confirmed (fail-safe)
    def generate_fn(prompt: str, system: str = "") -> str:
        return "1: 0"

    results = confirm_candidates([block], candidates, generate_fn)
    texts = [d.text for d in results]
    assert "Marie Curie" in texts


def test_confirm_candidates_generate_fn_raises_confirms_all() -> None:
    from incognito.pipeline.detect_ner import confirm_candidates

    block = _block("Jean Dupont habite à Paris.")
    candidates = [
        _det("Jean Dupont", EntityType.PERSON, 0, 11),
        _det("Paris", EntityType.ADDRESS, 21, 26),
    ]

    def generate_fn(prompt: str, system: str = "") -> str:
        raise RuntimeError("Ollama unavailable")

    results = confirm_candidates([block], candidates, generate_fn)
    assert len(results) == 2


def test_confirm_candidates_garbage_response_confirms_all() -> None:
    from incognito.pipeline.detect_ner import confirm_candidates

    block = _block("Jean Dupont habite à Paris.")
    candidates = [
        _det("Jean Dupont", EntityType.PERSON, 0, 11),
        _det("Paris", EntityType.ADDRESS, 21, 26),
    ]

    def generate_fn(prompt: str, system: str = "") -> str:
        return "je ne comprends pas cette question du tout"

    results = confirm_candidates([block], candidates, generate_fn)
    assert len(results) == 2


def test_confirm_candidates_empty_response_confirms_all() -> None:
    from incognito.pipeline.detect_ner import confirm_candidates

    block = _block("Jean Dupont")
    candidates = [_det("Jean Dupont", EntityType.PERSON, 0, 11)]

    def generate_fn(prompt: str, system: str = "") -> str:
        return ""

    results = confirm_candidates([block], candidates, generate_fn)
    assert len(results) == 1


def test_confirm_candidates_empty_candidates_returns_empty() -> None:
    from incognito.pipeline.detect_ner import confirm_candidates

    block = _block("Bonjour")

    def generate_fn(prompt: str, system: str = "") -> str:
        return ""

    results = confirm_candidates([block], [], generate_fn)
    assert results == []


def test_confirm_candidates_generate_fn_called_per_block() -> None:
    from incognito.pipeline.detect_ner import confirm_candidates

    block_a = _block("Jean Dupont", page=0, block_index=0)
    block_b = _block("Marie Curie", page=1, block_index=1)
    candidates = [
        _det("Jean Dupont", EntityType.PERSON, 0, 11, page=0, block_index=0),
        _det("Marie Curie", EntityType.PERSON, 0, 11, page=1, block_index=1),
    ]

    call_count = 0

    def generate_fn(prompt: str, system: str = "") -> str:
        nonlocal call_count
        call_count += 1
        return "1: 1"

    confirm_candidates([block_a, block_b], candidates, generate_fn)
    assert call_count == 2


# ---------------------------------------------------------------------------
# deduplicate — regex wins over GLiNER on overlap
# ---------------------------------------------------------------------------


def test_deduplicate_overlapping_gliner_det_removed() -> None:
    from incognito.pipeline.detect_ner import deduplicate

    regex_det = _det("jean@example.fr", EntityType.EMAIL, 10, 25)
    gliner_det = _det("jean@example.fr", EntityType.PERSON, 10, 25)

    results = deduplicate([regex_det], [gliner_det])
    assert gliner_det not in results
    assert regex_det in results


def test_deduplicate_non_overlapping_gliner_det_kept() -> None:
    from incognito.pipeline.detect_ner import deduplicate

    regex_det = _det("jean@example.fr", EntityType.EMAIL, 0, 15)
    gliner_det = _det("Jean Dupont", EntityType.PERSON, 20, 31)

    results = deduplicate([regex_det], [gliner_det])
    assert gliner_det in results


def test_deduplicate_all_regex_dets_present_in_output() -> None:
    from incognito.pipeline.detect_ner import deduplicate

    regex_dets = [
        _det("jean@example.fr", EntityType.EMAIL, 0, 15),
        _det("06 12 34 56 78", EntityType.PHONE, 20, 34),
    ]
    gliner_dets: list[RawDetection] = []

    results = deduplicate(regex_dets, gliner_dets)
    for det in regex_dets:
        assert det in results


def test_deduplicate_empty_inputs_returns_empty() -> None:
    from incognito.pipeline.detect_ner import deduplicate

    assert deduplicate([], []) == []


def test_deduplicate_partial_overlap_gliner_removed() -> None:
    from incognito.pipeline.detect_ner import deduplicate

    # regex span 10-25, gliner span 20-35 — they overlap
    regex_det = _det("jean@example.fr", EntityType.EMAIL, 10, 25)
    gliner_det = _det("example.fr dupont", EntityType.PERSON, 20, 37)

    results = deduplicate([regex_det], [gliner_det])
    gliner_results = [d for d in results if d.entity_type == EntityType.PERSON]
    assert gliner_results == []


def test_deduplicate_adjacent_spans_not_considered_overlapping() -> None:
    from incognito.pipeline.detect_ner import deduplicate

    # regex ends at 15, gliner starts at 15 — adjacent, not overlapping
    regex_det = _det("jean@example.fr", EntityType.EMAIL, 0, 15)
    gliner_det = _det("Jean Dupont", EntityType.PERSON, 15, 26)

    results = deduplicate([regex_det], [gliner_det])
    gliner_results = [d for d in results if d.entity_type == EntityType.PERSON]
    assert len(gliner_results) == 1


def test_deduplicate_page_isolated_overlap_check() -> None:
    from incognito.pipeline.detect_ner import deduplicate

    # Same offsets but different pages — should not be considered overlapping
    regex_det = _det("jean@example.fr", EntityType.EMAIL, 0, 15, page=0)
    gliner_det = _det("Jean Dupont", EntityType.PERSON, 0, 15, page=1)

    results = deduplicate([regex_det], [gliner_det])
    gliner_results = [d for d in results if d.entity_type == EntityType.PERSON]
    assert len(gliner_results) == 1


# ---------------------------------------------------------------------------
# module purity: no httpx import
# ---------------------------------------------------------------------------


def test_no_httpx_import_in_module() -> None:
    source = (
        Path(__file__).parent.parent / "src" / "incognito" / "pipeline" / "detect_ner.py"
    ).read_text()
    assert "httpx" not in source


def test_no_requests_import_in_module() -> None:
    source = (
        Path(__file__).parent.parent / "src" / "incognito" / "pipeline" / "detect_ner.py"
    ).read_text()
    assert "requests" not in source
