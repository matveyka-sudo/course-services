from typing import Any
from uuid import UUID

from src.core.database import Connection
from src.web.repository.base import Repository


class ReviewRepository(Repository):
    table = "reviews"
    columns = frozenset({"submission_id", "professor_id", "grade", "comment"})

    @classmethod
    async def for_submission(
        cls, connection: Connection, submission_id: UUID
    ) -> dict[str, Any] | None:
        row = await connection.fetchrow(
            "SELECT * FROM reviews WHERE submission_id = $1", submission_id
        )
        return dict(row) if row else None
