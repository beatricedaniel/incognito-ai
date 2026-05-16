from __future__ import annotations

import pytest

from incognito.models import BBox, EntityType, TextBlock
from incognito.pipeline.detect_regex import detect_regex

_BBOX = BBox(x=10.0, y=20.0, width=200.0, height=15.0)


def _block(
    text: str,
    page: int = 1,
    block_index: int = 0,
    bbox: BBox = _BBOX,
) -> TextBlock:
    return TextBlock(text=text, page=page, bbox=bbox, block_index=block_index)


# ---------------------------------------------------------------------------
# return type and basic shape
# ---------------------------------------------------------------------------


def test_returns_list() -> None:
    result = detect_regex([_block("hello")])
    assert isinstance(result, list)


def test_empty_block_list_returns_empty() -> None:
    assert detect_regex([]) == []


def test_no_pii_returns_empty() -> None:
    result = detect_regex([_block("Bonjour, voici un texte sans PII.")])
    assert result == []


def test_whitespace_only_block_returns_empty() -> None:
    assert detect_regex([_block("   \n\t  ")]) == []


def test_empty_string_block_returns_empty() -> None:
    assert detect_regex([_block("")]) == []


# ---------------------------------------------------------------------------
# email detection
# ---------------------------------------------------------------------------


def test_email_basic() -> None:
    block = _block("Contactez user@example.fr pour plus d'infos.")
    results = detect_regex([block])

    assert len(results) == 1
    det = results[0]
    assert det.entity_type == EntityType.EMAIL
    assert det.text == "user@example.fr"
    assert block.text[det.start : det.end] == det.text


def test_email_offsets_exact() -> None:
    text = "Envoyez à jean.dupont@hopital.org s'il vous plaît."
    block = _block(text)
    results = detect_regex([block])

    assert len(results) == 1
    det = results[0]
    assert det.start == text.index("jean.dupont@hopital.org")
    assert det.end == det.start + len("jean.dupont@hopital.org")
    assert text[det.start : det.end] == det.text


def test_email_subdomain() -> None:
    block = _block("user@sub.domain.co")
    results = detect_regex([block])

    assert len(results) == 1
    assert results[0].text == "user@sub.domain.co"


def test_email_metadata_inherited() -> None:
    bbox = BBox(x=1.0, y=2.0, width=50.0, height=8.0)
    block = _block("a@b.com", page=3, block_index=7, bbox=bbox)
    results = detect_regex([block])

    assert len(results) == 1
    det = results[0]
    assert det.page == 3
    assert det.block_index == 7
    assert det.bbox == bbox


# ---------------------------------------------------------------------------
# phone detection — canonical formats
# ---------------------------------------------------------------------------


def test_phone_spaced_mobile() -> None:
    block = _block("Appelez le 06 12 34 56 78 demain.")
    results = detect_regex([block])

    assert len(results) == 1
    det = results[0]
    assert det.entity_type == EntityType.PHONE
    assert det.text == "06 12 34 56 78"
    assert block.text[det.start : det.end] == det.text


def test_phone_international_prefix() -> None:
    block = _block("+33 6 12 34 56 78")
    results = detect_regex([block])

    assert len(results) == 1
    det = results[0]
    assert det.entity_type == EntityType.PHONE
    assert block.text[det.start : det.end] == det.text


def test_phone_dots() -> None:
    block = _block("01.23.45.67.89")
    results = detect_regex([block])

    assert len(results) == 1
    assert block.text[results[0].start : results[0].end] == results[0].text


def test_phone_compact() -> None:
    block = _block("0612345678")
    results = detect_regex([block])

    assert len(results) == 1
    assert results[0].text == "0612345678"
    assert results[0].entity_type == EntityType.PHONE


def test_phone_hyphens() -> None:
    block = _block("03-45-67-89-01")
    results = detect_regex([block])

    assert len(results) == 1
    assert block.text[results[0].start : results[0].end] == results[0].text


def test_phone_metadata_inherited() -> None:
    bbox = BBox(x=5.0, y=10.0, width=120.0, height=12.0)
    block = _block("0612345678", page=2, block_index=4, bbox=bbox)
    results = detect_regex([block])

    assert len(results) == 1
    det = results[0]
    assert det.page == 2
    assert det.block_index == 4
    assert det.bbox == bbox


# ---------------------------------------------------------------------------
# phone detection — unicode separators
# ---------------------------------------------------------------------------


