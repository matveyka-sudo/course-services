from uuid import UUID

from fastapi import BackgroundTasks

from src.core.database import Connection, Database
from src.core.exceptions import ServiceError, access_denied
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

        async def save(connection: Connection) -> Submission:
            assignment = await self.assignment(
                connection, data.assignment_id, lock=True, status=422
            )
            course = await self.course(connection, assignment["course_id"])
            if user.id not in course["student_ids"]:
                raise access_denied()
            attempts = await SubmissionRepository.count_attempts(
                connection, data.assignment_id, user.id
            )
            if attempts >= 10:
                raise ServiceError(
                    422,
                    "SUBMISSION_LIMIT_REACHED",
                    "Допускается не более 10 попыток на задание",
                )
            values = {
                **data.model_dump(),
                "student_id": user.id,
                "attempt": attempts + 1,
            }
            return Submission.model_validate(
                await SubmissionRepository.create(connection, values)
            )

        result, created = await self.create_once(
            user,
            "create_submission",
            key,
            data.model_dump(mode="json"),
            Submission,
            action=save,
        )
        if created and self.checker.settings.url:
            background.add_task(self.checker.check, result)
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
