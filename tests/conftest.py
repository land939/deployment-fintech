"""Pytest configuration and fixtures."""

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from config import Settings
from config.settings import get_settings
from database import Base, get_db, set_session_factory
from database.models import User
from routers import auth, fraud, superadmin, transactions
from services.auth import get_current_user


@pytest.fixture
def settings():
    """Provide test settings."""
    return Settings(
        environment="test",
        debug=True,
        database_url="sqlite+aiosqlite:///:memory:",
        secret_key="test-secret-key-change-me",
        superadmin_email="admin@test.local",
        superadmin_password="TestPassword123!",
        mail_server=None,
        mail_port=None,
        mail_username=None,
        mail_password=None,
        rpc_url=None,
        enable_blockchain=False,
        enable_email=False,
        enable_ml_fraud_detection=True,
        api_host="127.0.0.1",
    )


@pytest.fixture
def mock_fraud_data():
    """Vecteur minimal des 11 features FTK."""
    return {
        "amount": 100.0,
        "hour": 14.0,
        "day_of_week": 2.0,
        "account_age_days": 30.0,
        "tx_count_1h": 1.0,
        "tx_count_24h": 3.0,
        "amount_avg_ratio": 1.0,
        "seconds_since_last_tx": 3600.0,
        "is_new_receiver": 0.0,
        "unique_receivers_24h": 2.0,
        "past_fraud_count": 0.0,
    }


@pytest.fixture
def valid_wallet_address():
    """Provide a valid Ethereum wallet address."""
    return "0x742d35Cc6634C0532925a3b844Bc9e7595f42bE0"


@pytest.fixture
def valid_email():
    """Provide a valid email address."""
    return "test@example.com"


@pytest.fixture
async def db_engine(settings):
    """In-memory async SQLite engine + schema."""
    engine = create_async_engine(settings.database_url, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def session_factory(db_engine):
    """Session factory bound to the in-memory engine."""
    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    set_session_factory(factory)
    yield factory
    set_session_factory(None)  # type: ignore[arg-type]


@pytest.fixture
def current_user(valid_wallet_address):
    """Utilisateur authentifié par défaut pour les tests de routes protégées."""
    user = User(
        email="user@example.com",
        wallet_address=valid_wallet_address,
        role="user",
        is_active=True,
    )
    user.id = 42
    return user


@pytest.fixture
def current_superadmin():
    """Super administrateur authentifié pour les tests de routes /superadmin/api/*."""
    user = User(
        email="admin@test.local",
        wallet_address="0x1111111111111111111111111111111111111111",
        role="superadmin",
        is_active=True,
    )
    user.id = 1
    return user


@pytest.fixture
def mock_db_session():
    """Async DB session mock for route tests that don't need real SQL."""
    session = AsyncMock(spec=AsyncSession)
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.add = MagicMock()
    session.get = AsyncMock(return_value=None)
    return session


@pytest.fixture
def api_app(settings, mock_db_session, current_user, monkeypatch):
    """Minimal FastAPI app with routers and dependency overrides.

    get_current_user est surchargé vers un utilisateur "user" authentifié par
    défaut, afin que les tests existants (validation de payload, etc.) ne
    soient pas bloqués par la garde JWT. Les tests qui veulent vérifier le
    401/403 construisent leur propre app sans cette surcharge (voir
    test_api.py::test_*_requires_auth), ou la remplacent par current_superadmin.
    """
    get_settings.cache_clear()
    monkeypatch.setattr("config.settings.get_settings", lambda: settings)
    monkeypatch.setattr("config.get_settings", lambda: settings)

    app = FastAPI()
    app.include_router(auth.router)
    app.include_router(fraud.router)
    app.include_router(transactions.router)
    app.include_router(superadmin.router)

    async def _override_db() -> AsyncGenerator[AsyncSession, None]:
        yield mock_db_session

    async def _override_settings():
        return settings

    app.dependency_overrides[get_db] = _override_db
    from config.settings import get_settings as _gs

    app.dependency_overrides[_gs] = _override_settings
    app.dependency_overrides[get_current_user] = lambda: current_user
    return app


@pytest.fixture
def client(api_app):
    """Sync TestClient for API route tests."""
    with TestClient(api_app) as c:
        yield c
