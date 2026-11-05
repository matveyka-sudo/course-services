import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI

from src.core.database import Database
from src.web.services.checker import CheckerService

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan_app(app: FastAPI) -> AsyncIterator[None]:
    settings = app.state.settings
    database = Database(settings.database)
    await database.connect()
    try:
        async with httpx.AsyncClient(timeout=settings.checker.timeout) as client:
            app.state.database = database
            app.state.checker = CheckerService(database, client, settings.checker)
            logger.info("Application started")
            yield
    finally:
        await database.close()
        logger.info("Application stopped")
