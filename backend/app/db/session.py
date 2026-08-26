import os
from collections.abc import AsyncIterator
from functools import lru_cache

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


def create_session_factory(database_url: str | None = None) -> async_sessionmaker[AsyncSession]:
    """Create an async session factory without opening a connection eagerly."""
    url = database_url or os.environ["DATABASE_URL"]
    engine = create_async_engine(url, pool_pre_ping=True)
    return async_sessionmaker(engine, expire_on_commit=False)


@lru_cache
def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return the process-wide session factory configured from the environment."""
    return create_session_factory()


async def get_db_session() -> AsyncIterator[AsyncSession]:
    """Provide one transaction boundary per HTTP request."""
    session_factory = get_session_factory()
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
