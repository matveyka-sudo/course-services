import hashlib
from typing import Any

from src.core.database import Connection


class IdempotencyRepository:
    @classmethod
    async def lock(cls, connection: Connection, scope: str) -> None:
        lock_id = int.from_bytes(
            hashlib.sha256(scope.encode()).digest()[:8], signed=True
        )
        await connection.execute("SELECT pg_advisory_xact_lock($1)", lock_id)

    @classmethod
    async def get(
        cls, connection: Connection, user_id: int, operation: str, key: str
    ) -> dict[str, Any] | None:
        row = await connection.fetchrow(
            """
            SELECT fingerprint, response
            FROM idempotency_keys
            WHERE user_id = $1 AND operation = $2 AND key = $3
            """,
            user_id,
            operation,
            key,
        )
        return dict(row) if row else None

    @classmethod
    async def save(
        cls,
        connection: Connection,
        user_id: int,
        operation: str,
        key: str,
        fingerprint: str,
        *,
        response: dict[str, Any],
    ) -> None:
        await connection.execute(
            """
            INSERT INTO idempotency_keys (
                user_id, operation, key, fingerprint, response
            )
            VALUES ($1, $2, $3, $4, $5)
            """,
            user_id,
            operation,
            key,
            fingerprint,
            response,
        )
