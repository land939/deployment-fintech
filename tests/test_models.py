"""Tests for database models."""

from datetime import datetime, timedelta

from database.models import PasswordResetToken, User


class TestUserModel:
    """Test User model."""

    def test_user_creation(self):
        """Test creating a user."""
        user = User(
            email="test@example.com",
            wallet_address="0x742d35Cc6634C0532925a3b844Bc9e7595f42bE0",
        )
        user.set_password("TestPassword123")

        assert user.email == "test@example.com"
        assert user.password_hash is not None
        assert user.role == "user"
        assert user.is_active is True

    def test_password_hashing(self):
        """Test password hashing and verification."""
        user = User(
            email="test@example.com",
            wallet_address="0x742d35Cc6634C0532925a3b844Bc9e7595f42bE0",
        )
        password = "MySecurePassword123"
        user.set_password(password)

        assert user.verify_password(password) is True
        assert user.verify_password("WrongPassword") is False
        assert user.verify_password("") is False

    def test_account_lockout(self):
        """Test account lockout functionality."""
        user = User(
            email="test@example.com",
            wallet_address="0x742d35Cc6634C0532925a3b844Bc9e7595f42bE0",
        )

        # Initially not locked
        assert user.is_locked() is False

        # Lock account
        user.locked_until = datetime.utcnow() + timedelta(minutes=15)
        assert user.is_locked() is True

        # Unlock
        user.locked_until = datetime.utcnow() - timedelta(minutes=1)
        assert user.is_locked() is False


class TestPasswordResetToken:
    """Test PasswordResetToken model."""

    def test_token_validity(self):
        """Test token validity checking."""
        token = PasswordResetToken(
            user_id=1,
            token_hash="abc123",
            expires_at=datetime.utcnow() + timedelta(minutes=30),
        )

        assert token.is_valid() is True
        assert token.used is False

    def test_expired_token(self):
        """Test expired token."""
        token = PasswordResetToken(
            user_id=1,
            token_hash="abc123",
            expires_at=datetime.utcnow() - timedelta(minutes=1),
        )

        assert token.is_valid() is False

    def test_used_token(self):
        """Test used token."""
        token = PasswordResetToken(
            user_id=1,
            token_hash="abc123",
            expires_at=datetime.utcnow() + timedelta(minutes=30),
            used=True,
        )

        assert token.is_valid() is False
