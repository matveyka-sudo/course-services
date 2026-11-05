import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from tests.conftest import auth

BASE = "/api/v1"


def headers(role="admin", user_id=0, key=None):
    return {**auth(role, user_id), "Idempotency-Key": key or uuid4().hex}


async def test_course_crud(client):
    body = {"title": "Python", "professor_id": 1, "student_ids": [10]}
    created = await client.post(
        f"{BASE}/courses", json=body, headers=headers(key="course")
    )
    assert created.status_code == 201
    course_id = created.json()["id"]
    duplicate = await client.post(
        f"{BASE}/courses", json=body, headers=headers(key="course")
    )
    assert duplicate.json() == created.json()
    conflict = await client.post(
        f"{BASE}/courses",
        json={**body, "title": "Other"},
        headers=headers(key="course"),
    )
    assert conflict.status_code == 409
    listed = await client.get(f"{BASE}/courses", headers=auth("student", 10))
    assert listed.json()["pagination"] == {"offset": 0, "limit": 12, "total": 1}
    assert listed.json()["data"][0]["id"] == course_id
    fetched = await client.get(f"{BASE}/courses/{course_id}", headers=auth())
    assert fetched.json() == created.json()
    patched = await client.patch(
        f"{BASE}/courses/{course_id}",
        json={"title": "New"},
        headers=auth("professor", 1),
    )
    assert patched.status_code == 200
    assert patched.json()["title"] == "New"
    assert patched.json()["professor_id"] == 1
    deleted = await client.delete(f"{BASE}/courses/{course_id}", headers=auth())
    assert deleted.status_code == 204
    assert deleted.content == b""
    assert (
        await client.get(f"{BASE}/courses/{course_id}", headers=auth())
    ).status_code == 404


async def test_assignment_crud(client, resources):
    body = {"title": "Second assignment", "course_id": resources["course"]["id"]}
    created = await client.post(
        f"{BASE}/assignments", json=body, headers=headers("professor", 1, "assignment")
    )
    assert created.status_code == 201
    assignment_id = created.json()["id"]
    duplicate = await client.post(
        f"{BASE}/assignments", json=body, headers=headers("professor", 1, "assignment")
    )
    assert duplicate.json() == created.json()
    listed = await client.get(f"{BASE}/assignments", headers=auth("student", 10))
    assert listed.json()["pagination"]["total"] == 2
    assert listed.json()["data"][-1]["id"] == assignment_id
    fetched = await client.get(
        f"{BASE}/assignments/{assignment_id}", headers=auth("student", 10)
    )
    assert fetched.json() == created.json()
    patched = await client.patch(
        f"{BASE}/assignments/{assignment_id}",
        json={"description": "Updated"},
        headers=auth("professor", 1),
    )
    assert patched.status_code == 200
    assert patched.json()["description"] == "Updated"
    deleted = await client.delete(
        f"{BASE}/assignments/{assignment_id}", headers=auth("professor", 1)
    )
    assert deleted.status_code == 204
    assert deleted.content == b""
    assert (
        await client.get(f"{BASE}/assignments/{assignment_id}", headers=auth())
    ).status_code == 404


async def test_submission_read_and_immutable(client, resources):
    submission = resources["submission"]
    path = f"{BASE}/submissions/{submission['id']}"
    fetched = await client.get(path, headers=auth("student", 10))
    assert fetched.json() == submission
    assert fetched.json()["status"] == "SUBMITTED"
    for role, user_id in [("student", 10), ("professor", 1)]:
        response = await client.get(f"{BASE}/submissions", headers=auth(role, user_id))
        assert response.status_code == 200
        assert response.json()["pagination"]["total"] == 1
    assert (
        await client.patch(path, json={"solution": "new"}, headers=auth("student", 10))
    ).status_code == 405
    assert (await client.delete(path, headers=auth("student", 10))).status_code == 405


async def test_review_crud(client, resources):
    path = f"{BASE}/submissions/{resources['submission']['id']}/review"
    assert (await client.get(path, headers=auth("student", 10))).status_code == 404
    response = await client.post(
        path,
        json={"grade": 80, "comment": "Good"},
        headers=headers("professor", 1, "review"),
    )
    assert response.status_code == 201
    replay = await client.post(
        path,
        json={"grade": 80, "comment": "Good"},
        headers=headers("professor", 1, "review"),
    )
    assert replay.json() == response.json()
    conflict = await client.post(
        path, json={"grade": 90}, headers=headers("professor", 1)
    )
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "REVIEW_ALREADY_EXISTS"
    fetched = await client.get(path, headers=auth("student", 10))
    assert fetched.json() == response.json()
    patched = await client.patch(
        path, json={"grade": 100}, headers=auth("professor", 1)
    )
    assert patched.status_code == 200
    assert patched.json()["grade"] == 100
    assert patched.json()["comment"] == "Good"


