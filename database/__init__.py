"""Database initialization and session management."""

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Float, Text, ForeignKey
from sqlalchemy.orm import declarative_base
from datetime import datetime
from config.settings import Settings

Base = declarative_base()


async def init_db(database_url: str) -> tuple:
    """Initialize database engine and session factory."""
    engine = create_async_engine(
        database_url,
        echo=False,
        pool_size=20,
        max_overflow=0,
        pool_pre_ping=True,
        connect_args={"server_settings": {"application_name": "gta_fintech"}} if "asyncpg" in database_url else {},
    )

    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False, autoflush=False
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    return engine, async_session


async def get_session(async_session_factory):
    """Dependency: get database session."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
