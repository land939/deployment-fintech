"""Configuration and settings management for GTA Fintech."""

import logging
from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """Application settings with validation."""

    # Environment
    environment: str = "local"
    debug: bool = True

    # API Configuration
    # Default loopback for local runs; Docker Compose sets API_HOST=0.0.0.0
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    api_workers: int = 4
    api_log_level: str = "info"

    # Database — SQLite par défaut (local sans Docker).
    # Docker Compose force PostgreSQL via DATABASE_URL.
    database_url: str = "sqlite+aiosqlite:///./gta_fintech.db"

    # Security & JWT
    secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_expiration_hours: int = 24
    jwt_refresh_hours: int = 168

    # Super Admin
    superadmin_email: str
    superadmin_password: str

    # Email
    mail_server: str | None = None
    mail_port: int | None = None
    mail_username: str | None = None
    mail_password: str | None = None
    mail_from: str | None = None
    mail_reset_token_expiry_minutes: int = 30

    # Blockchain
    rpc_url: str | None = None
    admin_address: str | None = None
    admin_private_key: str | None = None
    token_address: str | None = None
    registry_address: str | None = None
    optimizer_address: str | None = None

    # ML Configuration
    ml_model_path: str = "./models/fraud_detector.pkl"
    ml_scaler_path: str = "./models/scaler.pkl"
    ml_features_path: str = "./models/feature_columns.json"
    ml_fraud_threshold: float = 0.30

    # Rate Limiting
    rate_limit_enabled: bool = True
    rate_limit_per_minute: int = 60
    rate_limit_auth_per_minute: int = 5

    # CORS
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:8000"]
    cors_allow_credentials: bool = True

    # Logging
    log_level: str = "INFO"
    log_file: str | None = None
    audit_log_file: str | None = None
    security_log_file: str | None = None

    # Feature Flags
    enable_blockchain: bool = True
    enable_email: bool = True
    enable_ml_fraud_detection: bool = True
    enable_rate_limiting: bool = True

    class Config:
        """Pydantic config."""

        env_file = ".env"
        case_sensitive = False


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# FastAPI-recommended Annotated dependency (avoids B008 on Depends-as-default)
SettingsDep = Annotated[Settings, Depends(get_settings)]


def validate_required_settings(settings: Settings) -> None:
    """Validate critical settings are configured."""
    critical_fields = [
        ("database_url", "Database URL not configured"),
        ("secret_key", "JWT secret key not configured"),
        ("superadmin_email", "Super admin email not configured"),
        ("superadmin_password", "Super admin password not configured"),
    ]

    for field, message in critical_fields:
        if not getattr(settings, field):
            logger.error(f"❌ Configuration Error: {message}")
            raise ValueError(message)

    logger.info("✅ All critical settings validated")
