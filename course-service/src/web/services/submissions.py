from uuid import UUID

from fastapi import BackgroundTasks

from src.application.create_submission import CreateSubmissionUseCase
from src.core.database import Connection, Database
from src.infrastructure.outbox_worker import OutboxWorker
from src.infrastructure.unit_of_work import UnitOfWork
from src.web.repository.submissions import SubmissionRepository
from src.web.schemas.base import Page
from src.web.schemas.submissions import Submission, SubmissionCreate, SubmissionQuery
from src.web.schemas.users import Role, User
from src.web.services.base import BaseService
from src.web.services.checker import CheckerService


class SubmissionService(BaseService):
    def __init__(self, database: Database, checker: CheckerService) -> None:
        super().__init__(database)
        self.checker = checker

    async def create(
        self, data: SubmissionCreate, user: User, key: str, background: BackgroundTasks
    ) -> Submission:
        self.require_role(user, Role.STUDENT)

        async with UnitOfWork(self.database) as uow:
            use_case = CreateSubmissionUseCase(uow)

            async def save(connection: Connection) -> Submission:
                return await use_case.execute(data, user)

            result, created = await self.create_once(
                user, "create_submission", key, data.model_dump(mode="json"), Submission,
                action=save, connection=uow.connection,
            )
        if created and self.checker.settings.url:
            worker = OutboxWorker(self.database, self.checker)
            background.add_task(worker.process_once, result.id)
        return result

    async def list(self, query: SubmissionQuery, user: User) -> Page[Submission]:
        self.require_role(user, Role.STUDENT, Role.PROFESSOR)
        async with self.database.transaction(readonly=True) as connection:
            rows, total = await SubmissionRepository.page(
                connection, user, query.offset, query.limit
            )
            return self.page(Submission, rows, total, query.offset, query.limit)

    async def get(self, resource_id: UUID, user: User) -> Submission:
        async with self.database.transaction(readonly=True) as connection:
            return Submission.model_validate(
                await self.submission(connection, user, resource_id)
            )
