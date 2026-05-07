from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

from incognito.core.config import SESSION_TIMEOUT_SECONDS
from incognito.core.exceptions import SessionError
from incognito.models import Detection, SessionState

_sessions: dict[str, Session] = {}


@dataclass
class Session:
    id: str
    state: SessionState
    pdf_path: Path | None = None
    detections: list[Detection] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)


def create_session() -> Session:
    sid = uuid.uuid4().hex
    session = Session(id=sid, state=SessionState.UPLOADING)
    _sessions[sid] = session
    return session


def get_session(session_id: str) -> Session:
    session = _sessions.get(session_id)
    if session is None:
        raise SessionError(f"Session not found: {session_id}")
    return session


def delete_session(session_id: str) -> None:
    _sessions.pop(session_id, None)


TIMEOUT: Final[int] = SESSION_TIMEOUT_SECONDS


def cleanup_expired_sessions() -> None:
    now = time.time()
    expired = [sid for sid, s in _sessions.items() if now - s.updated_at > TIMEOUT]
    for sid in expired:
        _sessions.pop(sid, None)
