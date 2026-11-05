from uuid import UUID

import httpx
import pytest

from src.core.config import Settings
from src.web.app import create_app


@pytest.mark.parametrize(
    "path,status",
    [("/service", 200), ("/openapi.json", 200), ("/docs", 200), ("/missing", 404)],
)
async def test_public_routes(path, status):
    app = create_app(Settings(_env_file=None))
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(path)
    assert response.status_code == status
    UUID(response.headers["X-Request-ID"])
    if path == "/service":
        assert response.json() == {"healthy": True}
    if path == "/openapi.json":
        assert response.json()["openapi"] == "3.1.0"


async def test_request_id_and_error_body():
    app = create_app(Settings(_env_file=None))
    request_id = "00000000-0000-0000-0000-000000000001"
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(
            "/api/v1/courses", headers={"X-Request-ID": request_id}
        )
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"
    assert response.headers["X-Request-ID"] == request_id
    assert response.headers["Content-Type"] == "application/problem+json"
    assert response.json()["error"] == {
        "code": "TOKEN_MISSING",
        "message": "Токен отсутствует",
        "status": 401,
        "path": "/api/v1/courses",
        "request_id": request_id,
    }


async def test_internal_error_is_sanitized():
    app = create_app(Settings(_env_file=None))

    @app.get("/broken")
    async def broken():
        raise RuntimeError("sensitive information")

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/broken")
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL_ERROR"
    assert "sensitive" not in response.text
    UUID(response.headers["X-Request-ID"])


async def test_every_api_operation_requires_authentication():
    app = create_app(Settings(_env_file=None))
    contract = app.openapi()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        for template, item in contract["paths"].items():
            if not template.startswith("/api/v1"):
                continue
            path = template.replace("{id}", "00000000-0000-0000-0000-000000000001")
            for method in item:
                if method in ("get", "post", "patch", "delete"):
                    response = await client.request(method, path)
                    assert response.status_code == 401, (method, path, response.text)


async def test_parallel_request_contexts():
    import asyncio

    from src.core.logging import request_id_context

    app = create_app(Settings(_env_file=None))

    @app.get("/context")
    async def context():
        before = request_id_context.get()
        await asyncio.sleep(0.01)
        return {"before": before, "after": request_id_context.get()}

    ids = [f"00000000-0000-0000-0000-{index:012d}" for index in range(1, 11)]
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        responses = await asyncio.gather(
            *(client.get("/context", headers={"X-Request-ID": value}) for value in ids)
        )
        invalid = await client.get("/context", headers={"X-Request-ID": "invalid"})
    for value, response in zip(ids, responses, strict=True):
        assert response.json() == {"before": value, "after": value}
        assert response.headers["X-Request-ID"] == value
    UUID(invalid.headers["X-Request-ID"])
    assert request_id_context.get() == "-"


async def test_cors():
    app = create_app(Settings(_env_file=None, cors_origins=["http://localhost:3000"]))
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.options(
            "/api/v1/courses",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Authorization, Idempotency-Key",
            },
        )
        assert response.status_code == 200
        assert (
            response.headers["Access-Control-Allow-Origin"] == "http://localhost:3000"
        )
        denied = await client.options(
            "/api/v1/courses",
            headers={
                "Origin": "http://untrusted.test",
                "Access-Control-Request-Method": "POST",
            },
        )
        assert denied.status_code == 400
