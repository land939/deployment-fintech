"""API route unit tests (dependency-overridden FastAPI app)."""

from unittest.mock import AsyncMock, MagicMock

from database.models import User


def _scalar_result(value):
    result = MagicMock()
    result.scalars.return_value.first.return_value = value
    result.scalars.return_value.all.return_value = []
    return result


def test_register_validation_rejects_bad_wallet(client):
    resp = client.post(
        "/auth/register",
        json={
            "email": "user@example.com",
            "password": "Password123",
            "wallet_address": "bad",
        },
    )
    assert resp.status_code == 422


def test_register_success(client, mock_db_session, valid_wallet_address):
    mock_db_session.execute = AsyncMock(return_value=_scalar_result(None))

    resp = client.post(
        "/auth/register",
        json={
            "email": "newuser@example.com",
            "password": "Password123",
            "wallet_address": valid_wallet_address,
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == "newuser@example.com"
    assert "user_id" in body
    mock_db_session.add.assert_called()
    mock_db_session.commit.assert_awaited()


def test_register_conflict_existing_email(client, mock_db_session, valid_wallet_address):
    existing = User(email="newuser@example.com", wallet_address=valid_wallet_address)
    existing.id = 1
    mock_db_session.execute = AsyncMock(return_value=_scalar_result(existing))

    resp = client.post(
        "/auth/register",
        json={
            "email": "newuser@example.com",
            "password": "Password123",
            "wallet_address": valid_wallet_address,
        },
    )
    assert resp.status_code == 409


def test_login_invalid_credentials(client, mock_db_session):
    mock_db_session.execute = AsyncMock(return_value=_scalar_result(None))
    resp = client.post(
        "/auth/login",
        json={"email": "nobody@example.com", "password": "Password123"},
    )
    assert resp.status_code == 401


def test_login_success(client, mock_db_session, valid_wallet_address):
    user = User(email="user@example.com", wallet_address=valid_wallet_address)
    user.id = 7
    user.role = "user"
    user.set_password("Password123")
    mock_db_session.execute = AsyncMock(return_value=_scalar_result(user))

    resp = client.post(
        "/auth/login",
        json={"email": "user@example.com", "password": "Password123"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["access_token"]
    assert body["email"] == "user@example.com"
    assert body["user_id"] == 7
    assert body["wallet"] == valid_wallet_address
    assert body["role"] == "user"


def test_fraud_disabled_returns_503(settings, mock_db_session, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from config.settings import get_settings
    from database import get_db
    from routers import fraud

    disabled = settings.model_copy(update={"enable_ml_fraud_detection": False})
    get_settings.cache_clear()

    app = FastAPI()
    app.include_router(fraud.router)

    async def _override_db():
        yield mock_db_session

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_settings] = lambda: disabled

    with TestClient(app) as client:
        resp = client.post("/fraud/check", json={"amount": 10.0})
    assert resp.status_code == 503


def test_transaction_rejects_invalid_receiver(client):
    resp = client.post(
        "/transactions/send",
        json={"receiver": "nope", "amount": 1.0},
    )
    assert resp.status_code == 422
