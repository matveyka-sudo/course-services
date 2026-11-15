import asyncio
from contextlib import asynccontextmanager

import httpx
import pytest

from src.core.config import CheckerSettings, DatabaseSettings
from src.core.database import Database
from src.infrastructure.outbox_repository import OutboxRepository
from src.infrastructure.outbox_worker import OutboxWorker
from src.web.services.checker import CheckerService
from tests.test_api import BASE, headers


@asynccontextmanager
async def worker(app, respond, retry_delay=0):
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        checker = CheckerService(app.state.database, client, CheckerSettings(url="https://checker.test/check"))
        yield OutboxWorker(app.state.database, checker, retry_delay)


async def event_for(app, submission_id):
    async with app.state.database.transaction() as connection:
        return await connection.fetchrow("SELECT * FROM outbox_events WHERE submission_id = $1", submission_id)


async def test_submission_and_event_are_idempotent(app, client, resources):
    body = {"assignment_id": resources["assignment"]["id"], "solution": "answer"}
    responses = await asyncio.gather(*(
        client.post(f"{BASE}/submissions", json=body, headers=headers("student", 10, "outbox"))
        for _ in range(6)
    ))
    assert all(response.status_code == 201 for response in responses)
    result = responses[0].json()
    assert all(response.json() == result for response in responses)
    async with app.state.database.transaction() as connection:
        assert await connection.fetchval("SELECT count(*) FROM outbox_events") == 2
    event = await event_for(app, result["id"])
    assert event["payload"] == result
    assert event["processed_at"] is None
    assert event["attempts"] == 0


async def test_outbox_failure_rolls_back_submission_and_idempotency(app, client, resources, monkeypatch):
    original = OutboxRepository.add

    async def fail(self, submission_id, payload):
        await original(self, submission_id, payload)
        raise RuntimeError("Outbox unavailable")

    body = {"assignment_id": resources["assignment"]["id"], "solution": "answer"}
    with monkeypatch.context() as patch:
        patch.setattr(OutboxRepository, "add", fail)
        response = await client.post(f"{BASE}/submissions", json=body, headers=headers("student", 10, "rollback-outbox"))
    assert response.status_code == 500
    async with app.state.database.transaction() as connection:
        assert await connection.fetchval("SELECT count(*) FROM submissions") == 1
        assert await connection.fetchval("SELECT count(*) FROM outbox_events") == 1
        assert await connection.fetchval("SELECT count(*) FROM idempotency_keys WHERE key = 'rollback-outbox'") == 0
    retried = await client.post(f"{BASE}/submissions", json=body, headers=headers("student", 10, "rollback-outbox"))
    assert retried.status_code == 201
    assert retried.json()["attempt"] == 2
    assert await event_for(app, retried.json()["id"]) is not None


async def test_worker_delivers_once(app, resources):
    calls = []

    async def respond(request):
        calls.append(request)
        return httpx.Response(200, json={"status": "COMPLETED"})

    async with worker(app, respond) as runner:
        assert await runner.process_once()
        assert not await runner.process_once()
    assert len(calls) == 1
    assert calls[0].headers["Idempotency-Key"] == resources["submission"]["id"]
    event = await event_for(app, resources["submission"]["id"])
    assert event["processed_at"] is not None
    assert event["attempts"] == 1
    async with app.state.database.transaction() as connection:
        assert await connection.fetchval("SELECT status FROM submissions WHERE id = $1", event["submission_id"]) == "COMPLETED"


async def test_worker_retries_with_same_payload_and_key(app, resources):
    calls = []

    async def respond(request):
        calls.append(request)
        if len(calls) == 1:
            return httpx.Response(503)
        return httpx.Response(200, json={"status": "COMPLETED"})

    async with worker(app, respond, retry_delay=5) as runner:
        assert await runner.process_once()
        event = await event_for(app, resources["submission"]["id"])
        assert event["attempts"] == 1
        assert event["processed_at"] is None
        assert not await runner.process_once()
        async with app.state.database.transaction() as connection:
            assert await connection.fetchval("SELECT status FROM submissions WHERE id = $1", event["submission_id"]) == "FAILED"
            await connection.execute("UPDATE outbox_events SET available_at = clock_timestamp() - interval '1 second'")
        assert await runner.process_once()
        assert not await runner.process_once()
    assert len(calls) == 2
    assert calls[0].content == calls[1].content
    assert calls[0].headers["Idempotency-Key"] == calls[1].headers["Idempotency-Key"]
    event = await event_for(app, resources["submission"]["id"])
    assert event["processed_at"] is not None
    assert event["attempts"] == 2


