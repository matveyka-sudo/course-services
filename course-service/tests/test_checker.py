import asyncio
from time import perf_counter

import httpx
import pytest

from src.core.config import CheckerSettings
from src.web.schemas.submissions import Submission
from src.web.services.checker import CheckerService
from tests.test_api import BASE, headers


@pytest.mark.parametrize(
    "concurrency,delay", [(1, 0.01), (1, 0.03), (2, 0.01), (2, 0.03), (4, 0.03)]
)
async def test_checker_concurrency(app, client, resources, concurrency, delay):
    submissions = [Submission.model_validate(resources["submission"])]
    for _ in range(3):
        response = await client.post(
            f"{BASE}/submissions",
            json={"assignment_id": resources["assignment"]["id"], "solution": "answer"},
            headers=headers("student", 10),
        )
        submissions.append(Submission.model_validate(response.json()))
    active = 0
    peak = 0

    async def respond(request):
        nonlocal active, peak
        assert request.headers["Idempotency-Key"]
        active += 1
        peak = max(peak, active)
        try:
            await asyncio.sleep(delay)
            return httpx.Response(200, json={"status": "COMPLETED"})
        finally:
            active -= 1

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as external:
        checker = CheckerService(
            app.state.database,
            external,
            CheckerSettings(
                url="https://checker.test/check", timeout=2, concurrency=concurrency
            ),
        )
        started = perf_counter()
        await asyncio.gather(*(checker.check(submission) for submission in submissions))
        elapsed = perf_counter() - started
    assert peak == concurrency
    for submission in submissions:
        response = await client.get(
            f"{BASE}/submissions/{submission.id}", headers=headers("student", 10)
        )
        assert response.json()["status"] == "COMPLETED"
    print(
        f"concurrency={concurrency} delay_ms={delay * 1000:.0f} elapsed_ms={elapsed * 1000:.0f} peak={peak}"
    )


@pytest.mark.parametrize(
    "failure", ["timeout", "http", "invalid_json", "invalid_status", "invalid_shape"]
)
async def test_checker_failures(app, client, resources, failure):
    async def respond(_request):
        if failure == "timeout":
            await asyncio.sleep(0.1)
        if failure == "http":
            return httpx.Response(503)
        if failure == "invalid_json":
            return httpx.Response(200, text="broken")
        if failure == "invalid_shape":
            return httpx.Response(200, json=[])
        return httpx.Response(200, json={"status": "PENDING"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as external:
        checker = CheckerService(
            app.state.database,
            external,
            CheckerSettings(url="https://checker.test/check", timeout=0.02),
        )
        await checker.check(Submission.model_validate(resources["submission"]))
    response = await client.get(
        f"{BASE}/submissions/{resources['submission']['id']}",
        headers=headers("student", 10),
    )
    assert response.json()["status"] == "FAILED"


async def test_submission_triggers_checker_once(app, client, resources):
    calls = 0

    async def respond(_request):
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={"status": "COMPLETED"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as external:
        app.state.checker = CheckerService(
            app.state.database,
            external,
            CheckerSettings(url="https://checker.test/check"),
        )
        body = {"assignment_id": resources["assignment"]["id"], "solution": "answer"}
        created = await client.post(
            f"{BASE}/submissions", json=body, headers=headers("student", 10, "checker")
        )
        assert created.status_code == 201
        assert created.json()["status"] == "SUBMITTED"
        replay = await client.post(
            f"{BASE}/submissions", json=body, headers=headers("student", 10, "checker")
        )
        assert replay.json() == created.json()
        assert calls == 1
        response = await client.get(
            f"{BASE}/submissions/{created.json()['id']}", headers=headers("student", 10)
        )
        assert response.json()["status"] == "COMPLETED"
