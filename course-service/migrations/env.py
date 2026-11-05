import asyncio

from alembic import context
from sqlalchemy import Connection, make_url, pool
from sqlalchemy.ext.asyncio import create_async_engine

from src.core.config import get_settings

url = make_url(get_settings().database.dsn.get_secret_value()).set(
    drivername="postgresql+asyncpg"
)


def run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=None)
    with context.begin_transaction():
        context.run_migrations()


async def run_online() -> None:
    engine = create_async_engine(url, poolclass=pool.NullPool)
    try:
        async with engine.connect() as connection:
            await connection.run_sync(run_migrations)
    finally:
        await engine.dispose()


if context.is_offline_mode():
    context.configure(
        url=url,
        target_metadata=None,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()
else:
    asyncio.run(run_online())
