from __future__ import annotations

import logging
import webbrowser

import uvicorn

from incognito.core.config import HOST, LOG_LEVEL, PORT

logger = logging.getLogger(__name__)


def run() -> None:
    logging.basicConfig(level=LOG_LEVEL, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    logger.info("Starting incognito on %s:%d", HOST, PORT)
    webbrowser.open(f"http://{HOST}:{PORT}")
    uvicorn.run("incognito.app:create_app", host=HOST, port=PORT, factory=True)
