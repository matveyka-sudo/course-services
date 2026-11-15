from typing import Any
from uuid import UUID

from src.core.database import Connection
from src.web.repository.assignments import AssignmentRepository
from src.web.repository.courses import CourseRepository
from src.web.repository.submissions import SubmissionRepository


class SubmissionAdapter:
    def __init__(self, connection: Connection):
        self.connection = connection

    async def count_attempts(self, assignment_id: UUID, student_id: int) -> int:
        return await SubmissionRepository.count_attempts(self.connection, assignment_id, student_id)

    async def create(self, values: dict[str, Any]) -> dict[str, Any]:
        return await SubmissionRepository.create(self.connection, values)


class AssignmentAdapter:
    def __init__(self, connection: Connection):
        self.connection = connection

    async def get(self, resource_id: UUID, *, lock: bool = False) -> dict[str, Any] | None:
        return await AssignmentRepository.get(self.connection, resource_id, lock=lock)


class CourseAdapter:
    def __init__(self, connection: Connection):
        self.connection = connection

    async def get(self, resource_id: UUID, *, lock: bool = False) -> dict[str, Any] | None:
        return await CourseRepository.get(self.connection, resource_id, lock=lock)
