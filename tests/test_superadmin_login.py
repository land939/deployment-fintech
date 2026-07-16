"""Tests seed superadmin + login .local."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from config.settings import get_settings
from database import get_db
from database.bootstrap import ensure_superadmin
from database.models import User
from routers import auth


def _scalar_result(value):
    result = MagicMock()
    result.scalars.return_value.first.return_value = value
    return result


@pytest.mark.asyncio
async def test_ensure_superadmin_creates_user(settings):
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_scalar_result(None))
    session.commit = AsyncMock()
    session.add = MagicMock()

    class _CM:
        async def __aenter__(self):
            return session

        async def __aexit__(self, *args):
            return None

    factory = MagicMock(return_value=_CM())

    await ensure_superadmin(factory, settings)
    session.add.assert_called_once()
    user = session.add.call_args[0][0]
    assert isinstance(user, User)
    assert user.email == settings.superadmin_email.lower()
    assert user.role == "superadmin"
    assert user.verify_password(settings.superadmin_password)
    session.commit.assert_awaited()


@pytest.mark.asyncio
async def test_ensure_superadmin_skips_existing(settings, valid_wallet_address):
    existing = User(
        email=settings.superadmin_email.lower(),
        wallet_address=valid_wallet_address,
        role="superadmin",
    )
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_scalar_result(existing))
    session.commit = AsyncMock()
    session.add = MagicMock()

    class _CM:
        async def __aenter__(self):
            return session

        async def __aexit__(self, *args):
            return None

    await ensure_superadmin(MagicMock(return_value=_CM()), settings)
    session.add.assert_not_called()
    session.commit.assert_not_awaited()


def test_login_accepts_local_email_domain(
    settings, mock_db_session, monkeypatch, valid_wallet_address
):
    """Regression: EmailStr rejected @*.local → 422 for SUPERADMIN_EMAIL."""
    get_settings.cache_clear()
    monkeypatch.setattr("config.settings.get_settings", lambda: settings)
    monkeypatch.setattr("config.get_settings", lambda: settings)

    user = User(
        email="admin@test.local",
        wallet_address=valid_wallet_address,
        role="superadmin",
    )
    user.id = 1
    user.set_password("TestPassword123!")
    mock_db_session.execute = AsyncMock(return_value=_scalar_result(user))

    app = FastAPI()
    app.include_router(auth.router)

    async def _override_db():
        yield mock_db_session

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_settings] = lambda: settings

    with TestClient(app) as client:
        resp = client.post(
            "/auth/login",
            json={"email": "admin@test.local", "password": "TestPassword123!"},
        )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["role"] == "superadmin"
    assert body["wallet"] == valid_wallet_address
