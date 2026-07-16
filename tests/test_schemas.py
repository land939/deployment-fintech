"""Unit tests for Pydantic schemas."""

import pytest
from pydantic import ValidationError

from schemas import LoginRequest, RegisterRequest, TransactionRequest


class TestRegisterRequest:
    def test_valid_register(self, valid_email, valid_wallet_address):
        req = RegisterRequest(
            email=valid_email,
            password="Password123",
            wallet_address=valid_wallet_address,
        )
        assert req.email == valid_email
        assert req.wallet_address == valid_wallet_address

    def test_rejects_short_password(self, valid_email, valid_wallet_address):
        with pytest.raises(ValidationError):
            RegisterRequest(
                email=valid_email,
                password="short1",
                wallet_address=valid_wallet_address,
            )

    def test_rejects_bad_wallet(self, valid_email):
        with pytest.raises(ValidationError):
            RegisterRequest(
                email=valid_email,
                password="Password123",
                wallet_address="not-a-wallet",
            )


class TestLoginRequest:
    def test_valid_login(self, valid_email):
        req = LoginRequest(email=valid_email, password="x")
        assert req.email == valid_email

    def test_rejects_invalid_email(self):
        with pytest.raises(ValidationError):
            LoginRequest(email="not-an-email", password="x")


class TestTransactionRequest:
    def test_valid_transaction(self, valid_wallet_address):
        req = TransactionRequest(receiver=valid_wallet_address, amount=10.5)
        assert req.amount == 10.5

    def test_rejects_non_positive_amount(self, valid_wallet_address):
        with pytest.raises(ValidationError):
            TransactionRequest(receiver=valid_wallet_address, amount=0)
