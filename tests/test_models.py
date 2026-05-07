from __future__ import annotations

from incognito.models import BBox, Detection, EntityType, TextBlock


def test_entity_type_values() -> None:
    assert EntityType.PERSON == "person"
    assert EntityType.ADDRESS == "address"
    assert EntityType.PHONE == "phone"
    assert EntityType.EMAIL == "email"


def test_bbox_immutable() -> None:
    bbox = BBox(x=0.0, y=0.0, width=100.0, height=20.0)
    assert bbox.x == 0.0
    assert bbox.width == 100.0


def test_text_block_creation() -> None:
    block = TextBlock(
        text="Jean Dupont",
        page=0,
        bbox=BBox(x=10.0, y=20.0, width=100.0, height=12.0),
        block_index=0,
    )
    assert block.text == "Jean Dupont"
    assert block.page == 0


def test_detection_has_id() -> None:
    det = Detection(
        text="Jean Dupont",
        entity_type=EntityType.PERSON,
        page=0,
        start=0,
        end=11,
        bbox=BBox(x=10.0, y=20.0, width=100.0, height=12.0),
    )
    assert len(det.id) == 32
    assert det.dismissed is False
    assert det.validated is True
