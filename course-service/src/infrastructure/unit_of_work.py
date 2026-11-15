from contextlib import AbstractAsyncContextManager
from types import TracebackType
from typing import Self

from src.application.ports import (
    LookupRepositoryPort,
    OutboxRepositoryPort,
    SubmissionRepositoryPort,
)
from src.core.database import Connection, Database
from src.infrastructure.outbox_repository import OutboxRepository
from src.infrastructure.submission_adapter import (
    AssignmentAdapter,
    CourseAdapter,
    SubmissionAdapter,
)


class UnitOfWork:
    def __init__(self, database: Database) -> None:
        self.db = database
        self.connection: Connection | None = None
        self.transaction: AbstractAsyncContextManager[Connection] | None = None
        self.assignments: LookupRepositoryPort
        self.courses: LookupRepositoryPort
        self.submissions: SubmissionRepositoryPort
        self.outbox: OutboxRepositoryPort

    async def __aenter__(self) -> Self:
        self.transaction = self.db.transaction()
        self.connection = await self.transaction.__aenter__()
        self.assignments = AssignmentAdapter(self.connection)
        self.courses = CourseAdapter(self.connection)
        self.submissions = SubmissionAdapter(self.connection)
        self.outbox = OutboxRepository(self.connection)
        return self

    async def __aexit__(self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None) -> None:
        try:
            if self.transaction is not None:
                await self.transaction.__aexit__(exc_type, exc, tb)
        finally:
            self.connection = None
            self.transaction = None
            del self.assignments, self.courses, self.submissions, self.outbox