async def test_artifacts(client, resources):
    path = f"{BASE}/submissions/{resources['submission']['id']}/artifacts"
    assert (await client.get(path, headers=auth("student", 10))).json() == []
    file = {"file": ("answer.py", b"print(1)", "text/x-python")}
    response = await client.post(
        path, files=file, headers=headers("professor", 1, "file")
    )
    assert response.status_code == 201
    assert response.json()["size"] == 8
    assert "content" not in response.json()
    replay = await client.post(
        path, files=file, headers=headers("professor", 1, "file")
    )
    assert replay.json() == response.json()
    conflict = await client.post(
        path,
        files={"file": ("answer.py", b"other")},
        headers=headers("professor", 1, "file"),
    )
    assert conflict.status_code == 409
    listed = await client.get(path, headers=auth("student", 10))
    assert listed.json() == [response.json()]
    oversized = await client.post(
        path, files={"file": ("large", b"x" * 1025)}, headers=headers("professor", 1)
    )
    assert oversized.status_code == 422
    assert (await client.post(path, headers=headers("professor", 1))).status_code == 422


@pytest.mark.parametrize(
    "method,path,role,user_id,status",
    [
        ("post", "/courses", "student", 10, 403),
        ("patch", "/courses/{course}", "admin", 0, 403),
        ("patch", "/courses/{course}", "professor", 2, 403),
        ("delete", "/courses/{course}", "professor", 1, 403),
        ("post", "/assignments", "student", 10, 403),
        ("patch", "/assignments/{assignment}", "professor", 2, 403),
        ("delete", "/assignments/{assignment}", "student", 10, 403),
        ("get", "/assignments/{assignment}", "student", 99, 404),
        ("post", "/submissions", "professor", 1, 403),
        ("post", "/submissions", "student", 99, 403),
        ("get", "/submissions", "admin", 0, 403),
        ("get", "/submissions/{submission}", "admin", 0, 403),
        ("get", "/submissions/{submission}", "student", 11, 403),
        ("get", "/submissions/{submission}", "professor", 2, 403),
        ("get", "/submissions/{submission}/review", "admin", 0, 403),
        ("post", "/submissions/{submission}/review", "student", 10, 403),
        ("patch", "/submissions/{submission}/review", "professor", 2, 403),
        ("get", "/submissions/{submission}/artifacts", "admin", 0, 403),
        ("get", "/submissions/{submission}/artifacts", "student", 11, 403),
        ("post", "/submissions/{submission}/artifacts", "student", 10, 403),
    ],
)
async def test_permissions(client, resources, method, path, role, user_id, status):
    path = path.format(**{key: value["id"] for key, value in resources.items()})
    payloads = {
        "/courses": {"title": "Course", "professor_id": 1},
        "/assignments": {"title": "Task", "course_id": resources["course"]["id"]},
        "/submissions": {
            "assignment_id": resources["assignment"]["id"],
            "solution": "answer",
        },
    }
    arguments = {"headers": headers(role, user_id)}
    if method in ("post", "patch"):
        arguments["json"] = payloads.get(
            path, {"grade": 75} if path.endswith("/review") else {"title": "Changed"}
        )
    if path.endswith("/artifacts") and method == "post":
        arguments.pop("json")
        arguments["files"] = {"file": ("a.txt", b"answer")}
    response = await client.request(method.upper(), BASE + path, **arguments)
    assert response.status_code == status, response.text


@pytest.mark.parametrize("entity", ["courses", "assignments", "submissions"])
async def test_empty_pages_and_validation(client, resources, entity):
    role, user_id = ("student", 10)
    response = await client.get(
        f"{BASE}/{entity}?offset=1000", headers=auth(role, user_id)
    )
    assert response.status_code == 200
    assert response.json()["data"] == []
    assert response.json()["pagination"]["total"] == 1
    for query in ("offset=-1", "limit=7", "offset=bad"):
        assert (
            await client.get(f"{BASE}/{entity}?{query}", headers=auth(role, user_id))
        ).status_code == 422
    assert (
        await client.get(f"{BASE}/{entity}/not-uuid", headers=auth(role, user_id))
    ).status_code == 422
    response = await client.get(
        f"{BASE}/{entity}/{uuid4()}", headers=auth(role, user_id)
    )
    assert response.status_code == 404


