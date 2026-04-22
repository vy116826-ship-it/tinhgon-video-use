"""SQLAlchemy database engine and session management.

The async engine is created lazily to avoid import-time errors
in Celery workers which use sync DB access.
"""
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


# Lazy-initialized async engine (only created when actually needed by FastAPI)
_engine = None
_async_session = None


def _get_engine():
    global _engine
    if _engine is None:
        from sqlalchemy.ext.asyncio import create_async_engine
        from app.core.config import DATABASE_URL
        _engine = create_async_engine(DATABASE_URL, echo=False, future=True)
    return _engine


def _get_session_factory():
    global _async_session
    if _async_session is None:
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
        _async_session = async_sessionmaker(
            _get_engine(), class_=AsyncSession, expire_on_commit=False
        )
    return _async_session


async def get_db():
    """FastAPI dependency — yields an async DB session."""
    session_factory = _get_session_factory()
    async with session_factory() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    """Create all tables on startup."""
    engine = _get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
