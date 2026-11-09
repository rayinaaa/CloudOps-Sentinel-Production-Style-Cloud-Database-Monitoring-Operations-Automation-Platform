"""SQLAlchemy 2.0 Async Engine and Session Factory.

Provides resilient connection pooling, transactional session lifecycle management,
and fast connectivity health checks for CloudOps Sentinel.
"""

from typing import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings
from app.core.logging import logger


class Base(DeclarativeBase):
    """Base declarative class for all SQLAlchemy entities."""

    pass


# Asynchronous database engine configured with production pool sizing
engine = create_async_engine(
    settings.async_database_url,
    echo=settings.DEBUG,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_timeout=settings.DB_POOL_TIMEOUT,
    pool_recycle=settings.DB_POOL_RECYCLE,
    pool_pre_ping=True,  # Proactively test connection validity before checkout
)

# Async session factory
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
    class_=AsyncSession,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency injection helper providing a scoped database transaction session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception as ex:
            await session.rollback()
            logger.error("Database session rolled back due to error", error=str(ex))
            raise
        finally:
            await session.close()


async def check_database_connection() -> bool:
    """Executes a lightweight query to verify connectivity to the Sentinel database."""
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT 1"))
            return result.scalar() == 1
    except Exception as exc:
        logger.warning("Database connectivity check failed", error=str(exc))
        return False
