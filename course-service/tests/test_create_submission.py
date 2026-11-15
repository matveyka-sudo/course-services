from copy import deepcopy
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from src.application.create_submission import CreateSubmissionUseCase
from src.core.exceptions import ServiceError
from src.web.schemas.submissions import SubmissionCreate
from src.web.schemas.users import User


class FakeLookup:
    def __init__(self, row):
        self.row = row
        self.locked = False

    async def get(self, resource_id, *, lock=False):
        self.locked = lock
        return self.row


class FakeSubmissions:
    def __init__(self):
        self.rows = []

    async def count_attempts(self, assignment_id, student_id):
        return len(self.rows)

    async def create(self, values):
        now = datetime.now(UTC)
        row = {**values, "id": uuid4(), "status": "SUBMITTED", "created_at": now, "updated_at": now}
        self.rows.append(row)
        return row


class FakeOutbox:
    def __init__(self):
        self.events = []
        self.fail = False

    async def add(self, submission_id, payload):
        self.events.append((submission_id, payload))
        if self.fail:
            raise RuntimeError("Outbox unavailable")


class FakeUnitOfWork:
    def __init__(self):
        self.assignments = FakeLookup({"course_id": uuid4()})
        self.courses = FakeLookup({"student_ids": [10]})
        self.submissions = FakeSubmissions()
        self.outbox = FakeOutbox()
        self.committed = False

    async def __aenter__(self):
        self.saved = deepcopy((self.submissions.rows, self.outbox.events))
        return self

    async def __aexit__(self, exc_type, exc, tb):
        self.committed = exc_type is None
        if exc_type is not None:
            self.submissions.rows, self.outbox.events = self.saved


@pytest.fixture
def scenario():
    return FakeUnitOfWork(), SubmissionCreate(assignment_id=uuid4(), solution="print(1)"), User(id=10, role="student")


async def test_create_submission(scenario):
    uow, data, user = scenario
    async with uow:
        submission = await CreateSubmissionUseCase(uow).execute(data, user)
    assert uow.committed
    assert uow.assignments.locked
    assert submission.student_id == 10
    assert submission.attempt == 1
    assert submission.solution == data.solution
    assert uow.outbox.events == [(submission.id, submission.model_dump(mode="json"))]


@pytest.mark.parametrize("attempts,allowed", [(9, True), (10, False)])
async def test_attempt_limit(scenario, attempts, allowed):
    uow, data, user = scenario
    uow.submissions.rows = [{} for _ in range(attempts)]
    if allowed:
        async with uow:
            result = await CreateSubmissionUseCase(uow).execute(data, user)
        assert result.attempt == 10
        assert len(uow.outbox.events) == 1
    else:
        with pytest.raises(ServiceError) as error:
            async with uow:
                await CreateSubmissionUseCase(uow).execute(data, user)
        assert error.value.status == 422
        assert error.value.code == "SUBMISSION_LIMIT_REACHED"
        assert len(uow.submissions.rows) == 10
        assert not uow.outbox.events


@pytest.mark.parametrize("role", ["admin", "professor"])
async def test_student_role_required(scenario, role):
    uow, data, user = scenario
    user = User(id=user.id, role=role)
    with pytest.raises(ServiceError) as error:
        async with uow:
            await CreateSubmissionUseCase(uow).execute(data, user)
    assert error.value.status == 403
    assert not uow.submissions.rows


@pytest.mark.parametrize("missing,code,status", [("assignments", "ASSIGNMENT_NOT_FOUND", 422), ("courses", "COURSE_NOT_FOUND", 404)])
async def test_missing_related_data(scenario, missing, code, status):
    uow, data, user = scenario
    getattr(uow, missing).row = None
    with pytest.raises(ServiceError) as error:
        async with uow:
            await CreateSubmissionUseCase(uow).execute(data, user)
    assert (error.value.code, error.value.status) == (code, status)
    assert not uow.submissions.rows


async def test_student_must_belong_to_course(scenario):
    uow, data, user = scenario
    uow.courses.row["student_ids"] = [11]
    with pytest.raises(ServiceError) as error:
        async with uow:
            await CreateSubmissionUseCase(uow).execute(data, user)
    assert error.value.status == 403
    assert not uow.submissions.rows


async def test_outbox_error_reaches_transaction_boundary(scenario):
    uow, data, user = scenario
    uow.outbox.fail = True
    with pytest.raises(RuntimeError, match="Outbox unavailable"):
        async with uow:
            await CreateSubmissionUseCase(uow).execute(data, user)
    assert not uow.committed
    assert not uow.submissions.rows
    assert not uow.outbox.events
