"""Authentication routes."""

import logging
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession

from config import Settings, get_settings
from database import get_session
from database.models import User, PasswordResetToken
from schemas import RegisterRequest, LoginRequest, ForgotPasswordRequest, ResetPasswordRequest, AuthResponse
from utils import (
    is_valid_email,
    is_valid_wallet,
    is_strong_password,
    generate_reset_token,
    build_reset_email_html,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=dict, status_code=status.HTTP_201_CREATED)
async def register(
    request: RegisterRequest,
    db: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
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

    existing_user = await db.execute(
        select(User).where(User.email == request.email.lower())
    )
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

    return {
        "message": "Registration successful",
        "user_id": user.id,
        "email": user.email,
    }


@router.post("/login", response_model=AuthResponse)
async def login(
    request: LoginRequest,
    db: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
):
    """User login with email and password."""
    if not is_valid_email(request.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid email format",
        )

    # Get user
    from sqlalchemy import select

    result = await db.execute(
        select(User).where(User.email == request.email.lower())
    )
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

    # Generate JWT token
    from jose import jwt

    payload = {
        "sub": user.email,
        "user_id": user.id,
        "exp": datetime.utcnow() + timedelta(hours=settings.jwt_expiration_hours),
    }
    token = jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)

    logger.info(f"✅ User logged in: {request.email}")

    return AuthResponse(
        access_token=token,
        user_id=user.id,
        email=user.email,
        role=user.role,
    )


@router.post("/forgot-password")
async def forgot_password(
    request: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_session),
):
    """Request password reset."""
    if not is_valid_email(request.email):
        # Don't reveal if email exists
        return {"message": "If email exists, reset link will be sent"}

    from sqlalchemy import select

    result = await db.execute(
        select(User).where(User.email == request.email.lower())
    )
    user = result.scalars().first()

    if not user:
        logger.info(f"📧 Forgot password request for non-existent email: {request.email}")
        return {"message": "If email exists, reset link will be sent"}

    # Generate reset token
    raw_token, token_hash = generate_reset_token()
    reset_token = PasswordResetToken(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=datetime.utcnow() + timedelta(minutes=30),
    )
    db.add(reset_token)
    await db.commit()

    # Build reset link
    reset_link = f"http://localhost:8000/reset-password?token={raw_token}"
    email_html = build_reset_email_html(reset_link, 30)

    # TODO: Send email
    logger.info(f"📧 Password reset requested: {request.email}")
    logger.debug(f"Reset link (not sent): {reset_link}")

    return {"message": "If email exists, reset link will be sent"}


@router.post("/reset-password")
async def reset_password(
    request: ResetPasswordRequest,
    db: AsyncSession = Depends(get_session),
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
