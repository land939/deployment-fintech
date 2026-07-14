"""Configuration and settings management for GTA Fintech."""

from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """Application settings with validation."""

    # Environment
    environment: str = "local"
    debug: bool = True

    # API Configuration
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_workers: int = 4
    api_log_level: str = "info"

    # Database
    database_url: str

    # Security & JWT
    secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_expiration_hours: int = 24
    jwt_refresh_hours: int = 168

    # Super Admin
    superadmin_email: str
    superadmin_password: str

    # Email
    mail_server: Optional[str] = None
    mail_port: Optional[int] = None
    mail_username: Optional[str] = None
    mail_password: Optional[str] = None
    mail_from: Optional[str] = None
    mail_reset_token_expiry_minutes: int = 30

    # Blockchain
    rpc_url: Optional[str] = None
    admin_address: Optional[str] = None
    admin_private_key: Optional[str] = None
    token_address: Optional[str] = None
    registry_address: Optional[str] = None
    optimizer_address: Optional[str] = None

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
    log_file: Optional[str] = None
    audit_log_file: Optional[str] = None
    security_log_file: Optional[str] = None

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
