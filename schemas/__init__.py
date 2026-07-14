"""Request/Response schemas for API."""

from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime


# ════════════════════════════════════════════════════════════════
# Authentication Schemas
# ════════════════════════════════════════════════════════════════


class RegisterRequest(BaseModel):
    """User registration request."""

    email: EmailStr
    password: str = Field(..., min_length=8)
    wallet_address: str = Field(..., regex=r"^0x[a-fA-F0-9]{40}$")


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
    """Authentication response with JWT token."""

    access_token: str
    token_type: str = "bearer"
    user_id: int
    email: str
    role: str


# ════════════════════════════════════════════════════════════════
# Transaction Schemas
# ════════════════════════════════════════════════════════════════


class TransactionRequest(BaseModel):
    """Transaction submission request."""

    receiver: str = Field(..., regex=r"^0x[a-fA-F0-9]{40}$")
    amount: float = Field(..., gt=0)
    features: Optional[dict] = None  # Optional: all 31 features for fraud detection


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
    """Fraud prediction request."""

    amount: float
    time: Optional[int] = None
    hour_of_day: Optional[int] = None
    # Optional: include V1-V28 features
    features: Optional[dict] = None


class FraudCheckResponse(BaseModel):
    """Fraud prediction response."""

    fraud_probability: float
    risk_score: int
    risk_level: str
    blocked: bool
    features_used: int


# ════════════════════════════════════════════════════════════════
# Error Schemas
# ════════════════════════════════════════════════════════════════


class ErrorResponse(BaseModel):
    """Standard error response."""

    error: str
    detail: Optional[str] = None
    code: Optional[str] = None


# ════════════════════════════════════════════════════════════════
# Status Schemas
# ════════════════════════════════════════════════════════════════


class StatusResponse(BaseModel):
    """Application status response."""

    app_version: str
    environment: str
    database: dict
    blockchain: dict
    ml_models: dict


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    timestamp: datetime
