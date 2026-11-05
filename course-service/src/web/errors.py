from uuid import UUID

from fastapi import Request
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse

from src.core.exceptions import ServiceError
from src.web.schemas.base import ErrorDetail, ErrorResponse


def error_response(
    request: Request, status: int, code: str, message: str
) -> JSONResponse:
    body = ErrorResponse(
        error=ErrorDetail(
            code=code,
            message=message,
            status=status,
            path=request.url.path,
            request_id=UUID(str(request.state.request_id)),
        )
    )
    headers = {"WWW-Authenticate": "Bearer"} if status == 401 else None
    return JSONResponse(
        body.model_dump(mode="json"),
        status_code=status,
        media_type="application/problem+json",
        headers=headers,
    )


async def service_error_handler(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, ServiceError)
    return error_response(request, exc.status, exc.code, exc.message)


async def validation_error_handler(request: Request, _exc: Exception) -> JSONResponse:
    return error_response(
        request, 422, "VALIDATION_ERROR", "Некорректные параметры или тело запроса"
    )


async def http_error_handler(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, HTTPException)
    return error_response(request, exc.status_code, "HTTP_ERROR", str(exc.detail))
