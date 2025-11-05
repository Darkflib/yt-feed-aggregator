"""SQLAlchemy async session management."""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings

_engine = None
_sessionmaker = None


def get_engine():
    """Get or create the async database engine."""
    global _engine
    if _engine:
        return _engine
    url = get_settings().database_url
    # Ensure SQLite URLs use async driver
    if url.startswith("sqlite:///"):
        url = url.replace("sqlite:///", "sqlite+aiosqlite:///")
    _engine = create_async_engine(url, future=True)
    return _engine


def get_sessionmaker():
    """Get or create the async session maker."""
    global _sessionmaker
    if _sessionmaker:
        return _sessionmaker
    _sessionmaker = async_sessionmaker(get_engine(), expire_on_commit=False)
    return _sessionmaker


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for FastAPI routes to get an async database session."""
    async with get_sessionmaker()() as session:
        yield session
