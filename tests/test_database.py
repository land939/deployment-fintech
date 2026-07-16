"""Unit tests for database session wiring."""

import pytest
from sqlalchemy import text

from database import get_db, init_db, set_session_factory


@pytest.mark.asyncio
async def test_get_db_requires_factory():
    set_session_factory(None)  # type: ignore[arg-type]
    with pytest.raises(RuntimeError, match="Database not initialized"):
        async for _ in get_db():
            pass


@pytest.mark.asyncio
async def test_init_db_and_get_db_roundtrip(settings):
    engine, factory = await init_db(settings.database_url)
    set_session_factory(factory)
    try:
        sessions = []
        async for session in get_db():
            sessions.append(session)
            result = await session.execute(text("SELECT 1"))
            assert result.scalar() == 1
        assert len(sessions) == 1
    finally:
        set_session_factory(None)  # type: ignore[arg-type]
        await engine.dispose()
