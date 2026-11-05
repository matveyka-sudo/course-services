from typing import Any
from uuid import UUID

from src.core.database import Connection
from src.web.repository.base import Repository
from src.web.schemas.users import User


class SubmissionRepository(Repository):
    table = "submissions"
    columns = frozenset(
        {"assignment_id", "student_id", "solution", "attempt", "status"}
    )

    @classmethod
    async def count_attempts(
        cls, connection: Connection, assignment_id: UUID, student_id: int
    ) -> int:
        return int(
            await connection.fetchval(
                """
                SELECT count(*)
                FROM submissions
                WHERE assignment_id = $1 AND student_id = $2
                """,
                assignment_id,
                student_id,
            )
        )

    @classmethod
    async def page(
        cls, connection: Connection, user: User, offset: int, limit: int
    ) -> tuple[list[dict[str, Any]], int]:
        rows = await connection.fetch(
            """
            SELECT s.*
            FROM submissions s
            JOIN assignments a ON a.id = s.assignment_id
            JOIN courses c ON c.id = a.course_id
            WHERE ($1::text = 'student' AND s.student_id = $2)
               OR ($1::text = 'professor' AND c.professor_id = $2)
            ORDER BY s.created_at DESC, s.id
            LIMIT $3 OFFSET $4
            """,
            user.role.value,
            user.id,
            limit,
            offset,
        )
        total = await connection.fetchval(
            """
            SELECT count(*)
            FROM submissions s
            JOIN assignments a ON a.id = s.assignment_id
            JOIN courses c ON c.id = a.course_id
            WHERE ($1::text = 'student' AND s.student_id = $2)
               OR ($1::text = 'professor' AND c.professor_id = $2)
            """,
            user.role.value,
            user.id,
        )
        return [dict(row) for row in rows], total
