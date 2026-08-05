from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from core.config import get_settings

engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def init_engine(database_url: str | None = None) -> AsyncEngine:
    global engine, _sessionmaker
    url = database_url or get_settings().database_url
    engine = create_async_engine(url, echo=False, pool_pre_ping=True)
    _sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
    return engine


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    if _sessionmaker is None:
        init_engine()
    assert _sessionmaker is not None
    return _sessionmaker


async def get_session() -> AsyncIterator[AsyncSession]:
    session = get_sessionmaker()()
    try:
        yield session
    finally:
        await session.close()


async def dispose_engine() -> None:
    global engine, _sessionmaker
    if engine is not None:
        await engine.dispose()
        engine = None
        _sessionmaker = None
