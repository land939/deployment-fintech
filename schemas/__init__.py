"""Request/Response schemas for API."""

from datetime import datetime

from pydantic import BaseModel, Field

# ════════════════════════════════════════════════════════════════
# Authentication Schemas
# ════════════════════════════════════════════════════════════════


class RegisterRequest(BaseModel):
    """User registration request."""

    # ponytail: str not EmailStr — email-validator rejects .local (dev SUPERADMIN_*)
    email: str = Field(..., min_length=3)
    password: str = Field(..., min_length=8)
    wallet_address: str = Field(..., pattern=r"^0x[a-fA-F0-9]{40}$")


class LoginRequest(BaseModel):
    """User login request."""

    email: str = Field(..., min_length=3)
    password: str


class ForgotPasswordRequest(BaseModel):
    """Forgot password request."""

    email: str = Field(..., min_length=3)


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
    reasons: list[str] = []
    amount_eth: float | None = None  # équivalent ETH (taux FTK_ETH_RATE)
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
    reasons: list[str] = []
    features_used: int


# ════════════════════════════════════════════════════════════════
# Dispute (contestation) Schemas
# ════════════════════════════════════════════════════════════════


class DisputeCreateRequest(BaseModel):
    """Contestation d'une transaction refusée."""

    transaction_id: str
    message: str = Field(..., min_length=10, max_length=2000)


class DisputeDecisionRequest(BaseModel):
    """Décision du super admin sur une contestation."""

    accept: bool
    response: str | None = Field(default=None, max_length=2000)


# ════════════════════════════════════════════════════════════════
# Wallet Schemas
# ════════════════════════════════════════════════════════════════


class WalletLinkRequest(BaseModel):
    """Association d'un wallet MetaMask au compte."""

    address: str = Field(..., pattern=r"^0x[a-fA-F0-9]{40}$")


class TxConfirmRequest(BaseModel):
    """Confirmation on-chain d'une transaction (hash MetaMask)."""

    tx_hash: str = Field(..., pattern=r"^0x[a-fA-F0-9]{64}$")


class ErrorResponse(BaseModel):
    """Erreur API standard."""

    error: str
    detail: str | None = None
    code: str | None = None


class StatusResponse(BaseModel):
    """Statut applicatif (badge UI)."""

    app_version: str
    environment: str
    blockchain_connected: bool = False
    chain_id: int | None = None
    token_address: str | None = None  # adresse du contrat FTK (pour MetaMask)
    ftk_eth_rate: float | None = None  # 1 FTK en ETH
    ia_model_loaded: bool = False
    total_transactions: int = 0


class HealthResponse(BaseModel):
    """Santé du service."""

    status: str
    timestamp: datetime
