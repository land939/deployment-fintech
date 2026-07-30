"""Database initialization and session management."""

from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base

Base = declarative_base()

# Set during app lifespan; required before get_db is used.
_session_factory: async_sessionmaker[AsyncSession] | None = None


def set_session_factory(factory: async_sessionmaker[AsyncSession] | None) -> None:
    """Register the async session factory after init_db() (None clears it)."""
    global _session_factory
    _session_factory = factory


async def init_db(database_url: str) -> tuple:
    """Initialize database engine and session factory."""
    engine_kwargs: dict = {
        "echo": False,
        "pool_pre_ping": True,
    }
    # SQLite (aiosqlite) uses StaticPool — pool_size/max_overflow are invalid there
    if database_url.startswith("sqlite"):
        engine_kwargs["connect_args"] = {"check_same_thread": False}
    else:
        engine_kwargs["pool_size"] = 20
        engine_kwargs["max_overflow"] = 0
        if "asyncpg" in database_url:
            engine_kwargs["connect_args"] = {"server_settings": {"application_name": "gta_fintech"}}

    engine = create_async_engine(database_url, **engine_kwargs)

    factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False, autoflush=False
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Mini-migration : create_all n'ajoute pas de colonne aux tables
    # existantes — on rattrape ici les colonnes ajoutées après coup.
    # Transaction séparée : un ALTER qui échoue (colonne déjà là) ne doit
    # pas invalider la transaction du create_all.
    from sqlalchemy import text

    try:
        async with engine.begin() as conn:
            await conn.execute(text("ALTER TABLE transactions ADD COLUMN block_reasons TEXT"))
    except Exception:
        pass  # colonne déjà présente

    return engine, factory


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency: yield a DB session."""
    if _session_factory is None:
        raise RuntimeError("Database not initialized — call set_session_factory() in lifespan")
    async with _session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# FastAPI-recommended Annotated dependency (avoids B008 on Depends-as-default)
DbSession = Annotated[AsyncSession, Depends(get_db)]
