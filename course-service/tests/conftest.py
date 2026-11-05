import asyncio
import os
import re
import subprocess
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import asyncpg
import httpx
import jwt
import pytest
from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012
from sqlalchemy import make_url

from src.core.config import ROOT, Settings
from src.web.app import create_app

SECRET = "test-secret-with-at-least-thirty-two-characters"


def auth(role="admin", user_id=0, **claims):
    payload = {
        "sub": str(user_id),
        "role": role,
        "exp": datetime.now(UTC) + timedelta(hours=1),
        **claims,
    }
    return {"Authorization": f"Bearer {jwt.encode(payload, SECRET, algorithm='HS256')}"}


@pytest.fixture(scope="session")
def database_dsn():
    admin_dsn = os.environ.get("TEST_DATABASE_DSN")
    if not admin_dsn:
        pytest.skip("Set TEST_DATABASE_DSN to run PostgreSQL integration tests")
    name = f"course_service_test_{uuid4().hex}"
    dsn = make_url(admin_dsn).set(database=name).render_as_string(hide_password=False)

    async def create():
        connection = await asyncpg.connect(admin_dsn)
        try:
            await connection.execute(f'CREATE DATABASE "{name}"')
        finally:
            await connection.close()

    async def drop():
        connection = await asyncpg.connect(admin_dsn)
        try:
            await connection.execute(f'DROP DATABASE "{name}" WITH (FORCE)')
        finally:
            await connection.close()

    asyncio.run(create())
    try:
        environment = {**os.environ, "DATABASE__DSN": dsn}
        subprocess.run(
            [str(ROOT / ".venv/bin/alembic"), "upgrade", "head"],
            cwd=ROOT,
            env=environment,
            check=True,
        )
        yield dsn
        subprocess.run(
            [str(ROOT / ".venv/bin/alembic"), "downgrade", "base"],
            cwd=ROOT,
            env=environment,
            check=True,
        )
        subprocess.run(
            [str(ROOT / ".venv/bin/alembic"), "upgrade", "head"],
            cwd=ROOT,
            env=environment,
            check=True,
        )
    finally:
        asyncio.run(drop())


@pytest.fixture
async def app(database_dsn):
    settings = Settings(
        _env_file=None,
        database={"dsn": database_dsn},
        auth={"secret": SECRET},
        max_upload_bytes=1024,
    )
    application = create_app(settings)
    async with application.router.lifespan_context(application):
        async with application.state.database.transaction() as connection:
            await connection.execute(
                "TRUNCATE courses, assignments, submissions, reviews, artifacts, idempotency_keys CASCADE"
            )
        yield application


@pytest.fixture
async def client(app):
    contract = app.openapi()
    registry = Registry().with_resource(
        "urn:course:api", Resource(contract, DRAFT202012)
    )

    async def validate_response(response):
        await response.aread()
        for template, path_item in contract["paths"].items():
            pattern = re.sub(r"\{[^}]+\}", "[^/]+", template)
            if re.fullmatch(pattern, response.request.url.path):
                operation = path_item.get(response.request.method.lower(), {})
                description = operation.get("responses", {}).get(
                    str(response.status_code)
                )
                if description is None:
                    return
                if "$ref" in description:
                    description = (
                        registry.resolver("urn:course:api")
                        .lookup(description["$ref"])
                        .contents
                    )
                media = description.get("content", {}).get(
                    response.headers.get("Content-Type", "").split(";")[0]
                )
                if media:
                    validator = Draft202012Validator(
                        contract, registry=registry
                    ).evolve(schema=media["schema"])
                    validator.validate(response.json())
                return

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
        event_hooks={"response": [validate_response]},
    ) as session:
        yield session


@pytest.fixture
async def resources(client):
    async def create(path, body, role, user_id):
        response = await client.post(
            path,
            json=body,
            headers={**auth(role, user_id), "Idempotency-Key": uuid4().hex},
        )
        assert response.status_code == 201, response.text
        return response.json()

    course = await create(
        "/api/v1/courses",
        {"title": "Python", "professor_id": 1, "student_ids": [10, 11]},
        "admin",
        0,
    )
    assignment = await create(
        "/api/v1/assignments",
        {"title": "Async", "course_id": course["id"]},
        "professor",
        1,
    )
    submission = await create(
        "/api/v1/submissions",
        {"assignment_id": assignment["id"], "solution": "print(1)"},
        "student",
        10,
    )
    return {"course": course, "assignment": assignment, "submission": submission}
