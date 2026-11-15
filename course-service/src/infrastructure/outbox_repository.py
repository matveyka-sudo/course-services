from typing import Any
from uuid import UUID

from src.core.database import Connection


class OutboxRepository:
    def __init__(self, connection: Connection):
        self.connection = connection

    async def add(self, submission_id: UUID, payload: dict[str, Any]) -> None:
        await self.connection.execute(
            "INSERT INTO outbox_events (submission_id, payload) VALUES ($1, $2)",
            submission_id, payload,
        )

    async def claim(self, submission_id: UUID | None = None) -> dict[str, Any] | None:
        row = await self.connection.fetchrow(
            """
            SELECT submission_id, payload
            FROM outbox_events
            WHERE processed_at IS NULL AND available_at <= clock_timestamp()
              AND ($1::uuid IS NULL OR submission_id = $1)
            ORDER BY available_at, submission_id
            LIMIT 1
            FOR UPDATE SKIP LOCKED
            """,
            submission_id,
        )
        return dict(row) if row else None

    async def finish(self, submission_id: UUID, success: bool, retry_delay: float) -> None:
        await self.connection.execute(
            """
            UPDATE outbox_events
            SET attempts = attempts + 1,
                processed_at = CASE WHEN $2 THEN clock_timestamp() ELSE NULL END,
                available_at = clock_timestamp() + $3 * interval '1 second'
            WHERE submission_id = $1
            """,
            submission_id, success, retry_delay,
        )