async def test_workers_do_not_process_same_event_together(app, resources):
    started = asyncio.Event()
    release = asyncio.Event()
    calls = 0

    async def respond(request):
        nonlocal calls
        calls += 1
        started.set()
        await release.wait()
        return httpx.Response(200, json={"status": "COMPLETED"})

    async with worker(app, respond) as first, worker(app, respond) as second:
        task = asyncio.create_task(first.process_once())
        try:
            await asyncio.wait_for(started.wait(), timeout=3)
            assert not await asyncio.wait_for(second.process_once(), timeout=3)
        finally:
            release.set()
            await task
    assert calls == 1


async def test_workers_can_process_different_events(app, client, resources):
    response = await client.post(
        f"{BASE}/submissions", headers=headers("student", 10),
        json={"assignment_id": resources["assignment"]["id"], "solution": "second"},
    )
    assert response.status_code == 201
    both_started = asyncio.Event()
    release = asyncio.Event()
    ids = []

    async def respond(request):
        ids.append(request.headers["Idempotency-Key"])
        if len(ids) == 2:
            both_started.set()
        await release.wait()
        return httpx.Response(200, json={"status": "COMPLETED"})

    async with worker(app, respond) as first, worker(app, respond) as second:
        tasks = [asyncio.create_task(runner.process_once()) for runner in (first, second)]
        try:
            await asyncio.wait_for(both_started.wait(), timeout=3)
        finally:
            release.set()
            results = await asyncio.gather(*tasks)
    assert results == [True, True]
    assert len(set(ids)) == 2


async def test_failure_after_remote_success_can_be_retried(app, resources, monkeypatch):
    requests = []
    remote_results = set()

    async def respond(request):
        requests.append(request)
        remote_results.add(request.headers["Idempotency-Key"])
        return httpx.Response(200, json={"status": "COMPLETED"})

    async def fail(*args):
        raise RuntimeError("Failed before commit")

    async with worker(app, respond) as runner:
        with monkeypatch.context() as patch:
            patch.setattr(OutboxRepository, "finish", fail)
            with pytest.raises(RuntimeError, match="Failed before commit"):
                await runner.process_once()
        event = await event_for(app, resources["submission"]["id"])
        assert event["processed_at"] is None
        assert event["attempts"] == 0
        async with app.state.database.transaction() as connection:
            assert await connection.fetchval("SELECT status FROM submissions WHERE id = $1", event["submission_id"]) == "SUBMITTED"
        assert await runner.process_once()
    assert len(requests) == 2
    assert requests[0].content == requests[1].content
    assert len(remote_results) == 1


async def test_completed_submission_is_not_checked_again(app, resources):
    async with app.state.database.transaction() as connection:
        await connection.execute("UPDATE submissions SET status = 'COMPLETED'")

    async def respond(request):
        pytest.fail("Completed submission was checked again")

    async with worker(app, respond) as runner:
        assert await runner.process_once()
    assert (await event_for(app, resources["submission"]["id"]))["processed_at"] is not None


async def test_cancellation_releases_event_for_retry(app, resources):
    started = asyncio.Event()
    calls = 0

    async def respond(request):
        nonlocal calls
        calls += 1
        if calls == 1:
            started.set()
            await asyncio.Event().wait()
        return httpx.Response(200, json={"status": "COMPLETED"})

    async with worker(app, respond) as runner:
        task = asyncio.create_task(runner.process_once())
        try:
            await asyncio.wait_for(started.wait(), timeout=3)
        finally:
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        event = await event_for(app, resources["submission"]["id"])
        assert event["processed_at"] is None
        assert await runner.process_once()
    assert calls == 2


async def test_worker_uses_one_connection(app, resources):
    database = Database(DatabaseSettings(dsn=app.state.database.settings.dsn, max_pool_size=1))
    await database.connect()

    async def respond(request):
        return httpx.Response(200, json={"status": "COMPLETED"})

    try:
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            checker = CheckerService(database, client, CheckerSettings(url="https://checker.test/check"))
            assert await asyncio.wait_for(OutboxWorker(database, checker).process_once(), timeout=3)
    finally:
        await database.close()


async def test_disabled_checker_keeps_event(app, resources):
    runner = OutboxWorker(app.state.database, app.state.checker)
    assert not await runner.process_once()
    event = await event_for(app, resources["submission"]["id"])
    assert event["processed_at"] is None
    assert event["attempts"] == 0
