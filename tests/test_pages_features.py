"""Tests construction features fraude + pages UI."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from database.models import User
from routers import pages
from services.ml.features import FEATURE_COLS, build_fraud_features


@pytest.mark.asyncio
async def test_build_fraud_features_empty_history(valid_wallet_address):
    user = User(email="u@test.local", wallet_address=valid_wallet_address)
    user.created_at = datetime.utcnow()

    session = AsyncMock()

    def _scalar(value):
        r = MagicMock()
        r.scalar_one.return_value = value
        return r

    def _first(value):
        r = MagicMock()
        r.scalars.return_value.first.return_value = value
        return r

    # counts / avgs / distinct then last_tx query
    session.execute = AsyncMock(
        side_effect=[
            _scalar(0),  # prev_1h
            _scalar(0),  # prev_24h
            _scalar(0),  # n_legit
            _scalar(None),  # avg_amt
            _first(None),  # last_tx
            _scalar(0),  # frauds
            _scalar(0),  # known
            _scalar(0),  # recv_24h
        ]
    )

    features = await build_fraud_features(session, user, amount=50.0, receiver="0x" + "a" * 40)
    assert set(features) == set(FEATURE_COLS)
    assert features["amount"] == 50.0
    assert features["is_new_receiver"] == 1.0
    assert features["past_fraud_count"] == 0.0
    assert features["amount_avg_ratio"] == 1.0


def test_pages_render_login():
    app = FastAPI()
    app.include_router(pages.router)
    with TestClient(app) as client:
        resp = client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "GTA" in resp.text or "Connexion" in resp.text or "login" in resp.text.lower()


def test_pages_render_dashboard():
    app = FastAPI()
    app.include_router(pages.router)
    with TestClient(app) as client:
        resp = client.get("/dashboard")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
