"""Database models for GTA Fintech."""

from datetime import datetime

from passlib.context import CryptContext
from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import relationship

from database import Base

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class User(Base):
    """User account model."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(120), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=True)
    wallet_address = Column(String(66), nullable=False, unique=True, index=True)
    role = Column(String(20), default="user")  # user | superadmin
    is_active = Column(Boolean, default=True)
    failed_logins = Column(Integer, default=0)
    locked_until = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    transactions = relationship("Transaction", back_populates="user", cascade="all, delete-orphan")
    fraud_alerts = relationship("FraudAlert", back_populates="user", cascade="all, delete-orphan")

    __table_args__ = (Index("ix_user_email_active", "email", "is_active"),)

    def __init__(self, **kwargs):
        kwargs.setdefault("role", "user")
        kwargs.setdefault("is_active", True)
        kwargs.setdefault("failed_logins", 0)
        super().__init__(**kwargs)

    def set_password(self, password: str) -> None:
        """Hash and set password."""
        self.password_hash = pwd_context.hash(password)

    def verify_password(self, password: str) -> bool:
        """Verify password against hash."""
        return pwd_context.verify(password, self.password_hash or "")

    def is_locked(self) -> bool:
        """Check if account is locked."""
        return bool(self.locked_until and datetime.utcnow() < self.locked_until)


class Transaction(Base):
    """Transaction model."""

    __tablename__ = "transactions"

    id = Column(String(36), primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    sender = Column(String(66), nullable=False, index=True)
    receiver = Column(String(66), nullable=False, index=True)
    amount = Column(Float, nullable=False)
    hash = Column(String(66), unique=True, nullable=True)
    status = Column(String(20), default="pending")  # pending | confirmed | failed
    risk_score = Column(Integer, default=0)
    risk_level = Column(String(20), default="LOW")  # LOW | MEDIUM | HIGH | CRITICAL
    blocked = Column(Boolean, default=False)
    approved = Column(Boolean, default=False)  # déblocage manuel superadmin
    block_reasons = Column(Text, nullable=True)  # JSON: facteurs de blocage lisibles
    tx_hash_ref = Column(String(66), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="transactions")

    __table_args__ = (
        Index("ix_transaction_user_created", "user_id", "created_at"),
        Index("ix_transaction_status", "status"),
    )


class FraudAlert(Base):
    """Fraud detection alert model."""

    __tablename__ = "fraud_alerts"

    id = Column(String(36), primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    transaction_id = Column(String(36), ForeignKey("transactions.id"), nullable=True)
    suspect_address = Column(String(66), nullable=False, index=True)
    victim_address = Column(String(66), nullable=True)
    amount = Column(Float, nullable=False)
    risk_score = Column(Integer, nullable=False)
    risk_level = Column(String(20), nullable=False)  # LOW | MEDIUM | HIGH | CRITICAL
    model_used = Column(String(50), nullable=False)  # RandomForest | XGBoost
    features_json = Column(Text, nullable=True)
    block_reason = Column(String(255), nullable=True)
    blocked = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="fraud_alerts")

    __table_args__ = (
        Index("ix_fraud_alert_risk", "risk_level", "created_at"),
        Index("ix_fraud_alert_address", "suspect_address"),
    )


class Dispute(Base):
    """Contestation d'une transaction refusée par la détection de fraude.

    L'utilisateur explique pourquoi sa transaction est légitime ; le super
    admin tranche : accepted (blocage levé) ou rejected. Statuts :
    pending | accepted | rejected.
    """

    __tablename__ = "disputes"

    id = Column(String(36), primary_key=True, index=True)
    transaction_id = Column(String(36), ForeignKey("transactions.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    message = Column(Text, nullable=False)  # explication de l'utilisateur
    status = Column(String(20), default="pending", nullable=False)
    admin_response = Column(Text, nullable=True)  # justification de la décision
    created_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)

    user = relationship("User")
    transaction = relationship("Transaction")

    __table_args__ = (
        Index("ix_dispute_status", "status", "created_at"),
        Index("ix_dispute_user", "user_id", "created_at"),
    )

    def __init__(self, **kwargs):
        kwargs.setdefault("status", "pending")
        super().__init__(**kwargs)


class AuditLog(Base):
    """Audit and security logging model."""

    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    event_type = Column(String(50), nullable=False, index=True)
    email = Column(String(120), nullable=True, index=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    details = Column(Text, nullable=True)
    success = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        Index("ix_audit_event_time", "event_type", "created_at"),
        Index("ix_audit_email_time", "email", "created_at"),
    )


class PasswordResetToken(Base):
    """Password reset token model."""

    __tablename__ = "password_reset_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    token_hash = Column(String(64), unique=True, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    used = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    def __init__(self, **kwargs):
        kwargs.setdefault("used", False)
        super().__init__(**kwargs)

    def is_valid(self) -> bool:
        """Check if token is still valid."""
        return not self.used and datetime.utcnow() < self.expires_at


class BlockchainAuditBlock(Base):
    """Immutable blockchain audit block model."""

    __tablename__ = "blockchain_audit_blocks"

    id = Column(Integer, primary_key=True, index=True)
    block_index = Column(Integer, unique=True, nullable=False)
    event_type = Column(String(50), nullable=False)
    data = Column(Text, nullable=False)
    previous_hash = Column(String(64), nullable=False)
    block_hash = Column(String(64), unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (Index("ix_blockchain_audit_time", "created_at"),)
