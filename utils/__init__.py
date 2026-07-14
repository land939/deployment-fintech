"""Utility functions for authentication, validation, and helpers."""

import hashlib
import secrets
import re
from datetime import datetime, timedelta
from typing import Tuple


# ════════════════════════════════════════════════════════════════
# Validation Helpers
# ════════════════════════════════════════════════════════════════

EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")
WALLET_REGEX = re.compile(r"^0x[a-fA-F0-9]{40}$")


def is_valid_email(email: str) -> bool:
    """Validate email format."""
    return bool(EMAIL_REGEX.match(email))


def is_valid_wallet(wallet: str) -> bool:
    """Validate Ethereum wallet address format."""
    return bool(WALLET_REGEX.match(wallet))


def is_strong_password(password: str) -> bool:
    """Validate password strength."""
    if len(password) < 8:
        return False
    if not re.search(r"[a-zA-Z]", password):
        return False
    if not re.search(r"[0-9]", password):
        return False
    return True


# ════════════════════════════════════════════════════════════════
# Token & Token Reset Helpers
# ════════════════════════════════════════════════════════════════


def generate_reset_token() -> Tuple[str, str]:
    """
    Generate a reset token and its hash.

    Returns:
        Tuple of (raw_token, token_hash)
    """
    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    return raw_token, token_hash


def build_reset_email_html(reset_link: str, expiry_minutes: int = 30) -> str:
    """Build HTML email for password reset."""
    return f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
      <div style="background: linear-gradient(90deg, #CC0000, #E53E3E); padding: 4px;"></div>
      <div style="padding: 2rem; background:#F5F7FA;">
        <h2 style="color:#1A202C;">🔐 Réinitialisation de mot de passe</h2>
        <p style="color:#2D3748; font-size:0.95rem; line-height:1.6;">
          Vous avez demandé à réinitialiser votre mot de passe sur <b>GTA-IT Fintech</b>.
          Cliquez sur le bouton ci-dessous pour choisir un nouveau mot de passe.
          Ce lien est valable <b>{expiry_minutes} minutes</b>.
        </p>
        <p style="text-align:center; margin: 2rem 0;">
          <a href="{reset_link}"
             style="background:#CC0000; color:#fff; text-decoration:none; padding:0.8rem 1.5rem;
                    border-radius:8px; font-weight:bold; display:inline-block;">
            🔑 Réinitialiser mon mot de passe
          </a>
        </p>
        <p style="color:#718096; font-size:0.85rem;">
          Si vous n'avez pas demandé cette réinitialisation, ignorez cet email.
          Votre compte reste sécurisé.
        </p>
      </div>
      <div style="background:#2D3748; color:#fff; padding:1rem; text-align:center; font-size:0.8rem;">
        <p>© 2026 GTA-IT Fintech. Tous droits réservés.</p>
      </div>
    </div>
    """


# ════════════════════════════════════════════════════════════════
# JWT Helpers
# ════════════════════════════════════════════════════════════════


def get_token_expiry(hours: int) -> datetime:
    """Get token expiry datetime."""
    return datetime.utcnow() + timedelta(hours=hours)
