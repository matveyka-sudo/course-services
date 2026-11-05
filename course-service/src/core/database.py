import json
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import asyncpg

from src.core.config import DatabaseSettings

type Connection = asyncpg.Connection | asyncpg.pool.PoolConnectionProxy

logger = logging.getLogger(__name__)


class Database:
    def __init__(self, settings: DatabaseSettings) -> None:
        self.settings = settings
        self.pool: asyncpg.Pool | None = None

    @staticmethod
    async def configure_connection(connection: asyncpg.Connection) -> None:
        await connection.set_type_codec(
            "jsonb",
            schema="pg_catalog",
            encoder=json.dumps,
            decoder=json.loads,
        )

    async def connect(self) -> None:
        self.pool = await asyncpg.create_pool(
            self.settings.dsn.get_secret_value(),
            min_size=self.settings.min_pool_size,
            max_size=self.settings.max_pool_size,
            command_timeout=self.settings.command_timeout,
            init=self.configure_connection,
        )
        logger.info("Database pool opened")

    async def close(self) -> None:
        if self.pool is not None:
            await self.pool.close()
            self.pool = None
            logger.info("Database pool closed")

    @asynccontextmanager
    async def transaction(self, *, readonly: bool = False) -> AsyncIterator[Connection]:
        if self.pool is None:
            raise RuntimeError("Database is not connected")
        async with self.pool.acquire() as connection:
            async with connection.transaction(
                isolation="repeatable_read" if readonly else "read_committed",
                readonly=readonly,
            ):
                yield connection
