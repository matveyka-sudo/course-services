from typing import Any
from uuid import UUID

from src.core.database import Connection
from src.web.repository.base import Repository


class ArtifactRepository(Repository):
    table = "artifacts"
    columns = frozenset(
        {"submission_id", "filename", "content_type", "size", "sha256", "content"}
    )

    @classmethod
    async def for_submission(
        cls, connection: Connection, submission_id: UUID
    ) -> list[dict[str, Any]]:
        rows = await connection.fetch(
            """
            SELECT id, submission_id, filename, content_type, size, sha256,
                   created_at, updated_at
            FROM artifacts
            WHERE submission_id = $1
            ORDER BY created_at, id
            """,
            submission_id,
        )
        return [dict(row) for row in rows]
