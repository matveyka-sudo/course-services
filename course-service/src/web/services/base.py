import hashlib
import json
from collections.abc import Awaitable, Callable
from typing import Any
from uuid import UUID

from pydantic import BaseModel

from src.core.database import Connection, Database
from src.core.exceptions import ServiceError, access_denied, not_found
from src.web.repository.assignments import AssignmentRepository
from src.web.repository.courses import CourseRepository
from src.web.repository.idempotency import IdempotencyRepository
from src.web.repository.submissions import SubmissionRepository
from src.web.schemas.base import Page, Pagination
from src.web.schemas.users import Role, User


class BaseService:
    def __init__(self, database: Database) -> None:
        self.database = database

    @staticmethod
    def require_role(user: User, *roles: Role) -> None:
        if user.role not in roles:
            raise access_denied()

    @staticmethod
    def require_professor(user: User, course: dict[str, Any]) -> None:
        if user.role != Role.PROFESSOR or user.id != course["professor_id"]:
            raise access_denied()

    @staticmethod
    async def course(
        connection: Connection,
        resource_id: UUID,
        *,
        lock: bool = False,
        status: int = 404,
    ) -> dict[str, Any]:
        course = await CourseRepository.get(connection, resource_id, lock=lock)
        if course is None:
            raise not_found("COURSE", status)
        return course

    @staticmethod
    async def assignment(
        connection: Connection,
        resource_id: UUID,
        *,
        lock: bool = False,
        status: int = 404,
    ) -> dict[str, Any]:
        assignment = await AssignmentRepository.get(connection, resource_id, lock=lock)
        if assignment is None:
            raise not_found("ASSIGNMENT", status)
        return assignment

    @classmethod
    async def submission(
        cls,
        connection: Connection,
        user: User,
        resource_id: UUID,
        *,
        lock: bool = False,
        missing: str = "SUBMISSION",
    ) -> dict[str, Any]:
        cls.require_role(user, Role.STUDENT, Role.PROFESSOR)
        submission = await SubmissionRepository.get(connection, resource_id, lock=lock)
        if submission is None:
            raise not_found(missing)
        if user.role == Role.STUDENT:
            if submission["student_id"] != user.id:
                raise access_denied()
        else:
            assignment = await cls.assignment(connection, submission["assignment_id"])
            course = await cls.course(connection, assignment["course_id"])
            cls.require_professor(user, course)
        return submission

    @staticmethod
    def page[T: BaseModel](
        schema: type[T], rows: list[dict[str, Any]], total: int, offset: int, limit: int
    ) -> Page[T]:
        return Page[T](
            data=[schema.model_validate(row) for row in rows],
            pagination=Pagination.model_validate(
                {"offset": offset, "limit": limit, "total": total}
            ),
        )

    async def create_once[T: BaseModel](
        self,
        user: User,
        operation: str,
        key: str,
        payload: dict[str, Any],
        schema: type[T],
        *,
        action: Callable[[Connection], Awaitable[T]],
    ) -> tuple[T, bool]:
        fingerprint = hashlib.sha256(
            json.dumps(
                payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
            ).encode()
        ).hexdigest()
        async with self.database.transaction() as connection:
            scope = json.dumps([user.id, operation, key])
            await IdempotencyRepository.lock(connection, scope)
            previous = await IdempotencyRepository.get(
                connection, user.id, operation, key
            )
            if previous:
                if previous["fingerprint"] != fingerprint:
                    raise ServiceError(
                        409,
                        "IDEMPOTENCY_KEY_CONFLICT",
                        "Idempotency-Key уже использован с другим содержимым",
                    )
                return schema.model_validate(previous["response"]), False
            result = await action(connection)
            await IdempotencyRepository.save(
                connection,
                user.id,
                operation,
                key,
                fingerprint,
                response=result.model_dump(mode="json"),
            )
            return result, True
