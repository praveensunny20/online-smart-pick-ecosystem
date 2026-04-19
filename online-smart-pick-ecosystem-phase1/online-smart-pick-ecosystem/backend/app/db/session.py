"""
Database session and engine setup.

Uses async SQLAlchemy with asyncpg driver for non-blocking Postgres access.
The async_session_maker is used as a dependency in FastAPI routes.
"""
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings


class Base(DeclarativeBase):
    """
    Base class all SQLAlchemy ORM models inherit from.
    DeclarativeBase is the SQLAlchemy 2.0 style.
    """
    pass


# Create the async engine.
# pool_pre_ping=True tests connections before use (handles dropped connections).
# echo=False in prod; set to True when debugging SQL.
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

# Session factory — creates new AsyncSession instances on demand
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,  # Keep objects usable after commit
    autoflush=False,
    autocommit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that yields an async database session.

    Usage in route:
        async def my_route(db: AsyncSession = Depends(get_db)):
            ...

    The session is automatically closed when the request ends.
    If an exception is raised, the session is rolled back.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
