"""Authentication routes."""

import logging
from datetime import datetime, timedelta

from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from fastapi.concurrency import run_in_threadpool

from config import SettingsDep
from database import DbSession
from database.models import PasswordResetToken, User
from schemas import (
    AuthResponse,
    ForgotPasswordRequest,
    LoginRequest,
    RegisterRequest,
    ResetPasswordRequest,
)
from services.auth import create_access_token
from services.email import send_email
from utils import (
    build_reset_email_html,
    generate_reset_token,
    is_strong_password,
    is_valid_email,
    is_valid_wallet,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["Authentication"])


SIGNUP_BONUS_FTK = 1000.0


def _send_signup_bonus(wallet_address: str) -> None:
    """Bonus d'inscription : 1 000 FTK transférés on-chain depuis l'admin.

    Best-effort en tâche de fond : si Ganache est hors ligne, l'inscription
    reste valide et le bonus pourra être re-crédité manuellement.
    """
    from services.blockchain import get_blockchain_service

    chain = get_blockchain_service()
    if not chain or not chain.connected:
        logger.warning("Bonus 1000 FTK non envoyé à %s (blockchain hors ligne)", wallet_address)
        return
    result = chain.transfer_from_admin(wallet_address, SIGNUP_BONUS_FTK)
    if "error" in result:
        logger.error("Bonus 1000 FTK échoué pour %s : %s", wallet_address, result["error"])
    else:
        logger.info("🎁 Bonus 1000 FTK crédité à %s (tx %s)", wallet_address, result["tx_hash"])


@router.post("/register", response_model=dict, status_code=status.HTTP_201_CREATED)
async def register(
    request: RegisterRequest,
    db: DbSession,
    settings: SettingsDep,
    background_tasks: BackgroundTasks,
):
    """Register a new user."""
    # Validate inputs
    if not is_valid_email(request.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid email format",
        )

    if not is_strong_password(request.password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters with letters and numbers",
        )

    if not is_valid_wallet(request.wallet_address):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid wallet address format",
        )

    # Check if email already exists
    from sqlalchemy import select

    existing_user = await db.execute(select(User).where(User.email == request.email.lower()))
    if existing_user.scalars().first():
        logger.warning(f"⚠️  Registration attempt with existing email: {request.email}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    # Create new user
    user = User(
        email=request.email.lower(),
        wallet_address=request.wallet_address,
        role="user",
        is_active=True,
    )
    user.set_password(request.password)

    db.add(user)
    await db.flush()
    await db.commit()

    logger.info(f"✅ New user registered: {request.email}")

    # Bonus de bienvenue on-chain, après la réponse HTTP (signature + minage)
    background_tasks.add_task(_send_signup_bonus, user.wallet_address)

    # Connexion immédiate : on renvoie un JWT comme /login, pour que le
    # front puisse rediriger vers le dashboard sans re-saisir les identifiants.
    token = create_access_token(user, settings)

    return {
        "message": "Registration successful",
        "access_token": token,
        "token_type": "bearer",
        "user_id": user.id,
        "email": user.email,
        "role": user.role,
        "wallet": user.wallet_address,
    }


@router.post("/login", response_model=AuthResponse)
async def login(
    request: LoginRequest,
    db: DbSession,
    settings: SettingsDep,
):
    """User login with email and password."""
    if not is_valid_email(request.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid email format",
        )

    # Get user
    from sqlalchemy import select

    result = await db.execute(select(User).where(User.email == request.email.lower()))
    user = result.scalars().first()

    if not user:
        logger.warning(f"⚠️  Login attempt with non-existent email: {request.email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    # Check if account is locked
    if user.is_locked():
        logger.warning(f"⚠️  Login attempt on locked account: {request.email}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is temporarily locked",
        )

    # Verify password
    if not user.verify_password(request.password):
        user.failed_logins += 1
        if user.failed_logins >= 5:
            user.locked_until = datetime.utcnow() + timedelta(minutes=15)
        await db.commit()
        logger.warning(f"⚠️  Failed login for {request.email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    # Reset failed logins
    user.failed_logins = 0
    user.locked_until = None
    await db.commit()

    token = create_access_token(user, settings)

    logger.info(f"✅ User logged in: {request.email}")

    return AuthResponse(
        access_token=token,
        user_id=user.id,
        email=user.email,
        role=user.role,
        wallet=user.wallet_address,
    )


@router.post("/forgot-password")
async def forgot_password(
    request: ForgotPasswordRequest,
    db: DbSession,
    settings: SettingsDep,
):
    """Request password reset."""
    if not is_valid_email(request.email):
        # Don't reveal if email exists
        return {"message": "If email exists, reset link will be sent"}

    from sqlalchemy import select

    result = await db.execute(select(User).where(User.email == request.email.lower()))
    user = result.scalars().first()

    if not user:
        logger.info(f"📧 Forgot password request for non-existent email: {request.email}")
        return {"message": "If email exists, reset link will be sent"}

    # Generate reset token
    expiry = settings.mail_reset_token_expiry_minutes
    raw_token, token_hash = generate_reset_token()
    reset_token = PasswordResetToken(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=datetime.utcnow() + timedelta(minutes=expiry),
    )
    db.add(reset_token)
    await db.commit()

    reset_link = f"{settings.app_base_url.rstrip('/')}/reset-password?token={raw_token}"
    email_html = build_reset_email_html(reset_link, expiry)

    # SMTP est bloquant → threadpool pour ne pas geler l'event loop
    sent = await run_in_threadpool(
        send_email,
        settings,
        user.email,
        "Réinitialisation de votre mot de passe — GTA-IT Fintech",
        email_html,
    )
    if sent:
        logger.info(f"📧 Password reset email sent: {request.email}")
    else:
        # Filet de sécurité local : sans SMTP, le lien reste utilisable via les logs
        logger.warning(f"📧 Reset email NOT sent — lien de secours : {reset_link}")

    return {"message": "If email exists, reset link will be sent"}


@router.post("/reset-password")
async def reset_password(
    request: ResetPasswordRequest,
    db: DbSession,
):
    """Reset password with token."""
    import hashlib

    if not is_strong_password(request.password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password too weak",
        )

    token_hash = hashlib.sha256(request.token.encode()).hexdigest()

    from sqlalchemy import select

    result = await db.execute(
        select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash)
    )
    reset_token = result.scalars().first()

    if not reset_token or not reset_token.is_valid():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        )

    # Update password
    user = await db.get(User, reset_token.user_id)
    user.set_password(request.password)
    user.failed_logins = 0
    user.locked_until = None
    reset_token.used = True
    await db.commit()

    logger.info(f"✅ Password reset successful for user {user.id}")

    return {"message": "Password reset successful"}
