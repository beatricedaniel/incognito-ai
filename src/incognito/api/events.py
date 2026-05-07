from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Final

STAGE_UPDATE: Final[str] = "stage_update"
PIPELINE_ERROR: Final[str] = "pipeline_error"
PIPELINE_COMPLETE: Final[str] = "pipeline_complete"


def sse_event(event_type: str, data: dict[str, object]) -> str:
    return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"


def stage_updates(stages: Iterator[tuple[str, str]]) -> Iterator[str]:
    for stage, message in stages:
        yield sse_event(STAGE_UPDATE, {"stage": stage, "message": message})
