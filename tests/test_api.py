"""API route unit tests (dependency-overridden FastAPI app)."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from database.models import Transaction, User


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


# ════════════════════════════════════════════════════════════════
# Garde d'authentification / autorisation
#
# Régression couverte : avant le rebranchement JWT, /transactions/send
# attribuait chaque transaction au premier utilisateur de la base (sans
# vérifier la moindre authentification) et /superadmin/api/* était
# accessible sans identifiant. Ces tests prouvent que ce n'est plus le cas.
# ════════════════════════════════════════════════════════════════


def _bare_app(router, db_session, settings):
    """App minimale avec un seul routeur, SANS surcharge de get_current_user."""
    from config.settings import get_settings
    from database import get_db

    app = FastAPI()
    app.include_router(router)

    async def _override_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_settings] = lambda: settings
    return app


def test_transaction_send_requires_auth(mock_db_session, settings):
    from routers import transactions

    with TestClient(_bare_app(transactions.router, mock_db_session, settings)) as c:
        resp = c.post(
            "/transactions/send",
            json={"receiver": "0x1234500000000000000000000000000000067890", "amount": 10.0},
        )
    assert resp.status_code == 401


def test_transaction_send_uses_authenticated_sender(
    client, mock_db_session, current_user, monkeypatch
):
    """Le sender de la transaction doit être le porteur du JWT, pas un utilisateur arbitraire."""

    class _FakeMLService:
        def predict_fraud(self, features):
            return {"risk_score": 5, "risk_level": "LOW", "blocked": False}

    monkeypatch.setattr("routers.transactions.get_fraud_service", lambda: _FakeMLService())
    monkeypatch.setattr("routers.transactions.build_fraud_features", AsyncMock(return_value={}))

    resp = client.post(
        "/transactions/send",
        json={"receiver": "0x1234500000000000000000000000000000067890", "amount": 50.0},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["sender"] == current_user.wallet_address

    added = mock_db_session.add.call_args[0][0]
    assert isinstance(added, Transaction)
    assert added.sender == current_user.wallet_address
    assert added.user_id == current_user.id


def test_superadmin_requires_auth(mock_db_session, settings):
    from routers import superadmin

    with TestClient(_bare_app(superadmin.router, mock_db_session, settings)) as c:
        resp = c.get("/superadmin/api/users")
    assert resp.status_code == 401


def test_superadmin_rejects_non_admin_role(client):
    """current_user (role="user") ne doit pas pouvoir accéder à la console admin."""
    resp = client.get("/superadmin/api/users")
    assert resp.status_code == 403


def test_superadmin_allows_admin(api_app, mock_db_session, current_superadmin):
    from services.auth import get_current_user

    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    mock_db_session.execute = AsyncMock(return_value=result)

    api_app.dependency_overrides[get_current_user] = lambda: current_superadmin
    with TestClient(api_app) as c:
        resp = c.get("/superadmin/api/users")
    assert resp.status_code == 200
    assert resp.json() == {"users": []}


@pytest.mark.asyncio
async def test_transactions_recent_scoped_to_current_user(session_factory, settings):
    """Bout-en-bout (vraie base SQLite en mémoire) : Alice ne voit pas les transactions de Bob."""
    from config.settings import get_settings
    from database import get_db
    from routers import transactions
    from services.auth import get_current_user

    alice_wallet = "0xA11CE000000000000000000000000000000000AA"
    bob_wallet = "0xB0B00000000000000000000000000000000000BB"

    async with session_factory() as db:
        alice = User(email="alice@example.com", wallet_address=alice_wallet, role="user")
        bob = User(email="bob@example.com", wallet_address=bob_wallet, role="user")
        db.add_all([alice, bob])
        await db.commit()
        await db.refresh(alice)
        await db.refresh(bob)

        db.add_all(
            [
                Transaction(
                    id="tx-alice",
                    user_id=alice.id,
                    sender=alice_wallet,
                    receiver="0x1234500000000000000000000000000000067890",
                    amount=10.0,
                ),
                Transaction(
                    id="tx-bob",
                    user_id=bob.id,
                    sender=bob_wallet,
                    receiver="0x1234500000000000000000000000000000067890",
                    amount=20.0,
                ),
            ]
        )
        await db.commit()
        alice_id = alice.id

    app = FastAPI()
    app.include_router(transactions.router)

    async def _override_db():
        async with session_factory() as s:
            yield s

    async def _override_user():
        return User(
            email="alice@example.com", wallet_address=alice_wallet, role="user", id=alice_id
        )

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_current_user] = _override_user

    with TestClient(app) as c:
        resp = c.get("/transactions/recent")

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["transactions"][0]["id"] == "tx-alice"


def test_forgot_password_generic_response_without_smtp(
    client, mock_db_session, valid_wallet_address
):
    """Sans SMTP configuré (tests), le flux répond quand même sans erreur
    et ne révèle pas si l'email existe."""
    user = User(email="user@example.com", wallet_address=valid_wallet_address)
    user.id = 7
    mock_db_session.execute = AsyncMock(return_value=_scalar_result(user))

    resp = client.post("/auth/forgot-password", json={"email": "user@example.com"})
    assert resp.status_code == 200
    assert "reset link" in resp.json()["message"]
    mock_db_session.add.assert_called()  # token de reset créé


def test_blocked_transaction_creates_alert_with_reasons(
    client, mock_db_session, current_user, monkeypatch
):
    """Une transaction bloquée enregistre les raisons et crée une FraudAlert."""
    from database.models import BlockchainAuditBlock, FraudAlert

    # append_audit_block lit le dernier bloc de la chaîne : aucun → GENESIS
    mock_db_session.execute = AsyncMock(return_value=_scalar_result(None))

    class _FakeMLService:
        def predict_fraud(self, features):
            return {
                "risk_score": 92,
                "risk_level": "CRITICAL",
                "blocked": True,
                "reasons": ["Montant aberrant : 40× la moyenne habituelle de l'expéditeur"],
            }

    monkeypatch.setattr("routers.transactions.get_fraud_service", lambda: _FakeMLService())
    monkeypatch.setattr(
        "routers.transactions.build_fraud_features", AsyncMock(return_value={"amount": 5000.0})
    )

    resp = client.post(
        "/transactions/send",
        json={"receiver": "0x1234500000000000000000000000000000067890", "amount": 5000.0},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["blocked"] is True
    assert body["reasons"] and "aberrant" in body["reasons"][0]

    added = [call.args[0] for call in mock_db_session.add.call_args_list]
    tx = next(a for a in added if isinstance(a, Transaction))
    alert = next(a for a in added if isinstance(a, FraudAlert))
    assert "aberrant" in tx.block_reasons
    assert alert.transaction_id == tx.id
    assert "aberrant" in alert.block_reason

    # Le blocage est aussi scellé dans la chaîne d'audit (GENESIS + bloc fraude)
    audit_blocks = [a for a in added if isinstance(a, BlockchainAuditBlock)]
    assert [b.event_type for b in audit_blocks] == ["GENESIS", "FRAUD_DETECTED"]
    assert audit_blocks[1].previous_hash == audit_blocks[0].block_hash
