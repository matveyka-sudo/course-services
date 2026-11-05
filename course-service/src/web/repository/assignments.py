from typing import Any

from src.core.database import Connection
from src.web.repository.base import Repository
from src.web.schemas.users import User


class AssignmentRepository(Repository):
    table = "assignments"
    columns = frozenset({"course_id", "title", "description"})

    @classmethod
    async def page(
        cls, connection: Connection, user: User, offset: int, limit: int
    ) -> tuple[list[dict[str, Any]], int]:
        rows = await connection.fetch(
            """
            SELECT a.*
            FROM assignments a
            JOIN courses c ON c.id = a.course_id
            WHERE $1::text <> 'student' OR $2 = ANY(c.student_ids)
            ORDER BY a.created_at, a.id
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
            FROM assignments a
            JOIN courses c ON c.id = a.course_id
            WHERE $1::text <> 'student' OR $2 = ANY(c.student_ids)
            """,
            user.role.value,
            user.id,
        )
        return [dict(row) for row in rows], total
