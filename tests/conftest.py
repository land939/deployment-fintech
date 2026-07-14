"""Pytest configuration and fixtures."""

import pytest
from config import Settings


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
    )


@pytest.fixture
def mock_fraud_data():
    """Provide mock transaction data for fraud testing."""
    return {
        "Amount": 100.0,
        "Time": 0,
        "V1": 0.0,
        "V2": 0.0,
        "V3": 0.0,
        "V4": 0.0,
        "V5": 0.0,
        "V6": 0.0,
        "V7": 0.0,
        "V8": 0.0,
        "V9": 0.0,
        "V10": 0.0,
        "V11": 0.0,
        "V12": 0.0,
        "V13": 0.0,
        "V14": 0.0,
        "V15": 0.0,
        "V16": 0.0,
        "V17": 0.0,
        "V18": 0.0,
        "V19": 0.0,
        "V20": 0.0,
        "V21": 0.0,
        "V22": 0.0,
        "V23": 0.0,
        "V24": 0.0,
        "V25": 0.0,
        "V26": 0.0,
        "V27": 0.0,
        "V28": 0.0,
    }


@pytest.fixture
def valid_wallet_address():
    """Provide a valid Ethereum wallet address."""
    return "0x742d35Cc6634C0532925a3b844Bc9e7595f42bE0"


@pytest.fixture
def valid_email():
    """Provide a valid email address."""
    return "test@example.com"
