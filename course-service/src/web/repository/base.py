from typing import Any, ClassVar
from uuid import UUID, uuid4

from src.core.database import Connection


class Repository:
    table: ClassVar[str]
    columns: ClassVar[frozenset[str]]

    @classmethod
    async def get(
        cls, connection: Connection, resource_id: UUID, *, lock: bool = False
    ) -> dict[str, Any] | None:
        suffix = " FOR UPDATE" if lock else ""
        row = await connection.fetchrow(
            f"SELECT * FROM {cls.table} WHERE id = $1{suffix}", resource_id
        )
        return dict(row) if row else None

    @classmethod
    async def create(
        cls, connection: Connection, values: dict[str, Any]
    ) -> dict[str, Any]:
        if not values.keys() <= cls.columns:
            raise ValueError("Unknown repository columns")
        data = {"id": uuid4(), **values}
        columns = ", ".join(data)
        placeholders = ", ".join(f"${index}" for index in range(1, len(data) + 1))
        row = await connection.fetchrow(
            f"INSERT INTO {cls.table} ({columns}) VALUES ({placeholders}) RETURNING *",
            *data.values(),
        )
        if row is None:
            raise RuntimeError("Insert did not return a row")
        return dict(row)

    @classmethod
    async def update(
        cls, connection: Connection, resource_id: UUID, values: dict[str, Any]
    ) -> dict[str, Any] | None:
        if not values.keys() <= cls.columns:
            raise ValueError("Unknown repository columns")
        if not values:
            return await cls.get(connection, resource_id)
        assignments = ", ".join(
            f"{key} = ${index}" for index, key in enumerate(values, 2)
        )
        row = await connection.fetchrow(
            f"""
            UPDATE {cls.table}
            SET {assignments}, updated_at = clock_timestamp()
            WHERE id = $1
            RETURNING *
            """,
            resource_id,
            *values.values(),
        )
        return dict(row) if row else None

    @classmethod
    async def delete(cls, connection: Connection, resource_id: UUID) -> None:
        await connection.execute(f"DELETE FROM {cls.table} WHERE id = $1", resource_id)
