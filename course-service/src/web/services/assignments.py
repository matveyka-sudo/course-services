from uuid import UUID

from src.core.database import Connection
from src.core.exceptions import not_found
from src.web.repository.assignments import AssignmentRepository
from src.web.schemas.assignments import (
    Assignment,
    AssignmentCreate,
    AssignmentQuery,
    AssignmentUpdate,
)
from src.web.schemas.base import Page
from src.web.schemas.users import Role, User
from src.web.services.base import BaseService


class AssignmentService(BaseService):
    async def create(self, data: AssignmentCreate, user: User, key: str) -> Assignment:
        self.require_role(user, Role.PROFESSOR)

        async def save(connection: Connection) -> Assignment:
            course = await self.course(
                connection, data.course_id, lock=True, status=422
            )
            self.require_professor(user, course)
            return Assignment.model_validate(
                await AssignmentRepository.create(connection, data.model_dump())
            )

        result, _ = await self.create_once(
            user,
            "create_assignment",
            key,
            data.model_dump(mode="json"),
            Assignment,
            action=save,
        )
        return result

    async def list(self, query: AssignmentQuery, user: User) -> Page[Assignment]:
        async with self.database.transaction(readonly=True) as connection:
            rows, total = await AssignmentRepository.page(
                connection, user, query.offset, query.limit
            )
            return self.page(Assignment, rows, total, query.offset, query.limit)

    async def get(self, resource_id: UUID, user: User) -> Assignment:
        async with self.database.transaction(readonly=True) as connection:
            assignment = await self.assignment(connection, resource_id)
            course = await self.course(connection, assignment["course_id"])
            if user.role == Role.STUDENT and user.id not in course["student_ids"]:
                raise not_found("ASSIGNMENT")
            return Assignment.model_validate(assignment)

    async def update(
        self, resource_id: UUID, data: AssignmentUpdate, user: User
    ) -> Assignment:
        self.require_role(user, Role.PROFESSOR)
        async with self.database.transaction() as connection:
            assignment = await self.assignment(connection, resource_id, lock=True)
            self.require_professor(
                user, await self.course(connection, assignment["course_id"])
            )
            updated = await AssignmentRepository.update(
                connection, resource_id, data.model_dump(exclude_unset=True)
            )
            return Assignment.model_validate(updated)

    async def delete(self, resource_id: UUID, user: User) -> None:
        self.require_role(user, Role.PROFESSOR)
        async with self.database.transaction() as connection:
            assignment = await self.assignment(connection, resource_id, lock=True)
            self.require_professor(
                user, await self.course(connection, assignment["course_id"])
            )
            await AssignmentRepository.delete(connection, resource_id)
