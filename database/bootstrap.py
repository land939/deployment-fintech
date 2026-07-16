"""Bootstrap helpers (superadmin seed, etc.)."""

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from config.settings import Settings
from database.models import User
from utils import is_valid_wallet

logger = logging.getLogger(__name__)

# Wallet démo si ADMIN_ADDRESS n'est pas configuré
_DEFAULT_ADMIN_WALLET = "0x1111111111111111111111111111111111111111"


async def ensure_superadmin(
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
) -> None:
    """Crée ou met à jour le compte superadmin depuis SUPERADMIN_*."""
    email = settings.superadmin_email.strip().lower()
    wallet = (
        settings.admin_address
        if settings.admin_address and is_valid_wallet(settings.admin_address)
        else _DEFAULT_ADMIN_WALLET
    )

    async with session_factory() as db:
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalars().first()
        if user is None:
            user = User(
                email=email,
                wallet_address=wallet,
                role="superadmin",
                is_active=True,
            )
            user.set_password(settings.superadmin_password)
            db.add(user)
            await db.commit()
            logger.info("Super admin créé : %s", email)
            return

        changed = False
        if user.role != "superadmin":
            user.role = "superadmin"
            changed = True
        if not user.verify_password(settings.superadmin_password):
            user.set_password(settings.superadmin_password)
            changed = True
        if changed:
            await db.commit()
            logger.info("Super admin mis à jour : %s", email)
        else:
            logger.info("Super admin déjà présent : %s", email)