async def test_validation_and_missing_key(client, resources):
    missing = await client.post(
        f"{BASE}/courses", json={"title": "Python", "professor_id": 1}, headers=auth()
    )
    assert missing.status_code == 422
    assert missing.json()["error"]["code"] == "IDEMPOTENCY_KEY_MISSING"
    for payload in ({"title": None}, {"professor_id": 2}, {"student_ids": [99]}):
        response = await client.patch(
            f"{BASE}/courses/{resources['course']['id']}",
            json=payload,
            headers=auth("professor", 1),
        )
        assert response.status_code == 422
    missing_course = await client.post(
        f"{BASE}/assignments",
        json={"title": "Task", "course_id": str(uuid4())},
        headers=headers("professor", 1),
    )
    assert missing_course.status_code == 422
    assert missing_course.json()["error"]["code"] == "COURSE_NOT_FOUND"
    missing_assignment = await client.post(
        f"{BASE}/submissions",
        json={"assignment_id": str(uuid4()), "solution": "answer"},
        headers=headers("student", 10),
    )
    assert missing_assignment.status_code == 422
    assert missing_assignment.json()["error"]["code"] == "ASSIGNMENT_NOT_FOUND"
    spoofed = await client.post(
        f"{BASE}/submissions",
        json={
            "assignment_id": resources["assignment"]["id"],
            "solution": "answer",
            "student_id": 11,
        },
        headers=headers("student", 10),
    )
    assert spoofed.status_code == 422


