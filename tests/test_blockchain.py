"""Unit tests for blockchain helpers."""

from web3.constants import ADDRESS_ZERO

from services.blockchain import _is_configured_address


def test_none_and_empty_not_configured():
    assert _is_configured_address(None) is False
    assert _is_configured_address("") is False


def test_zero_address_not_configured():
    assert _is_configured_address(ADDRESS_ZERO) is False
    assert _is_configured_address("0x0") is False
    assert _is_configured_address("0x0000000000000000000000000000000000000000") is False


def test_valid_address_is_configured(valid_wallet_address):
    assert _is_configured_address(valid_wallet_address) is True


def test_garbage_not_configured():
    assert _is_configured_address("not-an-address") is False
