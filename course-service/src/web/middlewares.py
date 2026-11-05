import logging
from time import perf_counter
from uuid import UUID, uuid4

from starlette.datastructures import Headers, MutableHeaders
from starlette.requests import Request
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from src.core.logging import request_id_context
from src.web.errors import error_response

logger = logging.getLogger(__name__)


class RequestMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        try:
            request_id = str(UUID(Headers(scope=scope).get("X-Request-ID", "")))
        except ValueError:
            request_id = str(uuid4())
        scope.setdefault("state", {})["request_id"] = request_id
        token = request_id_context.set(request_id)
        started = perf_counter()
        status = 500
        response_started = False
        duration_ms: float | None = None

        async def send_response(message: Message) -> None:
            nonlocal status, response_started, duration_ms
            if message["type"] == "http.response.start":
                status = message["status"]
                response_started = True
                MutableHeaders(scope=message)["X-Request-ID"] = request_id
            if message["type"] == "http.response.body" and not message.get(
                "more_body", False
            ):
                duration_ms = (perf_counter() - started) * 1000
            await send(message)

        try:
            await self.app(scope, receive, send_response)
        except Exception:
            logger.exception("Unhandled request error")
            if response_started:
                raise
            response = error_response(
                Request(scope), 500, "INTERNAL_ERROR", "Внутренняя ошибка сервиса"
            )
            await response(scope, receive, send_response)
        finally:
            logger.info(
                "%s %s status=%s duration_ms=%.2f",
                scope["method"],
                scope["path"],
                status,
                (
                    duration_ms
                    if duration_ms is not None
                    else (perf_counter() - started) * 1000
                ),
            )
            request_id_context.reset(token)