@pytest.mark.parametrize(
    "authorization,code",
    [
        ("Bearer invalid", "TOKEN_INVALID"),
        ("Basic abc", "TOKEN_INVALID"),
        ("Bearer", "TOKEN_INVALID"),
    ],
)
async def test_invalid_token(client, authorization, code):
    response = await client.get(
        f"{BASE}/courses", headers={"Authorization": authorization}
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == code


async def test_expired_token(client):
    response = await client.get(
        f"{BASE}/courses", headers=auth(exp=datetime.now(UTC) - timedelta(seconds=10))
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "TOKEN_EXPIRED"


async def test_student_filtering(client, resources):
    assignments = await client.get(f"{BASE}/assignments", headers=auth("student", 99))
    assert assignments.json()["pagination"]["total"] == 0
    submissions = await client.get(f"{BASE}/submissions", headers=auth("student", 11))
    assert submissions.json()["data"] == []
    professor = await client.get(f"{BASE}/submissions", headers=auth("professor", 2))
    assert professor.json()["data"] == []


async def test_concurrent_attempt_limit(client, resources):
    body = {"assignment_id": resources["assignment"]["id"], "solution": "answer"}
    responses = await asyncio.gather(
        *(
            client.post(
                f"{BASE}/submissions", json=body, headers=headers("student", 10)
            )
            for _ in range(15)
        )
    )
    accepted = [
        response.json() for response in responses if response.status_code == 201
    ]
    rejected = [response for response in responses if response.status_code == 422]
    assert len(accepted) == 9
    assert sorted(row["attempt"] for row in accepted) == list(range(2, 11))
    assert len(rejected) == 6
    assert all(
        response.json()["error"]["code"] == "SUBMISSION_LIMIT_REACHED"
        for response in rejected
    )
    page = await client.get(f"{BASE}/submissions", headers=auth("student", 10))
    assert page.json()["pagination"]["total"] == 10


async def test_concurrent_idempotency(client, resources):
    body = {"assignment_id": resources["assignment"]["id"], "solution": "answer"}
    responses = await asyncio.gather(
        *(
            client.post(
                f"{BASE}/submissions", json=body, headers=headers("student", 10, "same")
            )
            for _ in range(12)
        )
    )
    assert all(response.status_code == 201 for response in responses)
    assert len({response.json()["id"] for response in responses}) == 1
    assert all(response.json()["attempt"] == 2 for response in responses)
    conflict = await client.post(
        f"{BASE}/submissions",
        json={**body, "solution": "other"},
        headers=headers("student", 10, "same"),
    )
    assert conflict.status_code == 409


async def test_review_concurrency(client, resources):
    path = f"{BASE}/submissions/{resources['submission']['id']}/review"
    responses = await asyncio.gather(
        *(
            client.post(path, json={"grade": 90}, headers=headers("professor", 1))
            for _ in range(5)
        )
    )
    assert sorted(response.status_code for response in responses) == [
        201,
        409,
        409,
        409,
        409,
    ]


async def test_transaction_rollback(client, resources, monkeypatch):
    from src.web.repository.idempotency import IdempotencyRepository

    body = {"assignment_id": resources["assignment"]["id"], "solution": "answer"}

    async def fail(*_args, **_kwargs):
        raise RuntimeError("Failed to save idempotency record")

    with monkeypatch.context() as patch:
        patch.setattr(IdempotencyRepository, "save", fail)
        failed = await client.post(
            f"{BASE}/submissions", json=body, headers=headers("student", 10, "rollback")
        )
    assert failed.status_code == 500
    page = await client.get(f"{BASE}/submissions", headers=auth("student", 10))
    assert page.json()["pagination"]["total"] == 1
    retried = await client.post(
        f"{BASE}/submissions", json=body, headers=headers("student", 10, "rollback")
    )
    assert retried.status_code == 201
    assert retried.json()["attempt"] == 2


async def test_idempotency_between_application_instances(app, client, resources):
    import httpx

    from src.web.app import create_app

    other_app = create_app(app.state.settings)
    async with other_app.router.lifespan_context(other_app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=other_app), base_url="http://test"
        ) as other_client:
            clients = [client, other_client] * 5
            body = {
                "assignment_id": resources["assignment"]["id"],
                "solution": "answer",
            }
            responses = await asyncio.gather(
                *(
                    session.post(
                        f"{BASE}/submissions",
                        json=body,
                        headers=headers("student", 10, "two-instances"),
                    )
                    for session in clients
                )
            )
    assert all(response.status_code == 201 for response in responses)
    assert len({response.json()["id"] for response in responses}) == 1
    assert all(response.json()["attempt"] == 2 for response in responses)


async def test_fixed_page_sizes_and_sorting(client):
    courses = []
    for index in range(14):
        response = await client.post(
            f"{BASE}/courses",
            json={"title": f"Course {index}", "professor_id": 1},
            headers=headers(),
        )
        courses.append(response.json())
    first = await client.get(
        f"{BASE}/courses?limit=12&sort=created_at:desc", headers=auth()
    )
    second = await client.get(f"{BASE}/courses?offset=12", headers=auth())
    assert len(first.json()["data"]) == 12
    assert len(second.json()["data"]) == 2
    assert first.json()["data"][0]["id"] == courses[-1]["id"]
    assert first.json()["pagination"]["total"] == 14
    assignments = []
    for index in range(12):
        response = await client.post(
            f"{BASE}/assignments",
            json={"title": f"Task {index}", "course_id": courses[0]["id"]},
            headers=headers("professor", 1),
        )
        assignments.append(response.json())
    first = await client.get(f"{BASE}/assignments?sort=created_at:asc", headers=auth())
    second = await client.get(f"{BASE}/assignments?offset=10", headers=auth())
    assert len(first.json()["data"]) == 10
    assert len(second.json()["data"]) == 2
    assert first.json()["data"][0]["id"] == assignments[0]["id"]
    assert (
        await client.get(f"{BASE}/courses?sort=created_at:asc", headers=auth())
    ).status_code == 422
    assert (
        await client.get(f"{BASE}/assignments?sort=created_at:desc", headers=auth())
    ).status_code == 422


async def test_missing_review_and_artifact_parents(client):
    missing = str(uuid4())
    path = f"{BASE}/submissions/{missing}"
    requests = [
        ("get", path + "/review", {}),
        ("post", path + "/review", {"json": {"grade": 80}}),
        ("patch", path + "/review", {"json": {"grade": 80}}),
        ("get", path + "/artifacts", {}),
        ("post", path + "/artifacts", {"files": {"file": ("a.txt", b"a")}}),
    ]
    for method, url, kwargs in requests:
        response = await client.request(
            method, url, headers=headers("professor", 1), **kwargs
        )
        assert response.status_code == 404


async def test_idempotency_keys_are_user_scoped(client):
    body = {"title": "Python", "professor_id": 1}
    first = await client.post(
        f"{BASE}/courses", json=body, headers=headers("admin", 0, "shared-key")
    )
    second = await client.post(
        f"{BASE}/courses", json=body, headers=headers("admin", 2, "shared-key")
    )
    assert first.status_code == second.status_code == 201
    assert first.json()["id"] != second.json()["id"]
