from uuid import UUID

from src.core.database import Connection
from src.web.repository.courses import CourseRepository
from src.web.schemas.base import Page
from src.web.schemas.courses import Course, CourseCreate, CourseQuery, CourseUpdate
from src.web.schemas.users import Role, User
from src.web.services.base import BaseService


class CourseService(BaseService):
    async def create(self, data: CourseCreate, user: User, key: str) -> Course:
        self.require_role(user, Role.ADMIN)

        async def save(connection: Connection) -> Course:
            values = data.model_dump()
            values["student_ids"] = sorted(set(values["student_ids"]))
            return Course.model_validate(
                await CourseRepository.create(connection, values)
            )

        result, _ = await self.create_once(
            user,
            "create_course",
            key,
            data.model_dump(mode="json"),
            Course,
            action=save,
        )
        return result

    async def list(self, query: CourseQuery) -> Page[Course]:
        async with self.database.transaction(readonly=True) as connection:
            rows, total = await CourseRepository.page(
                connection, query.offset, query.limit
            )
            return self.page(Course, rows, total, query.offset, query.limit)

    async def get(self, resource_id: UUID) -> Course:
        async with self.database.transaction(readonly=True) as connection:
            return Course.model_validate(await self.course(connection, resource_id))

    async def update(self, resource_id: UUID, data: CourseUpdate, user: User) -> Course:
        self.require_role(user, Role.PROFESSOR)
        async with self.database.transaction() as connection:
            course = await self.course(connection, resource_id, lock=True)
            self.require_professor(user, course)
            updated = await CourseRepository.update(
                connection, resource_id, data.model_dump(exclude_unset=True)
            )
            return Course.model_validate(updated)

    async def delete(self, resource_id: UUID, user: User) -> None:
        self.require_role(user, Role.ADMIN)
        async with self.database.transaction() as connection:
            await self.course(connection, resource_id, lock=True)
            await CourseRepository.delete(connection, resource_id)
