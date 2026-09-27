from collections.abc import Sequence
from typing import Any

from fastapi import APIRouter, FastAPI

from src.core.config import Settings


def create_app(
    settings: Settings, routers: Sequence[APIRouter], **params: Any
) -> FastAPI:
    """Создание приложения и добавление в него роутеров"""

    app_params = {**settings.app.model_dump(), **params}

    app = FastAPI(**app_params)

    for router in routers:
        app.include_router(router)

    return app
