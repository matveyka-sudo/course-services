from types import TracebackType
from typing import Any, Protocol, Self
from uuid import UUID


class LookupRepositoryPort(Protocol):
    async def get(self, resource_id: UUID, *, lock: bool = False) -> dict[str, Any] | None: ...


class SubmissionRepositoryPort(Protocol):
    async def count_attempts(self, assignment_id: UUID, student_id: int) -> int: ...

    async def create(self, values: dict[str, Any]) -> dict[str, Any]: ...


class OutboxRepositoryPort(Protocol):
    async def add(self, submission_id: UUID, payload: dict[str, Any]) -> None: ...


class UnitOfWorkPort(Protocol):
    assignments: LookupRepositoryPort
    courses: LookupRepositoryPort
    submissions: SubmissionRepositoryPort
    outbox: OutboxRepositoryPort

    async def __aenter__(self) -> Self: ...

    async def __aexit__(self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None) -> None: ...
