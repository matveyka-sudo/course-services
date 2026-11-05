from typing import Any

from src.core.database import Connection
from src.web.repository.base import Repository


class CourseRepository(Repository):
    table = "courses"
    columns = frozenset(
        {"title", "description", "professor_id", "student_ids", "status"}
    )

    @classmethod
    async def page(
        cls, connection: Connection, offset: int, limit: int
    ) -> tuple[list[dict[str, Any]], int]:
        rows = await connection.fetch(
            """
            SELECT *
            FROM courses
            ORDER BY created_at DESC, id
            LIMIT $1 OFFSET $2
            """,
            limit,
            offset,
        )
        total = await connection.fetchval("SELECT count(*) FROM courses")
        return [dict(row) for row in rows], total
