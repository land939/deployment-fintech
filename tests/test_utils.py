"""Tests for utility functions."""

from utils import (
    generate_reset_token,
    is_strong_password,
    is_valid_email,
    is_valid_wallet,
)


class TestValidation:
    """Test validation functions."""

    def test_valid_email(self, valid_email):
        """Test valid email validation."""
        assert is_valid_email(valid_email) is True

    def test_invalid_emails(self):
        """Test invalid email validation."""
        invalid_emails = [
            "notanemail",
            "missing@domain",
            "@nodomain.com",
            "spaces in@email.com",
        ]
        for email in invalid_emails:
            assert is_valid_email(email) is False

    def test_valid_wallet(self, valid_wallet_address):
        """Test valid wallet address validation."""
        assert is_valid_wallet(valid_wallet_address) is True

    def test_invalid_wallets(self):
        """Test invalid wallet address validation."""
        invalid_wallets = [
            "0x123",  # Too short
            "0x" + "Z" * 40,  # Invalid hex
            "742d35Cc6634C0532925a3b844Bc9e7595f42bE0",  # Missing 0x
            "",
        ]
        for wallet in invalid_wallets:
            assert is_valid_wallet(wallet) is False

    def test_strong_password(self):
        """Test strong password validation."""
        strong_passwords = [
            "Password123",
            "MySecurePass456",
            "Test1234567",
        ]
        for pwd in strong_passwords:
            assert is_strong_password(pwd) is True

    def test_weak_passwords(self):
        """Test weak password validation."""
        weak_passwords = [
            "short1",  # Too short
            "nletters",  # No numbers
            "12345678",  # No letters
            "",
        ]
        for pwd in weak_passwords:
            assert is_strong_password(pwd) is False


class TestTokenGeneration:
    """Test token generation functions."""

    def test_generate_reset_token(self):
        """Test reset token generation."""
        raw_token, token_hash = generate_reset_token()

        assert isinstance(raw_token, str)
        assert isinstance(token_hash, str)
        assert len(raw_token) > 20
        assert len(token_hash) == 64  # SHA256 hex length
        assert raw_token != token_hash

    def test_generate_unique_tokens(self):
        """Test that each generated token is unique."""
        tokens1 = {generate_reset_token()[0] for _ in range(10)}
        tokens2 = {generate_reset_token()[0] for _ in range(10)}

        assert len(tokens1) == 10
        assert len(tokens2) == 10
        assert tokens1.isdisjoint(tokens2)
