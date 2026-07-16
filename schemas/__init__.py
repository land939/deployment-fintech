"""Request/Response schemas for API."""

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

# ════════════════════════════════════════════════════════════════
# Authentication Schemas
# ════════════════════════════════════════════════════════════════


class RegisterRequest(BaseModel):
    """User registration request."""

    email: EmailStr
    password: str = Field(..., min_length=8)
    wallet_address: str = Field(..., pattern=r"^0x[a-fA-F0-9]{40}$")


class LoginRequest(BaseModel):
    """User login request."""

    email: EmailStr
    password: str


class ForgotPasswordRequest(BaseModel):
    """Forgot password request."""

    email: EmailStr


class ResetPasswordRequest(BaseModel):
    """Reset password request."""

    token: str
    password: str = Field(..., min_length=8)


class AuthResponse(BaseModel):
    """Réponse d'authentification JWT (compat UI)."""

    access_token: str
    token_type: str = "bearer"
    user_id: int
    email: str
    role: str
    wallet: str


# ════════════════════════════════════════════════════════════════
# Transaction Schemas
# ════════════════════════════════════════════════════════════════


class TransactionRequest(BaseModel):
    """Soumission de transaction."""

    receiver: str = Field(..., pattern=r"^0x[a-fA-F0-9]{40}$")
    amount: float = Field(..., gt=0)
    features: dict | None = None  # optionnel : 11 features FTK


class TransactionResponse(BaseModel):
    """Transaction response."""

    id: str
    sender: str
    receiver: str
    amount: float
    status: str
    risk_score: int
    risk_level: str
    blocked: bool
    created_at: datetime


# ════════════════════════════════════════════════════════════════
# Fraud Detection Schemas
# ════════════════════════════════════════════════════════════════


class FraudCheckRequest(BaseModel):
    """Requête de prédiction fraude."""

    amount: float
    hour: int | None = None
    hour_of_day: int | None = None
    features: dict | None = None


class FraudCheckResponse(BaseModel):
    """Réponse prédiction fraude."""

    fraud_probability: float
    risk_score: int
    risk_level: str
    blocked: bool
    features_used: int


class ErrorResponse(BaseModel):
    """Erreur API standard."""

    error: str
    detail: str | None = None
    code: str | None = None


class StatusResponse(BaseModel):
    """Statut applicatif (compat badge UI + détail)."""

    app_version: str
    environment: str
    blockchain_connected: bool = False
    chain_id: int | None = None
    ia_model_loaded: bool = False
    total_transactions: int = 0
    database: dict = {}
    blockchain: dict = {}
    ml_models: dict = {}


class HealthResponse(BaseModel):
    """Santé du service."""

    status: str
    timestamp: datetime
