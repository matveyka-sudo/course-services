from collections.abc import Sequence
from typing import Any

from fastapi import APIRouter, FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException

from src.core.config import Settings
from src.core.exceptions import ServiceError
from src.web.errors import (
    http_error_handler,
    service_error_handler,
    validation_error_handler,
)
from src.web.lifespans import lifespan_app
from src.web.middlewares import RequestMiddleware
from src.web.openapi import build_openapi
from src.web.routers import routers as default_routers


class CourseApplication(FastAPI):
    def openapi(self) -> dict[str, Any]:
        return build_openapi(self)


def create_app(
    settings: Settings, routers: Sequence[APIRouter] = default_routers, **params: Any
) -> FastAPI:
    app = CourseApplication(
        **{**settings.app.model_dump(), "lifespan": lifespan_app, **params}
    )
    app.state.settings = settings
    app.add_exception_handler(ServiceError, service_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(HTTPException, http_error_handler)
    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_methods=["GET", "POST", "PATCH", "DELETE"],
            allow_headers=[
                "Authorization",
                "Content-Type",
                "Idempotency-Key",
                "X-Request-ID",
            ],
            expose_headers=["X-Request-ID"],
        )
    app.add_middleware(RequestMiddleware)
    for router in routers:
        app.include_router(router)
    return app