def test_phone_nbsp_separator() -> None:
    text = "06\u00a012\u00a034\u00a056\u00a078"
    block = _block(text)
    results = detect_regex([block])

    assert len(results) == 1
    assert block.text[results[0].start : results[0].end] == results[0].text


def test_phone_soft_hyphen_separator() -> None:
    text = "06\u00ad12\u00ad34\u00ad56\u00ad78"
    block = _block(text)
    results = detect_regex([block])

    assert len(results) == 1
    assert block.text[results[0].start : results[0].end] == results[0].text


def test_phone_zero_width_space_separator() -> None:
    text = "06\u200b12\u200b34\u200b56\u200b78"
    block = _block(text)
    results = detect_regex([block])

    assert len(results) == 1
    assert block.text[results[0].start : results[0].end] == results[0].text


# ---------------------------------------------------------------------------
# phone detection — negative cases
# ---------------------------------------------------------------------------


def test_too_short_number_not_matched() -> None:
    block = _block("12345678")
    results = detect_regex([block])
    phones = [d for d in results if d.entity_type == EntityType.PHONE]
    assert phones == []


def test_eight_digit_number_not_matched() -> None:
    block = _block("0600 1234")
    results = detect_regex([block])
    phones = [d for d in results if d.entity_type == EntityType.PHONE]
    assert phones == []


# ---------------------------------------------------------------------------
# multiple matches in one block
# ---------------------------------------------------------------------------


def test_multiple_phones_in_one_block() -> None:
    text = "Bureau: 01 23 45 67 89, Mobile: 06 98 76 54 32."
    block = _block(text)
    results = detect_regex([block])

    phones = [d for d in results if d.entity_type == EntityType.PHONE]
    assert len(phones) == 2
    for det in phones:
        assert text[det.start : det.end] == det.text


def test_multiple_emails_in_one_block() -> None:
    text = "alice@example.com et bob@test.fr sont en copie."
    block = _block(text)
    results = detect_regex([block])

    emails = [d for d in results if d.entity_type == EntityType.EMAIL]
    assert len(emails) == 2
    for det in emails:
        assert text[det.start : det.end] == det.text


def test_phone_and_email_in_same_block() -> None:
    text = "Tel: 06 12 34 56 78 — mail: agent@prefet.gouv.fr"
    block = _block(text)
    results = detect_regex([block])

    assert any(d.entity_type == EntityType.PHONE for d in results)
    assert any(d.entity_type == EntityType.EMAIL for d in results)
    for det in results:
        assert text[det.start : det.end] == det.text


def test_multiple_blocks_each_contribute() -> None:
    block_a = _block("06 12 34 56 78", page=1, block_index=0)
    block_b = _block("user@example.com", page=2, block_index=1)
    results = detect_regex([block_a, block_b])

    assert len(results) == 2
    pages = {d.page for d in results}
    assert pages == {1, 2}


# ---------------------------------------------------------------------------
# invariant: text slice always equals det.text
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "06 12 34 56 78",
        "+33 6 12 34 56 78",
        "01.23.45.67.89",
        "0612345678",
        "03-45-67-89-01",
        "jean@example.fr",
        "user@sub.domain.co",
        "Contacter jean@hopital.org ou 01 23 45 67 89.",
        "06\u00a012\u00a034\u00a056\u00a078",
        "06\u00ad12\u00ad34\u00ad56\u00ad78",
        "06\u200b12\u200b34\u200b56\u200b78",
    ],
)
def test_slice_invariant(text: str) -> None:
    block = _block(text)
    for det in detect_regex([block]):
        assert block.text[det.start : det.end] == det.text


# ---------------------------------------------------------------------------
# purity: no network, no LLM, no forbidden imports
# ---------------------------------------------------------------------------


def test_no_network_imports_in_module() -> None:
    from pathlib import Path

    source = (
        Path(__file__).parent.parent / "src" / "incognito" / "pipeline" / "detect_regex.py"
    ).read_text()
    for forbidden in ("httpx", "requests", "urllib", "socket", "ollama"):
        assert forbidden not in source


def test_no_fitz_import_in_module() -> None:
    from pathlib import Path

    source = (
        Path(__file__).parent.parent / "src" / "incognito" / "pipeline" / "detect_regex.py"
    ).read_text()
    assert "fitz" not in source
