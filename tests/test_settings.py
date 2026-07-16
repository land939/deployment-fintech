"""Unit tests for settings defaults."""

from config import Settings


def _make_settings(**kwargs):
    """Build Settings without loading repo .env (avoids local API_HOST bleed)."""
    base = {
        "database_url": "sqlite+aiosqlite:///:memory:",
        "secret_key": "k",
        "superadmin_email": "a@b.c",
        "superadmin_password": "Password123!",
        "_env_file": None,
    }
    base.update(kwargs)
    return Settings(**base)


def test_api_host_defaults_to_loopback():
    """Local default is loopback; Docker Compose overrides to 0.0.0.0 via env."""
    s = _make_settings()
    assert s.api_host == "127.0.0.1"


def test_api_host_env_override(monkeypatch):
    monkeypatch.setenv("API_HOST", "0.0.0.0")
    s = _make_settings()
    assert s.api_host == "0.0.0.0"
