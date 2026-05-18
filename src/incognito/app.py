from __future__ import annotations

import asyncio
import logging
import webbrowser
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Final

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from incognito.api.routes import router
from incognito.core.config import HOST, NO_BROWSER, PORT, STATIC_DIR
from incognito.core.exceptions import IncognitoError
from incognito.core.tempfiles import cleanup_orphaned_temp_dirs

logger: Final = logging.getLogger(__name__)

_BROWSER_OPEN_TIMEOUT: Final[float] = 5.0


@asynccontextmanager
async def _lifespan(_app: FastAPI) -> AsyncIterator[None]:
    if not NO_BROWSER:
        loop = asyncio.get_running_loop()
        try:
            await asyncio.wait_for(
                loop.run_in_executor(None, webbrowser.open, f"http://{HOST}:{PORT}"),
                timeout=_BROWSER_OPEN_TIMEOUT,
            )
        except TimeoutError:
            logger.warning("Browser open timed out after %.1fs", _BROWSER_OPEN_TIMEOUT)
        except OSError:
            logger.warning("Failed to open browser", exc_info=True)
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="incognito", version="0.1.0", lifespan=_lifespan)

    cleanup_orphaned_temp_dirs()

    app.include_router(router)

    @app.exception_handler(IncognitoError)
    async def handle_incognito_error(request: Request, exc: IncognitoError) -> JSONResponse:
        logger.error("%s: %s", type(exc).__name__, exc)
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": exc.error, "detail": exc.detail},
        )

    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")

    return app
