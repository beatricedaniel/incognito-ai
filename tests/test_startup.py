from __future__ import annotations

from pathlib import Path
from typing import Final
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_EXPECTED_URL: Final[str] = "http://127.0.0.1:8642"


def _make_app(tmp_path: Path) -> FastAPI:
    """Return a FastAPI instance with side-effect dependencies neutralised."""
    static_dir = tmp_path / "static"
    static_dir.mkdir()
    (static_dir / "index.html").write_text("<html></html>")

    with (
        patch("incognito.app.STATIC_DIR", static_dir),
        patch("incognito.app.cleanup_orphaned_temp_dirs"),
    ):
        from incognito.app import create_app

        return create_app()


# ---------------------------------------------------------------------------
# Story 9.4 — browser open moved out of main.py
# ---------------------------------------------------------------------------


def test_main_run_does_not_call_webbrowser_open() -> None:
    """After the fix, main.run() must NOT call webbrowser.open directly.

    Verifies that the webbrowser module is not even imported in main.py.
    """
    import incognito.main as main_module

    assert not hasattr(
        main_module, "webbrowser"
    ), "main.py should no longer import webbrowser — browser open moved to app.py lifespan"


# ---------------------------------------------------------------------------
# Story 9.4 — app.py gains a lifespan handler
# ---------------------------------------------------------------------------


def test_create_app_has_lifespan(tmp_path: Path) -> None:
    """After the fix, app.py must expose a module-level `_lifespan` async context
    manager and pass it to FastAPI, so create_app()'s lifespan is our function and
    not the FastAPI default.

    This test FAILS before the fix because app.py defines no `_lifespan` symbol.
    """
    import incognito.app as app_module

    assert hasattr(
        app_module, "_lifespan"
    ), "Expected incognito.app to define a module-level `_lifespan` context manager."

    app = _make_app(tmp_path)

    # The app's lifespan_context must not be the bare FastAPI default.
    import fastapi.routing

    assert not isinstance(
        app.router.lifespan_context, fastapi.routing._DefaultLifespan
    ), "Expected create_app() to wire up the custom _lifespan, got the FastAPI default."


@pytest.mark.asyncio
async def test_lifespan_opens_browser(tmp_path: Path) -> None:
    """Lifespan must call webbrowser.open with the server URL when NO_BROWSER is False.

    This test FAILS before the fix because app.py imports no webbrowser and has no
    lifespan context manager.
    """
    static_dir = tmp_path / "static"
    static_dir.mkdir()
    (static_dir / "index.html").write_text("<html></html>")

    browser_mock = MagicMock()

    with (
        patch("incognito.app.STATIC_DIR", static_dir),
        patch("incognito.app.cleanup_orphaned_temp_dirs"),
        patch("incognito.app.NO_BROWSER", False),
        patch("incognito.app.webbrowser.open", browser_mock),
    ):
        from incognito.app import create_app

        app = create_app()

        async with app.router.lifespan_context(app):
            pass

    browser_mock.assert_called_once_with(_EXPECTED_URL)


@pytest.mark.asyncio
async def test_lifespan_skips_browser_when_no_browser_set(tmp_path: Path) -> None:
    """Lifespan must NOT call webbrowser.open when NO_BROWSER is True.

    This test FAILS before the fix because app.py has no lifespan and no NO_BROWSER
    constant.
    """
    static_dir = tmp_path / "static"
    static_dir.mkdir()
    (static_dir / "index.html").write_text("<html></html>")

    browser_mock = MagicMock()

    with (
        patch("incognito.app.STATIC_DIR", static_dir),
        patch("incognito.app.cleanup_orphaned_temp_dirs"),
        patch("incognito.app.NO_BROWSER", True),
        patch("incognito.app.webbrowser.open", browser_mock),
    ):
        from incognito.app import create_app

        app = create_app()

        async with app.router.lifespan_context(app):
            pass

    browser_mock.assert_not_called()
