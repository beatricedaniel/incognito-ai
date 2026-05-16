from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Final

from gliner import GLiNER

from incognito.core.config import GLINER_MODEL
from incognito.core.exceptions import DetectionError

if TYPE_CHECKING:
    pass

logger: Final = logging.getLogger(__name__)

_model: GLiNER | None = None


def load_model() -> GLiNER:
    global _model  # noqa: PLW0603
    if _model is not None:
        return _model
    logger.info("Loading GLiNER model %s", GLINER_MODEL)
    try:
        loaded = GLiNER.from_pretrained(GLINER_MODEL)
    except Exception as exc:
        raise DetectionError(f"Failed to load GLiNER model {GLINER_MODEL}") from exc
    _model = loaded
    logger.info("GLiNER model loaded")
    return _model
