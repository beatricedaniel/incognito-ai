from __future__ import annotations

import logging
from typing import Final

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from incognito.api.routes import router
from incognito.core.config import STATIC_DIR
from incognito.core.exceptions import IncognitoError
from incognito.core.tempfiles import cleanup_orphaned_temp_dirs

logger: Final = logging.getLogger(__name__)


def create_app() -> FastAPI:
    app = FastAPI(title="incognito", version="0.1.0")

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
