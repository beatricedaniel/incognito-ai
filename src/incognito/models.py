from __future__ import annotations

import enum
import uuid
from typing import Final

from pydantic import BaseModel, Field

ENTITY_TYPES: Final = ("person", "address", "phone", "email")


class EntityType(enum.StrEnum):
    PERSON = "person"
    ADDRESS = "address"
    PHONE = "phone"
    EMAIL = "email"


class BBox(BaseModel, frozen=True):
    x: float
    y: float
    width: float
    height: float


class TextBlock(BaseModel, frozen=True):
    text: str
    page: int
    bbox: BBox
    block_index: int


class RawDetection(BaseModel, frozen=True):
    text: str
    entity_type: EntityType
    start: int
    end: int
    page: int
    bbox: BBox
    block_index: int


class Detection(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    text: str
    entity_type: EntityType
    page: int
    start: int
    end: int
    bbox: BBox
    validated: bool = True
    dismissed: bool = False


class SessionState(enum.StrEnum):
    UPLOADING = "uploading"
    PROCESSING = "processing"
    REVIEWING = "reviewing"
    REDACTING = "redacting"
    COMPLETE = "complete"
    ERROR = "error"
