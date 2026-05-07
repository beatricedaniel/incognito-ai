from __future__ import annotations

import atexit
import logging
import shutil
import tempfile
from pathlib import Path
from typing import Final

from incognito.core.config import TEMP_DIR_PERMISSIONS, TEMP_PREFIX

logger: Final = logging.getLogger(__name__)

_active_dirs: list[Path] = []


class TempFileManager:
    def __init__(self) -> None:
        raw = tempfile.mkdtemp(prefix=TEMP_PREFIX)
        self._root = Path(raw)
        self._root.chmod(TEMP_DIR_PERMISSIONS)
        _active_dirs.append(self._root)

    @property
    def root(self) -> Path:
        return self._root

    def create_file(self, name: str) -> Path:
        path = self._root / name
        path.touch()
        return path

    def cleanup(self) -> None:
        if self._root.exists():
            shutil.rmtree(self._root)
        if self._root in _active_dirs:
            _active_dirs.remove(self._root)

    def __enter__(self) -> TempFileManager:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        self.cleanup()


def cleanup_orphaned_temp_dirs() -> None:
    tmp = Path(tempfile.gettempdir())
    for entry in tmp.iterdir():
        if entry.is_dir() and entry.name.startswith(TEMP_PREFIX) and entry not in _active_dirs:
            logger.info("Removing orphaned temp dir: %s", entry.name)
            shutil.rmtree(entry)


def _cleanup_at_exit() -> None:
    for d in list(_active_dirs):
        if d.exists():
            shutil.rmtree(d)
    _active_dirs.clear()


atexit.register(_cleanup_at_exit)
